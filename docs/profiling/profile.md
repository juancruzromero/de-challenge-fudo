# Profiling de datasets

> Generado por `uv run --project etl ecobici-profile`. No editar a mano: volver a correr el script.

| Dataset | Archivo | Filas |
|---|---|---|
| Viajes 2025 | `ecobici-datasets-2025.csv` | 3.156.182 |
| Usuarios con alta en 2025 | `usuarios-ecobici-2025.csv` | 192.674 |
| Usuarios con alta en 2024 | `usuarios-ecobici-2024.csv` | 197.077 |
| Estaciones (sistema actual) | `estaciones.csv` | 407 |
| Estaciones (sistema viejo) | `estaciones-sistema-viejo.csv` | 204 |

## Viajes 2025 — `ecobici-datasets-2025.csv`

| Filas | Columnas | Tamaño | Encoding | Delimitador | Tiempo |
|---|---|---|---|---|---|
| 3.156.182 | 17 | 832,4 MB | UTF-8 sin BOM | `,` | 43,2 s |

### Columnas

| Columna | Vacíos | Distintos | Ejemplo |
|---|---|---|---|
| `Id_recorrido` | 0 | > 1.000 | 27699090BAEcobici |
| `duracion_recorrido` | 0 | > 1.000 | 800 |
| `fecha_origen_recorrido` | 0 | > 1.000 | 2025-10-15 11:12:52 |
| `id_estacion_origen` | 0 | 403 | 146BAEcobici |
| `nombre_estacion_origen` | 18 | 404 | 146 - Hospital Francés |
| `direccion_estacion_origen` | 0 | 400 | 3024 Calvo, Carlos |
| `long_estacion_origen` | 18 | 427 | -58.40784190000001 |
| `lat_estacion_origen` | 18 | 427 | -34.6221118 |
| `fecha_destino_recorrido` | 0 | > 1.000 | 2025-10-15 11:26:12 |
| `id_estacion_destino` | 1 | 404 | 17BAEcobici |
| `nombre_estacion_destino` | 29 | 405 | 017 - Plaza Almagro |
| `direccion_estacion_destino` | 177 | 400 | 441 Bulnes & Peron, Juan Domingo, Tte... |
| `long_estacion_destino` | 29 | 428 | -58.4187306 |
| `lat_estacion_destino` | 29 | 428 | -34.6064101 |
| `id_usuario` | 0 | > 1.000 | 1177390BAEcobici |
| `modelo_bicicleta` | 0 | 2 | ICONIC |
| `género` | 8.601 | 3 | FEMALE |

### Duplicados

| Columna | Valores repetidos |
|---|---|
| `Id_recorrido` | 0 |

### Numéricas

| Columna | Mín | Máx | Con separador de miles | No numéricos | Rango esperado | Debajo | Encima |
|---|---|---|---|---|---|---|---|
| `duracion_recorrido` | 61 | 2.481.476 | 1.526.481 | 0 | [1, 86.400] | 0 | 398 |
| `lat_estacion_origen` | -34.687767 | -34.536691 | 0 | 0 | [-34.75, -34.5] | 0 | 0 |
| `long_estacion_origen` | -58.527098 | -58.355465 | 0 | 0 | [-58.55, -58.3] | 0 | 0 |
| `lat_estacion_destino` | -34.687767 | 0 | 0 | 0 | [-34.75, -34.5] | 0 | 176 |
| `long_estacion_destino` | -58.527098 | 0 | 0 | 0 | [-58.55, -58.3] | 0 | 176 |

### Fechas

| Columna | Mín | Máx | No parseables | Año esperado | Fuera del año |
|---|---|---|---|---|---|
| `fecha_origen_recorrido` | 2025-01-01 00:01:40 | 2025-12-31 23:58:28 | 0 | 2025 | 0 |
| `fecha_destino_recorrido` | 2025-01-01 00:11:09 | 2026-01-09 12:34:47 | 0 | — | 0 |

Registros por mes (`fecha_origen_recorrido`):

| Mes | Registros |
|---|---|
| 2025-01 | 301.248 |
| 2025-02 | 260.340 |
| 2025-03 | 288.796 |
| 2025-04 | 297.754 |
| 2025-05 | 230.404 |
| 2025-06 | 150.753 |
| 2025-07 | 177.440 |
| 2025-08 | 227.801 |
| 2025-09 | 289.102 |
| 2025-10 | 344.320 |
| 2025-11 | 308.389 |
| 2025-12 | 279.835 |

### Categóricas

`modelo_bicicleta`:

| Valor | Filas | % |
|---|---|---|
| FIT | 2.139.336 | 67,8 % |
| ICONIC | 1.016.846 | 32,2 % |

`género`:

| Valor | Filas | % |
|---|---|---|
| MALE | 1.944.994 | 61,6 % |
| FEMALE | 1.020.532 | 32,3 % |
| OTHER | 182.055 | 5,8 % |
| (vacío) | 8.601 | 0,3 % |


### Chequeos

| Chequeo | Casos |
|---|---|
| misma estación de origen y destino | 275.733 |
| fecha de destino anterior a la de origen | 0 |
| IDs de estación con más de un nombre | 2 (307, 449) |

