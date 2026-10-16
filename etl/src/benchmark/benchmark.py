"""Benchmark de las consultas analíticas y del dashboard.

Corre cada sentencia de sql/analysis/*.sql y sql/optimization/dashboard.sql con
`EXPLAIN (ANALYZE, BUFFERS)` como bi_reader, varias veces, y escribe un reporte en Markdown con
la mediana, los buffers leídos y los escaneos del plan. Opcionalmente suma los tiempos por modelo
de un `run_results.json` de dbt y compara contra una medición anterior.

Uso (desde la raíz del repo, con el stack levantado):
    make bench label=baseline
    make bench label=after baseline=baseline
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import statistics
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

import psycopg
from psycopg.conninfo import make_conninfo

log = logging.getLogger("benchmark")

DEFAULT_QUERIES = ("sql/analysis/*.sql", "sql/optimization/dashboard.sql")
SETTINGS = (
    "shared_buffers",
    "work_mem",
    "effective_cache_size",
    "max_parallel_workers_per_gather",
    "jit",
    "random_page_cost",
)
BLOCK_BYTES = 8192
STATS_MIN_ROWS = 10_000  # por debajo, el autovacuum puede no analizar nunca la tabla
NAME_COMMENT = re.compile(r"^--\s*name:\s*(\S+)\s*$")


@dataclass(frozen=True)
class Query:
    name: str
    title: str
    sql: str
    source: str


@dataclass
class Result:
    name: str
    title: str
    source: str
    runs_ms: list[float]
    planning_ms: float
    shared_hit_mb: float
    shared_read_mb: float
    temp_written_mb: float
    workers: int
    scans: list[str] = field(default_factory=list)

    @property
    def median_ms(self) -> float:
        return statistics.median(self.runs_ms)


# --------------------------------------------------------------------------------------------
# Lectura de las consultas
# --------------------------------------------------------------------------------------------


def split_statements(text: str, stem: str, source: str = "") -> list[Query]:
    """Separa un archivo en sentencias. Corta en las líneas de código que terminan en `;`,
    así un `;` dentro de un comentario no parte la sentencia.

    El nombre sale de un comentario `-- name: x`; si no hay, `<stem>` o `<stem>_<n>`. El título
    es el primer comentario de la sentencia que no es el nombre."""
    chunks: list[list[str]] = [[]]
    for line in text.splitlines():
        chunks[-1].append(line)
        stripped = line.strip()
        if not stripped.startswith("--") and stripped.endswith(";"):
            chunks.append([])

    statements = []
    for lines in chunks:
        code = [line for line in lines if line.strip() and not line.strip().startswith("--")]
        if not code:
            continue
        comments = [line.strip()[2:].strip() for line in lines if line.strip().startswith("--")]
        name = next((m.group(1) for c in lines if (m := NAME_COMMENT.match(c.strip()))), None)
        title = next((c for c in comments if c and not c.startswith("name:")), "")
        sql = "\n".join(code).strip().removesuffix(";")
        statements.append(Query(name or "", title, sql, source))

    unnamed = [q for q in statements if not q.name]
    for index, query in enumerate(statements):
        if not query.name:
            suffix = f"_{unnamed.index(query) + 1}" if len(unnamed) > 1 else ""
            statements[index] = Query(f"{stem}{suffix}", query.title, query.sql, query.source)
    return statements


def load_queries(root: Path, patterns: tuple[str, ...]) -> list[Query]:
    queries = []
    for pattern in patterns:
        for path in sorted(root.glob(pattern)):
            text = path.read_text(encoding="utf-8")
            queries.extend(split_statements(text, path.stem, str(path.relative_to(root))))
    return queries


# --------------------------------------------------------------------------------------------
# Lectura del plan
# --------------------------------------------------------------------------------------------


def walk(node: dict):
    yield node
    for child in node.get("Plans", []):
        yield from walk(child)


def summarize_plan(plan: dict) -> dict:
    """Del JSON de `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`: tiempos, buffers del nodo raíz
    (son acumulados), workers paralelos y los escaneos por tabla."""
    root = plan["Plan"]
    scans: list[str] = []
    workers = 0
    for node in walk(root):
        workers = max(workers, node.get("Workers Launched", 0))
        if "Relation Name" in node:
            scan = f"{node['Node Type']} {node['Relation Name']}"
            if scan not in scans:
                scans.append(scan)
    mb = BLOCK_BYTES / 1024 / 1024
    return {
        "execution_ms": plan["Execution Time"],
        "planning_ms": plan["Planning Time"],
        "shared_hit_mb": root.get("Shared Hit Blocks", 0) * mb,
        "shared_read_mb": root.get("Shared Read Blocks", 0) * mb,
        "temp_written_mb": root.get("Temp Written Blocks", 0) * mb,
        "workers": workers,
        "scans": scans,
    }


# --------------------------------------------------------------------------------------------
# Medición
# --------------------------------------------------------------------------------------------


def measure(conn: psycopg.Connection, query: Query, runs: int, plans_dir: Path) -> Result:
    with conn.cursor() as cur:
        cur.execute(query.sql)  # calentamiento: deja las páginas en caché
        cur.fetchall()
        summaries = []
        for _ in range(runs):
            cur.execute(f"explain (analyze, buffers, format json) {query.sql}")
            summaries.append(summarize_plan(cur.fetchone()[0][0]))
        cur.execute(f"explain (analyze, buffers) {query.sql}")
        plan_text = "\n".join(row[0] for row in cur.fetchall())

    plans_dir.mkdir(parents=True, exist_ok=True)
    (plans_dir / f"{query.name}.txt").write_text(
        f"-- {query.source}: {query.title}\n\n{query.sql};\n\n{plan_text}\n", encoding="utf-8"
    )
    last = summaries[-1]
    return Result(
        name=query.name,
        title=query.title,
        source=query.source,
        runs_ms=[s["execution_ms"] for s in summaries],
        planning_ms=statistics.median(s["planning_ms"] for s in summaries),
        shared_hit_mb=last["shared_hit_mb"],
        shared_read_mb=last["shared_read_mb"],
        temp_written_mb=last["temp_written_mb"],
        workers=last["workers"],
        scans=last["scans"],
    )


def wait_for_stats(conn: psycopg.Connection, timeout_s: int) -> list[str]:
    """Espera a que las tablas grandes de gold tengan estadísticas.

    dbt recrea las tablas y no las analiza: hasta que corre el autovacuum, el planner estima
    con valores por defecto y la medición no es comparable. Devuelve las que siguen sin
    estadísticas al vencer el plazo."""
    pending_sql = """
        select relname from pg_stat_user_tables
        where schemaname = 'gold' and n_live_tup >= %s
          and last_analyze is null and last_autoanalyze is null
        order by relname
    """
    deadline = time.monotonic() + timeout_s
    while True:
        pending = [row[0] for row in conn.execute(pending_sql, (STATS_MIN_ROWS,))]
        if not pending or time.monotonic() >= deadline:
            return pending
        log.info("Esperando el autoanalyze de %s...", ", ".join(pending))
        time.sleep(5)


def dbt_timings(path: Path) -> dict:
    """Tiempo total y por modelo de un run_results.json de dbt (solo modelos, sin tests)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    models = {
        r["unique_id"].split(".")[-1]: r["execution_time"]
        for r in data["results"]
        if r["unique_id"].startswith("model.")
    }
    return {"elapsed_s": data["elapsed_time"], "models": models}


