# ADR 002: Usar el catálogo de estaciones del sistema actual

- **Estado:** Aceptado
- **Fecha:** 2026-10-15
- **Requerimientos:** FR-05, FR-05b, FR-07

## Contexto

El portal publica dos catálogos de estaciones:

| Archivo | Filas | Origen |
|---|---|---|
| `estaciones.csv` | 407 | Sistema actual |
| `estaciones-sistema-viejo.csv` | 204 | Sistema inicial (IDs como `1.0`, observaciones de 2015) |

Los viajes de 2025 identifican cada estación con un ID con sufijo (`146BAEcobici`), y hay que elegir contra qué catálogo cruzarlo. El profiling ([profile.md](../profiling/profile.md)) dio:

| Catálogo | Estaciones de los viajes que cruzan | Salidas y llegadas cubiertas |
|---|---|---|
| Actual (`estaciones.id`) | 398 / 404 | 99,8 % |
| Viejo (`id_estacion`) | 133 / 404 | 43,0 % |

Además, los dos catálogos comparten 135 IDs, pero **26 de ellos son estaciones distintas**, a 200 m o más una de otra. Por ejemplo, el ID 131 es "Retiro III" en el viejo y "Hospital de Clínicas" en el actual, a 2,4 km. El ID 176 es "Pinzón" contra "Parque Sarmiento I", a 15 km.

## Decisión

- `silver.stations` se construye **solo desde el catálogo actual**, cruzando por `id`. `numero_de_estacion` no sirve como clave porque tiene 9 valores repetidos.
- Las 6 estaciones de los viajes que no están en el catálogo (591, 448, 593, 443, 510, 594) se completan con el nombre, la dirección y las coordenadas más frecuentes en los viajes, marcadas con `source = 'trips'`. Así quedan 413 estaciones y ningún viaje pierde su estación.
- Si un ID tiene más de un nombre en los viajes (2 casos: 307 y 449), gana el nombre del catálogo.
- El catálogo viejo se carga en `bronze.stations_legacy` para que quede registro de lo recibido, pero **no pasa a silver**.

## Alternativas consideradas

| Alternativa | Por qué se descartó |
|---|---|
| Usar el catálogo viejo | Cubre menos de la mitad de los viajes. |
| Unir los dos catálogos y completar con el viejo | Los 26 IDs reutilizados asignarían coordenadas, y por lo tanto comunas, de otra estación. El error no se vería: el cruce funciona igual y el dato es incorrecto. Tampoco aporta las 6 estaciones faltantes, porque sus IDs llegan hasta 200. |
| Descartar los viajes de las 6 estaciones faltantes | Se perderían 10.678 salidas y llegadas, y los viajes tienen datos suficientes para reconstruir esas estaciones. |

## Consecuencias

- El modelo depende de que el catálogo actual siga usando los mismos IDs que los viajes. Un test de dbt de `relationships` entre `fct_trips` y `dim_station` lo controla en cada corrida.
- `source` deja visibles las 6 estaciones reconstruidas, por si después aparecen en una versión nueva del catálogo.
- Si se suman viajes de años anteriores (anteriores al sistema actual), habría que revisar esta decisión con un catálogo por período.

## Notas

- **2026-10-15 (T4.2):** una de las 6 estaciones completadas desde los viajes, la 510 "[Valet] Galpón" (punto de servicio, no una estación pública), trae lat/long en 0 en sus 176 apariciones. Se conserva sin ubicación (`comuna_assignment = 'unknown'`, comuna `NULL`) para que ningún viaje pierda su estación. No cambia la decisión.
