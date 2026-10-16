<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/fudo-logo-white.svg">
    <img src="assets/fudo-logo-black.svg" alt="Fudo" width="120">
  </picture>
</p>

# Diccionario de datos

Cada columna de cada archivo de entrada: cómo se llama en el origen, en **bronze** y en **silver**, su tipo, un ejemplo y la regla de limpieza. Los números de calidad salen de [profiling/profile.md](profiling/profile.md) y las reglas están definidas en [spec.md](../specs/spec.md) (FR-04 a FR-08).

## Convenciones

| Capa | Nombres | Tipos |
|---|---|---|
| **Origen** | Tal cual el CSV (con espacios, tildes y mayúsculas). | Texto. |
| **bronze** | Nombre original normalizado a snake_case ASCII (FR-01b): minúsculas, sin tildes, todo lo que no sea letra o número pasa a `_`. `ID Cliente` → `id_cliente`, `género` → `genero`. | Todo `text`. Más `_source_file`, `_row_number`, `_loaded_at`. |
| **silver** | Inglés, snake_case, nombres de negocio (`user_id`, `started_at`). | Tipados. Las filas que no pasan las reglas van a `<entidad>_rejected` con `reject_reason`. |

- **IDs**: se quita el sufijo `BAEcobici` y el `.0` de los decimales, y se pasan a entero (`146BAEcobici` → `146`, `1.0` → `1`).
- **Números con separador de miles**: se quita la coma antes de convertir (`"3,108"` → `3108`).
- **Fechas y horas**: `timestamp` sin zona horaria, en hora local de Buenos Aires, como vienen en el origen.
- **Textos**: `trim`; un texto vacío pasa a `NULL`.
- **Coordenadas**: `numeric` en WGS84 más un punto PostGIS `geometry(Point, 4326)`. Una coordenada fuera de la caja de CABA (lat [-34,75, -34,50], lon [-58,55, -58,30]) se trata como faltante.

---

## 🚲 Viajes 2025

`data/raw/ecobici-datasets-2025.csv` → `bronze.trips` → `silver.trips`. 3.156.182 filas, 1 por viaje: **3.155.783 válidos** en `silver.trips` y **399 rechazados** en `silver.trips_rejected` (398 `duration_over_24h` y 1 `missing_station`). Las reglas se evalúan en el orden de la tabla y el rechazo informa la primera que falla.

En 8 viajes `ended_at` es igual a `started_at` aunque la duración es de varios minutos: se conservan, la duración informada es la medida de referencia, y un test de nivel warn los deja visibles.

| Origen | Bronze | Silver | Tipo silver | Ejemplo | Regla |
|---|---|---|---|---|---|
| `Id_recorrido` | `id_recorrido` | `trip_id` | `bigint` PK | `27699090BAEcobici` → `27699090` | Quitar sufijo. Único (0 duplicados). |
| `duracion_recorrido` | `duracion_recorrido` | `duration_seconds` | `integer` | `"3,108"` → `3108` | Quitar separador de miles (48 % de las filas). ≤ 0 → rechazado `non_positive_duration` (0); > 86.400 → rechazado `duration_over_24h` (398). |
| `fecha_origen_recorrido` | `fecha_origen_recorrido` | `started_at` | `timestamp` | `2025-10-15 11:12:52` | Fuera de 2025 → rechazado `out_of_period` (0). |
| `id_estacion_origen` | `id_estacion_origen` | `origin_station_id` | `integer` FK | `146BAEcobici` → `146` | Quitar sufijo. Vacío → rechazado `missing_station` (0). |
| `nombre_estacion_origen` | `nombre_estacion_origen` | — | — | `146 - Hospital Francés` | No pasa a `silver.trips`: los atributos de la estación salen de `silver.stations`. Se usa solo para completar las 6 estaciones que no están en el catálogo (FR-05). 18 vacíos. |
| `direccion_estacion_origen` | `direccion_estacion_origen` | — | — | `3024 Calvo, Carlos` | Igual que el nombre. |
| `long_estacion_origen` | `long_estacion_origen` | — | — | `-58.4078419` | Igual que el nombre. 18 vacíos. |
| `lat_estacion_origen` | `lat_estacion_origen` | — | — | `-34.6221118` | Igual que el nombre. 18 vacíos. |
| `fecha_destino_recorrido` | `fecha_destino_recorrido` | `ended_at` | `timestamp` | `2025-10-15 11:26:12` | Anterior a `started_at` → rechazado `destination_before_origin` (0). Puede caer en 2026 (viajes que terminan después del 31/12). |
| `id_estacion_destino` | `id_estacion_destino` | `destination_station_id` | `integer` FK | `17BAEcobici` → `17` | Quitar sufijo. Vacío → rechazado `missing_station` (1). |
| `nombre_estacion_destino` | `nombre_estacion_destino` | — | — | `017 - Plaza Almagro` | Como en origen. 29 vacíos. |
| `direccion_estacion_destino` | `direccion_estacion_destino` | — | — | `441 Bulnes & Peron, Juan Domingo` | Como en origen. 177 vacíos. |
| `long_estacion_destino` | `long_estacion_destino` | — | — | `-58.4187306` | Como en origen. 29 vacíos; 176 en `0` (fuera de CABA → faltante): son todos de la estación 510 "[Valet] Galpón". |
| `lat_estacion_destino` | `lat_estacion_destino` | — | — | `-34.6064101` | Como en origen. 29 vacíos; 176 en `0`. |
| `id_usuario` | `id_usuario` | `user_id` | `integer` FK | `1177390BAEcobici` → `1177390` | Quitar sufijo. El 51 % no tiene perfil en los archivos de usuarios: se conserva igual (ver `dim_user.has_profile`). |
| `modelo_bicicleta` | `modelo_bicicleta` | `bike_model` | `text` | `ICONIC` | Valores aceptados: `FIT`, `ICONIC`. |
| `género` | `genero` | `gender` | `text` | `FEMALE` | Valores aceptados: `MALE`, `FEMALE`, `OTHER`; vacío → `NULL` (8.601). |
| — | — | `is_round_trip` | `boolean` | `true` | Derivada: `origin_station_id = destination_station_id` (275.733 viajes, se conservan). |