# --------------------------------------------------------------------------------------------
# Reporte
# --------------------------------------------------------------------------------------------


def fmt_num(value: float, decimals: int) -> str:
    """Formato es-AR: `1234.5` -> `1.234,5`."""
    text = f"{value:,.{decimals}f}"
    return text.replace(",", "_").replace(".", ",").replace("_", ".")


def fmt_ms(value: float) -> str:
    """Milisegundos: sin decimales desde 100 ms, con uno por debajo."""
    return fmt_num(value, 0 if value >= 100 else 1)


def fmt_mb(value: float) -> str:
    return "0" if value == 0 else fmt_num(value, 1)


def speedup(before: float, after: float) -> str:
    if after <= 0 or before <= 0:
        return "–"
    ratio = before / after
    return f"{fmt_num(ratio, 1)}×" if ratio >= 1 else f"{fmt_num(ratio, 2)}× (peor)"


def render_report(report: dict, baseline: dict | None) -> str:
    lines = [
        f"# Benchmark: {report['label']}",
        "",
        f"> Generado por `make bench label={report['label']}"
        + (f" baseline={baseline['label']}" if baseline else "")
        + "`. No editar a mano: volver a correr el comando.",
        "",
        f"- Fecha: {report['date']}",
        f"- {report['version']}",
        f"- Corridas por consulta: {report['runs']} (más una de calentamiento); se informa la "
        "mediana del tiempo de ejecución de `EXPLAIN ANALYZE`.",
        "- Configuración: "
        + ", ".join(f"`{k}={v}`" for k, v in report["settings"].items()),
    ]
    wait = report.get("stats_wait_s", 0)
    lines.append(
        f"- Estadísticas de gold: hubo que esperar {wait} s al autoanalyze antes de medir."
        if wait
        else "- Estadísticas de gold: ya estaban al empezar."
    )
    if report.get("without_stats"):
        lines.append(f"- **Medido sin estadísticas en:** {', '.join(report['without_stats'])}")
    if baseline:
        lines.append(f"- Comparado contra: `{baseline['label']}` ({baseline['date']})")

    before = {r["name"]: r for r in baseline["queries"]} if baseline else {}
    lines += ["", "## Consultas", ""]
    if baseline:
        lines += [
            "| Consulta | Antes (ms) | Ahora (ms) | Mejora | Leído de disco (MB) | "
            "Temp escrito (MB) | Escaneos |",
            "|---|--:|--:|--:|--:|--:|---|",
        ]
    else:
        lines += [
            "| Consulta | Mediana (ms) | Mín–máx (ms) | Caché (MB) | Leído de disco (MB) | "
            "Temp escrito (MB) | Workers | Escaneos |",
            "|---|--:|--:|--:|--:|--:|--:|---|",
        ]
    for r in report["queries"]:
        median = statistics.median(r["runs_ms"])
        scans = "<br>".join(r["scans"])
        name = f"`{r['name']}`"
        if baseline:
            prev = before.get(r["name"])
            prev_ms = statistics.median(prev["runs_ms"]) if prev else None
            lines.append(
                f"| {name} | {fmt_ms(prev_ms) if prev else '–'} | {fmt_ms(median)} | "
                f"{speedup(prev_ms, median) if prev else '–'} | {fmt_mb(r['shared_read_mb'])} | "
                f"{fmt_mb(r['temp_written_mb'])} | {scans} |"
            )
        else:
            lines.append(
                f"| {name} | {fmt_ms(median)} | "
                f"{fmt_ms(min(r['runs_ms']))}–{fmt_ms(max(r['runs_ms']))} | "
                f"{fmt_mb(r['shared_hit_mb'])} | {fmt_mb(r['shared_read_mb'])} | "
                f"{fmt_mb(r['temp_written_mb'])} | {r['workers']} | {scans} |"
            )

    lines += ["", "<details><summary>Qué mide cada consulta</summary>", ""]
    lines += [f"- `{r['name']}` ({r['source']}): {r['title']}" for r in report["queries"]]
    lines += ["", "</details>"]

    dbt = report.get("dbt")
    if dbt:
        prev_dbt = (baseline or {}).get("dbt") or {}
        prev_models = prev_dbt.get("models", {})
        lines += ["", "## Build de dbt (`dbt run`)", ""]
        total = f"{fmt_num(dbt['elapsed_s'], 1)} s"
        if prev_dbt:
            total = f"{fmt_num(prev_dbt['elapsed_s'], 1)} s → {total}"
        lines += [f"Tiempo total de pared: **{total}** (los modelos corren en paralelo).", ""]
        if prev_dbt:
            lines += ["| Modelo | Antes (s) | Ahora (s) |", "|---|--:|--:|"]
        else:
            lines += ["| Modelo | Tiempo (s) |", "|---|--:|"]
        for model, seconds in sorted(dbt["models"].items(), key=lambda item: -item[1]):
            if seconds < 1 and prev_models.get(model, 0) < 1:
                continue
            if prev_dbt:
                prev_s = prev_models.get(model)
                prev_txt = fmt_num(prev_s, 1) if prev_s is not None else "–"
                lines.append(f"| `{model}` | {prev_txt} | {fmt_num(seconds, 1)} |")
            else:
                lines.append(f"| `{model}` | {fmt_num(seconds, 1)} |")
        lines += ["", "Se omiten los modelos de menos de 1 s."]
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------------


