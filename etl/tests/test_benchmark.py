from pathlib import Path

from benchmark.benchmark import (
    dbt_timings,
    fmt_ms,
    load_queries,
    render_report,
    speedup,
    split_statements,
    summarize_plan,
)

REPO = Path(__file__).resolve().parents[2]


def test_split_ignores_semicolon_in_comment_and_numbers_unnamed():
    text = """-- Q6: ranking; desempata la duración.
select 1;

-- 2. Resumen.
select
    2;
"""
    queries = split_statements(text, "q6")
    assert [q.name for q in queries] == ["q6_1", "q6_2"]
    assert queries[0].title == "Q6: ranking; desempata la duración."
    assert queries[0].sql == "select 1"
    assert queries[1].sql == "select\n    2"


def test_split_single_statement_keeps_stem_and_uses_name_comment():
    assert [q.name for q in split_statements("-- Q1\nselect 1;\n", "q1")] == ["q1"]
    queries = split_statements("-- name: d1_top\n-- Top 20.\nselect 1;\n", "dashboard")
    assert queries[0].name == "d1_top"
    assert queries[0].title == "Top 20."


def test_split_drops_trailing_comment_only_chunk():
    assert len(split_statements("select 1;\n-- fin\n", "q")) == 1


def test_repo_queries_have_unique_names():
    queries = load_queries(REPO, ("sql/analysis/*.sql", "sql/optimization/dashboard.sql"))
    names = [q.name for q in queries]
    assert len(names) == len(set(names))
    assert {"q1_comunas_origen", "q5_duracion_vs_modelo_2", "d1_top_od_month"} <= set(names)


def test_summarize_plan_collects_scans_buffers_and_workers():
    plan = {
        "Execution Time": 12.5,
        "Planning Time": 0.4,
        "Plan": {
            "Node Type": "Gather",
            "Workers Launched": 2,
            "Shared Hit Blocks": 128,
            "Shared Read Blocks": 256,
            "Temp Written Blocks": 0,
            "Plans": [
                {"Node Type": "Seq Scan", "Relation Name": "fct_trips"},
                {
                    "Node Type": "Hash",
                    "Plans": [{"Node Type": "Index Scan", "Relation Name": "dim_station"}],
                },
                {"Node Type": "Seq Scan", "Relation Name": "fct_trips"},
            ],
        },
    }
    summary = summarize_plan(plan)
    assert summary["execution_ms"] == 12.5
    assert summary["workers"] == 2
    assert summary["shared_hit_mb"] == 1.0
    assert summary["shared_read_mb"] == 2.0
    assert summary["scans"] == ["Seq Scan fct_trips", "Index Scan dim_station"]


def test_formatting():
    assert fmt_ms(1234.4) == "1.234"
    assert fmt_ms(12.34) == "12,3"
    assert speedup(1000, 250) == "4,0×"
    assert speedup(100, 200) == "0,50× (peor)"


def test_dbt_timings_keeps_only_models(tmp_path):
    path = tmp_path / "run_results.json"
    path.write_text(
        '{"elapsed_time": 70.5, "results": ['
        '{"unique_id": "model.ecobici.trips", "execution_time": 28.6},'
        '{"unique_id": "test.ecobici.not_null_x", "execution_time": 1.0}]}'
    )
    assert dbt_timings(path) == {"elapsed_s": 70.5, "models": {"trips": 28.6}}


def report(label, ms, dbt_s):
    return {
        "label": label,
        "date": "2026-10-16 10:00",
        "version": "PostgreSQL 16.10",
        "runs": 3,
        "settings": {"work_mem": "4MB"},
        "queries": [
            {
                "name": "q1",
                "title": "Q1",
                "source": "sql/analysis/q1.sql",
                "runs_ms": ms,
                "planning_ms": 0.1,
                "shared_hit_mb": 1.0,
                "shared_read_mb": 0.0,
                "temp_written_mb": 0.0,
                "workers": 2,
                "scans": ["Seq Scan fct_trips"],
            }
        ],
        "dbt": {"elapsed_s": dbt_s, "models": {"trips": dbt_s, "tiny": 0.2}},
    }


def test_render_report_with_and_without_baseline():
    baseline = report("baseline", [900.0, 1000.0, 1100.0], 70.0)
    text = render_report(baseline, None)
    assert "| `q1` | 1.000 | 900–1.100 |" in text
    assert "| `trips` | 70,0 |" in text
    assert "tiny" not in text

    compared = render_report(report("after", [200.0, 250.0, 300.0], 35.0), baseline)
    assert "| `q1` | 1.000 | 250 | 4,0× |" in compared
    assert "70,0 s → 35,0 s" in compared