## Usuarios con alta en 2025 — `usuarios-ecobici-2025.csv`

| Filas | Columnas | Tamaño | Encoding | Delimitador | Tiempo |
|---|---|---|---|---|---|
| 192.674 | 6 | 8,1 MB | UTF-8 sin BOM | `,` | 0,9 s |

### Columnas

| Columna | Vacíos | Distintos | Ejemplo |
|---|---|---|---|
| `ID Cliente` | 0 | > 1.000 | 1473152 |
| `genero_usuario` | 0 | 3 | OTHER |
| `edad_usuario` | 0 | 148 | 27 |
| `fecha_alta` | 0 | 365 | 2025-12-31 |
| `hora_alta` | 0 | > 1.000 | 12:39:34 |
| `Customer Has Dni (Yes / No)` | 0 | 2 | No |

### Duplicados

| Columna | Valores repetidos |
|---|---|
| `ID Cliente` | 0 |

### Numéricas

| Columna | Mín | Máx | Con separador de miles | No numéricos | Rango esperado | Debajo | Encima |
|---|---|---|---|---|---|---|---|
| `edad_usuario` | -41 | 2.025 | 17 | 0 | [15, 100] | 5 | 95 |

### Fechas

| Columna | Mín | Máx | No parseables | Año esperado | Fuera del año |
|---|---|---|---|---|---|
| `fecha_alta` | 2025-01-01 00:00:00 | 2025-12-31 00:00:00 | 0 | 2025 | 0 |

Registros por mes (`fecha_alta`):

| Mes | Registros |
|---|---|
| 2025-01 | 22.896 |
| 2025-02 | 14.571 |
| 2025-03 | 16.378 |
| 2025-04 | 16.294 |
| 2025-05 | 13.696 |
| 2025-06 | 9.340 |
| 2025-07 | 14.260 |
| 2025-08 | 14.728 |
| 2025-09 | 16.166 |
| 2025-10 | 18.877 |
| 2025-11 | 19.499 |
| 2025-12 | 15.969 |

### Categóricas

`genero_usuario`:

| Valor | Filas | % |
|---|---|---|
| MALE | 88.966 | 46,2 % |
| FEMALE | 81.724 | 42,4 % |
| OTHER | 21.984 | 11,4 % |

`Customer Has Dni (Yes / No)`:

| Valor | Filas | % |
|---|---|---|
| Yes | 168.124 | 87,3 % |
| No | 24.550 | 12,7 % |

## Usuarios con alta en 2024 — `usuarios-ecobici-2024.csv`

| Filas | Columnas | Tamaño | Encoding | Delimitador | Tiempo |
|---|---|---|---|---|---|
| 197.077 | 5 | 7,3 MB | UTF-8 con BOM | `,` | 0,9 s |

### Columnas

| Columna | Vacíos | Distintos | Ejemplo |
|---|---|---|---|
| `id_usuario` | 0 | > 1.000 | 1094487 |
| `genero_usuario` | 0 | 3 | OTHER |
| `edad_usuario` | 0 | 134 | 35 |
| `fecha_alta` | 0 | 366 | 2024-01-18 |
| `hora_alta` | 0 | > 1.000 | 09:21:02 |

### Duplicados

| Columna | Valores repetidos |
|---|---|
| `id_usuario` | 0 |

### Numéricas

| Columna | Mín | Máx | Con separador de miles | No numéricos | Rango esperado | Debajo | Encima |
|---|---|---|---|---|---|---|---|
| `edad_usuario` | 4 | 2.021 | 0 | 0 | [15, 100] | 6 | 70 |

### Fechas

| Columna | Mín | Máx | No parseables | Año esperado | Fuera del año |
|---|---|---|---|---|---|
| `fecha_alta` | 2024-01-01 00:00:00 | 2024-12-31 00:00:00 | 0 | 2024 | 0 |

Registros por mes (`fecha_alta`):

| Mes | Registros |
|---|---|
| 2024-01 | 20.455 |
| 2024-02 | 16.179 |
| 2024-03 | 17.786 |
| 2024-04 | 12.848 |
| 2024-05 | 10.686 |
| 2024-06 | 10.976 |
| 2024-07 | 13.350 |
| 2024-08 | 12.924 |
| 2024-09 | 20.623 |
| 2024-10 | 21.973 |
| 2024-11 | 20.303 |
| 2024-12 | 18.974 |

### Categóricas

`genero_usuario`:

| Valor | Filas | % |
|---|---|---|
| MALE | 88.655 | 45,0 % |
| FEMALE | 79.310 | 40,2 % |
| OTHER | 29.112 | 14,8 % |

## Estaciones (sistema actual) — `estaciones.csv`

| Filas | Columnas | Tamaño | Encoding | Delimitador | Tiempo |
|---|---|---|---|---|---|
| 407 | 9 | 0,0 MB | UTF-8 con BOM | `,` | 0,0 s |

### Columnas