def conninfo_from_env() -> str:
    """Conexión como bi_reader desde el host (el puerto publicado de postgres)."""
    missing = [n for n in ("POSTGRES_DB", "BI_DB_USER", "BI_DB_PASSWORD") if not os.environ.get(n)]
    if missing:
        raise SystemExit(f"Faltan variables de entorno: {', '.join(missing)} (ver .env)")
    return make_conninfo(
        host=os.environ.get("BENCH_DB_HOST", "localhost"),
        port=os.environ.get("POSTGRES_HOST_PORT", "5432"),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["BI_DB_USER"],
        password=os.environ["BI_DB_PASSWORD"],
        application_name="ecobici-benchmark",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--label", required=True, help="nombre de la medición (ej. baseline)")
    parser.add_argument("--baseline", help="label de una medición anterior para comparar")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--only", help="corre solo las consultas cuyo nombre empieza así")
    parser.add_argument("--dbt-results", type=Path, help="run_results.json de un dbt run")
    parser.add_argument(
        "--stats-timeout", type=int, default=300, help="segundos de espera al autoanalyze"
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--out-dir", type=Path, default=Path("sql/optimization"))
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if not re.fullmatch(r"[a-z0-9_-]+", args.label):
        log.error("label debe ser minúsculas, números, - o _: %r", args.label)
        return 1
    baseline = None
    if args.baseline:
        baseline_path = args.out_dir / "results" / f"{args.baseline}.json"
        if not baseline_path.exists():
            log.error("No existe la medición %s (%s)", args.baseline, baseline_path)
            return 1
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))

    queries = load_queries(args.root, DEFAULT_QUERIES)
    if args.only:
        queries = [q for q in queries if q.name.startswith(args.only)]
    if not queries:
        log.error("No hay consultas para medir")
        return 1

    plans_dir = args.out_dir / "plans" / args.label
    results = []
    with psycopg.connect(conninfo_from_env(), autocommit=True) as conn:
        version = conn.execute("select version()").fetchone()[0].split(" on ")[0]
        settings = {name: conn.execute(f"show {name}").fetchone()[0] for name in SETTINGS}
        started = time.monotonic()
        without_stats = wait_for_stats(conn, args.stats_timeout)
        stats_wait_s = round(time.monotonic() - started)
        if without_stats:
            log.warning("Se mide sin estadísticas en: %s", ", ".join(without_stats))
        for query in queries:
            result = measure(conn, query, args.runs, plans_dir)
            log.info("%-40s %10s ms", query.name, fmt_ms(result.median_ms))
            results.append(result)

    report = {
        "label": args.label,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "version": version,
        "runs": args.runs,
        "settings": settings,
        "stats_wait_s": stats_wait_s,
        "without_stats": without_stats,
        "queries": [asdict(r) for r in results],
    }
    if args.dbt_results:
        report["dbt"] = dbt_timings(args.dbt_results)

    results_dir = args.out_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / f"{args.label}.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    output = args.out_dir / f"{args.label}.md"
    output.write_text(render_report(report, baseline), encoding="utf-8")
    log.info("Reporte escrito en %s (planes en %s)", output, plans_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
