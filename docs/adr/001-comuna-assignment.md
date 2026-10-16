# ADR 001: Asignar la comuna de cada estación con PostGIS

- **Estado:** Aceptado
- **Fecha:** 2026-10-15
- **Requerimientos:** FR-05c, Q1, Q2

## Contexto

Dos de las preguntas del challenge piden agrupar por comuna: de qué comunas salen más viajes (Q1) y a cuáles llegan más (Q2). Ningún dataset trae ese dato:

- `estaciones.csv` tiene las columnas `barrio` y `comuna`, pero están vacías en las 407 filas.
- `Trips.csv` solo trae latitud y longitud de cada estación.

Lo que sí hay son coordenadas WGS84 en todas las estaciones del catálogo actual, y el portal de la Ciudad publica los polígonos oficiales de las 15 comunas en GeoJSON.

## Decisión

Calcular la comuna con un cruce espacial dentro de la base:

1. Versionar el GeoJSON oficial en `data/reference/comunas.geojson`, con su fuente y su SHA-256 en `spec.md`.
2. Usar una imagen de PostgreSQL 16 con PostGIS y cargar los polígonos en `silver.comunas` como `geometry(MultiPolygon, 4326)` con índice GiST.
3. En `silver.stations`, asignar la comuna con `ST_Contains(comuna.geom, station.geom)`.
4. Si una estación no cae dentro de ningún polígono, asignarle la comuna más cercana (`ST_Distance`) y marcarla con `comuna_assignment = 'nearest'`.

El profiling ([profile.md](../profiling/profile.md)) muestra que 406 de las 407 estaciones caen dentro de un polígono. La que no es AEROPARQUE (id 541): está sobre la costa del río, fuera del límite del polígono. Se espera que la más cercana sea la Comuna 14 (Palermo), a la que pertenece; se verifica con un test en T4.2.

## Alternativas consideradas

| Alternativa | Por qué se descartó |
|---|---|
| Cruce espacial en Python (shapely) durante la ingesta | Pone lógica de negocio en la capa bronze, que tiene que ser una copia fiel del origen. La transformación queda fuera de dbt: sin tests ni lineage. |
| Seed manual estación → comuna | Habría que mantenerlo a mano para 413 estaciones, se rompe si aparece una nueva y no hay forma de justificar cada asignación. |
| Descargar el GeoJSON en cada corrida | El pipeline dependería de internet y del portal; si el archivo cambia, los resultados dejan de ser reproducibles. |
| Postgres sin PostGIS, con un punto en polígono escrito en SQL | Reimplementa a mano algo que PostGIS resuelve, indexado y probado. |

## Consecuencias

- La base pasa a ser PostgreSQL con la extensión PostGIS (se crea en `sql/init`).
- Las geometrías quedan disponibles en gold: Metabase puede mostrar mapas de estaciones y comunas.
- `comuna_assignment` deja explícita la única asignación aproximada. Un test de dbt verifica que todas las estaciones tengan comuna.
- No se asigna barrio: el GeoJSON solo lista los barrios de cada comuna, sin sus polígonos. Si hiciera falta, se agrega el GeoJSON de barrios con el mismo mecanismo.

## Notas

- **2026-10-15 (T2.1):** la imagen oficial `postgis/postgis` solo se publica para amd64. Se usa `imresamu/postgis:16-3.5.3-bookworm`, la variante multi-arquitectura que mantiene un colaborador del proyecto postgis-docker, para que corra nativa también en arm64 (Apple Silicon). No cambia la decisión.