| Columna | Vacíos | Distintos | Ejemplo |
|---|---|---|---|
| `id` | 0 | 407 | 240 |
| `numero_de_estacion` | 0 | 398 | 239 |
| `nombre` | 0 | 406 | VIDAL |
| `direccion` | 0 | 403 | Av. Cramer 2900 |
| `barrio` | 407 | 0 |  |
| `comuna` | 407 | 0 |  |
| `emplazamiento` | 407 | 0 |  |
| `latitud` | 0 | 405 | -34.55813699999999 |
| `longitud` | 0 | 405 | -58.46725929999999 |

### Duplicados

| Columna | Valores repetidos |
|---|---|
| `id` | 0 |
| `numero_de_estacion` | 9 |

### Numéricas

| Columna | Mín | Máx | Con separador de miles | No numéricos | Rango esperado | Debajo | Encima |
|---|---|---|---|---|---|---|---|
| `latitud` | -34.687767 | -34.536691 | 0 | 0 | [-34.75, -34.5] | 0 | 0 |
| `longitud` | -58.527098 | -58.355465 | 0 | 0 | [-58.55, -58.3] | 0 | 0 |

## Estaciones (sistema viejo) — `estaciones-sistema-viejo.csv`

| Filas | Columnas | Tamaño | Encoding | Delimitador | Tiempo |
|---|---|---|---|---|---|
| 204 | 8 | 0,0 MB | UTF-8 sin BOM | `,` | 0,0 s |

### Columnas

| Columna | Vacíos | Distintos | Ejemplo |
|---|---|---|---|
| `id_estacion` | 4 | 199 | 1.0 |
| `nombre_estacion` | 0 | 204 | Facultad de Derecho |
| `long_estacion` | 6 | 198 | -58.392452073017 |
| `lat_estacion` | 6 | 198 | -34.5831330757635 |
| `domicilio_estacion` | 6 | 197 | Av. Pres.Figueroa Alcorta y  Juan A.B... |
| `tipo_estacion` | 11 | 1 | AUTOMÁTICA |
| `observaciones` | 11 | 35 | Abril 2015 (pasó de ser Manual a Auto... |
| `horario_estacion` | 11 | 1 | Estación automática: disponibilidad l... |

### Duplicados

| Columna | Valores repetidos |
|---|---|
| `id_estacion` | 1 |

### Numéricas

| Columna | Mín | Máx | Con separador de miles | No numéricos | Rango esperado | Debajo | Encima |
|---|---|---|---|---|---|---|---|
| `lat_estacion` | -34.641728 | -34.568074 | 0 | 0 | [-34.75, -34.5] | 0 | 0 |
| `long_estacion` | -58.455062 | -58.356257 | 0 | 0 | [-58.55, -58.3] | 0 | 0 |

### Categóricas

`tipo_estacion`:

| Valor | Filas | % |
|---|---|---|
| AUTOMÁTICA | 193 | 94,6 % |
| (vacío) | 11 | 5,4 % |

## Cruces entre datasets

### Viajes ↔ estaciones

| Catálogo | Estaciones de los viajes | Salidas y llegadas cubiertas | Faltantes |
|---|---|---|---|
| Catálogo actual (`estaciones.id`) | 398 / 404 | 6.301.685 (99,8 %) | 591 (4.441), 448 (2.736), 593 (2.571)... |
| Catálogo viejo (`id_estacion`) | 133 / 404 | 2.714.863 (43,0 %) | 516 (63.837), 289 (49.661), 202 (46.0... |

### Viajes ↔ usuarios

| Archivo de usuarios | Usuarios con viajes | Viajes cubiertos | Viajes/usuario |
|---|---|---|---|
| Altas 2025 | 140.533 / 286.322 | 860.741 (27,3 %) | 6,1 |
| Altas 2024 | 48.268 / 286.322 | 686.780 (21,8 %) | 14,2 |
| Altas 2024 + 2025 | 188.801 / 286.322 | 1.547.521 (49,0 %) | 8,2 |

### Catálogo viejo ↔ catálogo actual

IDs compartidos: **135**. En la misma ubicación (< 200 m): **109**. En otra ubicación: **26**.

| ID | Nombre en el viejo | Nombre en el actual | Distancia (m) |
|---|---|---|---|
| 176 | Pinzón | PARQUE SARMIENTO I | 15.068 |
| 61 | Ministerio de Economía | BENITO JUAREZ | 12.343 |
| 68 | Rivarola | PARQUE SAAVEDRA | 10.605 |
| 77 | Sarandí | ESTACION PUEYRREDON | 10.322 |
| 148 | Constitución II | PARQUE AVELLANEDA II | 9.834 |
| 134 | Don Bosco | SOLDADO DE LA FRONTERA | 9.315 |
| 187 | Parque Rivadavia | QUINTEROS LIDORO | 7.447 |
| 197 | Quintino Bocayuva | PLAZA CIUDAD DE UDINE | 6.419 |
| 59 | Coronel Díaz | INDEPENDENCIA | 4.161 |
| 188 | Aranguren | JORGELINA DE SIMONE | 4.133 |

### Estaciones ↔ comunas

Polígonos: **15**. Estaciones del catálogo actual dentro de una comuna: **406**. Fuera de todas: **1** (AEROPARQUE (541)).