## 👤 Usuarios

Dos archivos con esquemas distintos que se cargan por separado en bronze (FR-01c) y se unen en `silver.users` (389.751 usuarios). Además de las columnas de las tablas de abajo, `silver.users` tiene `signup_date` (fecha de `signed_up_at`) y `source_file`.

Una fila va a `silver.users_rejected` con su `reject_reason` si: el ID no es un entero (`invalid_user_id`), la fecha y hora de alta no tienen el formato esperado (`invalid_signup_date`), o el ID ya apareció con un alta más antigua (`duplicate_user_id`). Hoy no hay ninguna.

### Altas 2025

`data/raw/usuarios-ecobici-2025.csv` → `bronze.users_2025`. 192.674 filas.

| Origen | Bronze | Silver | Tipo silver | Ejemplo | Regla |
|---|---|---|---|---|---|
| `ID Cliente` | `id_cliente` | `user_id` | `integer` PK | `1473152` | Único (0 duplicados) y sin solapamiento con 2024. |
| `genero_usuario` | `genero_usuario` | `gender` | `text` | `OTHER` | Valores aceptados: `MALE`, `FEMALE`, `OTHER`. |
| `edad_usuario` | `edad_usuario` | `age` | `smallint` | `27` | Quitar separador de miles y convertir; fuera de [15, 100] → `NULL`, el usuario se conserva. 100 casos: de -41 a 2.025, 17 con separador (`"2,024"`, son años). |
| `fecha_alta` | `fecha_alta` | `signed_up_at` | `timestamp` | `2025-12-31` | Se combina con `hora_alta`. Todas en 2025. |
| `hora_alta` | `hora_alta` | (en `signed_up_at`) | — | `12:39:34` | `fecha_alta + hora_alta` → `2025-12-31 12:39:34`. |
| `Customer Has Dni (Yes / No)` | `customer_has_dni_yes_no` | `has_dni` | `boolean` | `No` → `false` | `Yes` → `true`, `No` → `false`. |
| — | — | `signup_year` | `smallint` | `2025` | Derivada del archivo de origen. |

### Altas 2024

`data/raw/usuarios-ecobici-2024.csv` (UTF-8 con BOM) → `bronze.users_2024`. 197.077 filas.

| Origen | Bronze | Silver | Tipo silver | Ejemplo | Regla |
|---|---|---|---|---|---|
| `id_usuario` | `id_usuario` | `user_id` | `integer` PK | `1094487` | Único (0 duplicados). |
| `genero_usuario` | `genero_usuario` | `gender` | `text` | `OTHER` | Como en 2025. |
| `edad_usuario` | `edad_usuario` | `age` | `smallint` | `35` | Como en 2025. 76 fuera de rango (de 4 a 2.021). |
| `fecha_alta` | `fecha_alta` | `signed_up_at` | `timestamp` | `2024-01-18` | Como en 2025. Todas en 2024. |
| `hora_alta` | `hora_alta` | (en `signed_up_at`) | — | `09:21:02` | Como en 2025. |
| — | — | `has_dni` | `boolean` | `NULL` | El archivo 2024 no trae la columna. |
| — | — | `signup_year` | `smallint` | `2024` | Derivada del archivo de origen. |

## 📍 Estaciones (sistema actual)

