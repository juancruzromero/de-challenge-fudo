<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/fudo-logo-white.svg">
  <img src="docs/assets/fudo-logo-black.svg" alt="Fudo" width="160">
</picture>
</div>

# FUDO Data Engineer Challenge (🚲 Ecobici BA 2025)

Pipeline de datos de punta a punta sobre los viajes del sistema de bicicletas públicas de Buenos Aires durante 2025:
ingesta, limpieza, modelo relacional, consultas analíticas y dashboard.

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)
![PostGIS](https://img.shields.io/badge/PostGIS-3-5CAE58?logo=postgresql&logoColor=white)
![dbt](https://img.shields.io/badge/dbt-core-FF694B?logo=dbt&logoColor=white)
![Metabase](https://img.shields.io/badge/Metabase-BI-509EE3?logo=metabase&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![Status](https://img.shields.io/badge/estado-en%20construcción-orange)

---

## 🏗️ Arquitectura

Arquitectura **medallion** sobre PostgreSQL:

```
data/raw/*.csv ──► 🥉 bronze ──► 🥈 silver ──► 🥇 gold ──► 📊 Metabase
                   crudo, TEXT   tipado, limpio   modelo estrella
                   (Python COPY)  (dbt)           + agregados (dbt)
```

| Capa | Qué tiene |
|---|---|
| 🥉 **bronze** | Los CSV tal cual llegan, con metadatos de carga. Inmutable y reproducible. |
| 🥈 **silver** | Datos tipados, normalizados y deduplicados. Las filas descartadas quedan en tablas `*_rejected` con el motivo. |
| 🥇 **gold** | Modelo estrella (`fct_trips` + dimensiones), agregados origen→destino y marts para cada pregunta del challenge. |

## 🚀 Quickstart

> 🚧 En construcción: `make up` ya levanta la base (PostgreSQL + PostGIS), carga los datasets en bronze y levanta Metabase. Las capas silver/gold y el dashboard llegan en las próximas fases del [plan](specs/tasks.md).

**Requisitos:** Docker y Docker Compose. Para desarrollo local, además [uv](https://docs.astral.sh/uv/).

```bash
# 1. Descargar los datasets en data/raw/ (ver tabla de abajo)
# 2. Levantar todo (crea .env desde .env.example si no existe)
make up
# 3. Abrir el dashboard
open http://localhost:3000
```

`make help` lista todos los comandos:

| Comando | Qué hace |
|---|---|
| `make up` / `make down` | Levanta / detiene el stack |
| `make reset` | Borra los datos y levanta desde cero |
| `make ps` · `make logs` | Estado y logs de los servicios |
| `make psql` | Consola SQL en la base analítica |
| `make etl` · `make dbt` | Corre el pipeline / un comando de dbt |
| `make sql` | Corre las consultas de análisis |
| `make setup` · `make test` · `make lint` | Entorno local, tests y linters |
| `make profile` | Regenera el reporte de profiling de los datasets |

## 📦 Datasets

Fuente: [Buenos Aires Data](https://data.buenosaires.gob.ar). Descargar cada archivo en `data/raw/` con el nombre indicado:

| | Dataset | Archivo esperado | Descarga |
|---|---|---|---|
| 🚲 | Recorridos 2025 | `ecobici-datasets-2025.csv` | [⬇️ zip](https://data.buenosaires.gob.ar/dataset/bicicletas-publicas/resource/d860362d-99f9-49a2-9ea0-1afd65581a97/download) (descomprimir `Trips.csv` y renombrar) |
| 👤 | Usuarios 2025 | `usuarios-ecobici-2025.csv` | [⬇️ csv](https://data.buenosaires.gob.ar/dataset/bicicletas-publicas/resource/f522cefa-d113-4871-bb0f-559ccfdbd639/download) |
| 👤 | Usuarios 2024 | `usuarios-ecobici-2024.csv` | [⬇️ csv](https://data.buenosaires.gob.ar/dataset/bicicletas-publicas/resource/b7ee1b17-3f70-4dbd-877b-7abc5e3ba7d4/download) |
| 📍 | Estaciones (sistema actual) | `estaciones.csv` | [⬇️ csv](https://data.buenosaires.gob.ar/dataset/estaciones-bicicletas-publicas/resource/1d21a28a-bb2b-4ddb-b00b-77f82f3e34fb/download) |
| 📍 | Estaciones (sistema inicial) | `estaciones-sistema-viejo.csv` | [⬇️ csv](https://data.buenosaires.gob.ar/dataset/estaciones-bicicletas-publicas/resource/juqdkmgo-1011-resource/download) |
| 🗺️ | Comunas (polígonos) | `data/reference/comunas.geojson` | ✅ ya incluido en el repo ([fuente](https://cdn.buenosaires.gob.ar/datosabiertos/datasets/ministerio-de-educacion/comunas/comunas.geojson)) |

> ℹ️ `data/raw/` no se versiona. `data/reference/` sí: son datos auxiliares chicos que el pipeline necesita para funcionar sin internet.

## ❓ Preguntas que responder

| | Pregunta |
|---|---|
| 🏙️ | Comunas de las que más viajes parten |
| 🎯 | Comunas que más viajes reciben |
| 🎂 | Relación entre la edad de los usuarios y la cantidad de viajes |
| 📅 | Relación entre la cantidad de viajes y la fecha de alta de los usuarios |
| ⏱️ | Relación entre la duración de los viajes y el modelo de bicicleta |
| 🏆 | Usuarios más activos durante 2025 |

## 📁 Estructura

```
specs/          📋 plan, especificación y tareas (SDD)
etl/            🐍 ingesta a bronze (Python)
dbt/            🔧 transformaciones silver y gold
sql/            🗄️ init de la base, consultas de análisis y optimización
metabase/       📊 provisión automática del dashboard
docs/           📚 diccionario de datos, decisiones (ADRs) y diagrama ER
data/raw/       📥 datasets de entrada (no versionado)
data/reference/ 🗺️ datos auxiliares versionados
```

## 📋 Documentación del proyecto

El proyecto se desarrolla con **Spec-Driven Development**:

- 🧭 [plan.md](specs/plan.md): stack, arquitectura y decisiones técnicas.
- 📐 [spec.md](specs/spec.md): requerimientos, reglas de calidad de datos y criterios de aceptación.
- ✅ [tasks.md](specs/tasks.md): tareas por fase y su estado.
- 📝 [CHALLENGUE.md](CHALLENGUE.md): enunciado original.