`data/raw/estaciones.csv` (UTF-8 con BOM) → `bronze.stations` → `silver.stations`. 407 filas, más 6 estaciones que solo aparecen en los viajes (FR-05): 413 en silver. Las comunas quedan: 411 por polígono, 1 por cercanía (AEROPARQUE → 14) y 1 sin ubicación (510).

| Origen | Bronze | Silver | Tipo silver | Ejemplo | Regla |
|---|---|---|---|---|---|
| `id` | `id` | `station_id` | `integer` PK | `240` | Clave de cruce con los viajes (99,8 % de cobertura). |
| `numero_de_estacion` | `numero_de_estacion` | `station_number` | `integer` | `239` | Número público de la estación. **No es clave**: 9 repetidos. |
| `nombre` | `nombre` | `station_name` | `text` | `VIDAL` | Nombre de referencia de la estación (FR-07: gana sobre los nombres de los viajes). |
| `direccion` | `direccion` | `address` | `text` | `Av. Cramer 2900` | `trim`. |
| `barrio` | `barrio` | — | — | (vacío) | Vacío en las 407 filas: se descarta. |
| `comuna` | `comuna` | — | — | (vacío) | Vacío en las 407 filas: se calcula (ver `comuna` abajo). |
| `emplazamiento` | `emplazamiento` | — | — | (vacío) | Vacío en las 407 filas: se descarta. |
| `latitud` | `latitud` | `latitude` | `numeric` | `-34.558137` | Dentro de CABA en las 407 filas. |
| `longitud` | `longitud` | `longitude` | `numeric` | `-58.467259` | Dentro de CABA en las 407 filas. |
| — | — | `geom` | `geometry(Point, 4326)` | — | `ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)`, índice GiST. |
| — | — | `comuna` | `smallint` | `13` | `ST_Contains` contra `silver.comunas`; si no cae en ninguna, la más cercana (FR-05c). |
| — | — | `comuna_assignment` | `text` | `contains` | `contains`; `nearest` (solo AEROPARQUE, id 541, asignada a la comuna 14); `unknown` si no tiene coordenadas válidas (solo la 510 "[Valet] Galpón", con comuna `NULL`). |
| — | — | `source` | `text` | `catalog` | `catalog` para las 407 del archivo; `trips` para las 6 completadas desde los viajes (591, 448, 593, 443, 510, 594). |

## 📍 Estaciones (sistema viejo)

`data/raw/estaciones-sistema-viejo.csv` → `bronze.stations_legacy`. 204 filas. **Solo bronze**: no pasa a silver porque 26 de sus 135 IDs compartidos con el catálogo actual son de otra estación (FR-05b).

| Origen | Bronze | Ejemplo | Calidad |
|---|---|---|---|
| `id_estacion` | `id_estacion` | `1.0` | 4 vacíos, 1 repetido. |
| `nombre_estacion` | `nombre_estacion` | `Facultad de Derecho` | Completo. |
| `long_estacion` | `long_estacion` | `-58.392452` | 6 vacíos. |
| `lat_estacion` | `lat_estacion` | `-34.583133` | 6 vacíos. |
| `domicilio_estacion` | `domicilio_estacion` | `Av. Pres.Figueroa Alcorta y Juan A.Bibiloni` | 6 vacíos. |
| `tipo_estacion` | `tipo_estacion` | `AUTOMÁTICA` | Único valor; 11 vacíos. |
| `observaciones` | `observaciones` | `Abril 2015 (pasó de ser Manual a Automática)` | 11 vacíos. |
| `horario_estacion` | `horario_estacion` | `Estación automática: disponibilidad las 24 horas` | Único valor; 11 vacíos. |

## 🗺️ Comunas

`data/reference/comunas.geojson` (CRS84 = WGS84 lon/lat) → `bronze.comunas` (1 fila por polígono, geometría como GeoJSON en `text`) → `silver.comunas`. 15 filas.

| Origen (`properties`) | Bronze | Silver | Tipo silver | Ejemplo | Regla |
|---|---|---|---|---|---|
| `id` | `id` | — | — | `1` | Igual a `comuna`: se descarta. |
| `objeto` | `objeto` | — | — | `COMUNA` | Valor constante: se descarta. |
| `comuna` | `comuna` | `comuna` | `smallint` PK | `1` | De 1 a 15. |
| `barrios` | `barrios` | `barrios` | `text` | `Constitucion, Monserrat, Retiro, ...` | Lista de barrios de la comuna, solo descriptiva (no hay polígonos por barrio). |
| `perimetro` | `perimetro` | `perimeter_m` | `numeric` | `36011.96` | En metros. |
| `area` | `area` | `area_m2` | `numeric` | `17784744.41` | En metros cuadrados. |
| `geometry` | `geometry` | `geom` | `geometry(MultiPolygon, 4326)` | — | `ST_Multi(ST_GeomFromGeoJSON(...))`: 14 vienen como `Polygon` y 1 como `MultiPolygon`. Índice GiST. |
