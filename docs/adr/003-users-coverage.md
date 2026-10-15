# ADR 003: Usuarios con alta 2024 y 2025, y `has_profile` para el resto

- **Estado:** Aceptado
- **Fecha:** 2026-10-15
- **Requerimientos:** FR-01c, FR-09, Q3, Q4

## Contexto

Dos preguntas del challenge necesitan datos del usuario: la relación entre la edad y la cantidad de viajes (Q3), y la relación entre la cantidad de viajes y la fecha de alta (Q4). Los viajes solo traen `id_usuario` y `género`; la edad y la fecha de alta están en los archivos de usuarios.

El dataset de usuarios 2025 del challenge **solo trae a quienes se dieron de alta en 2025**. El profiling ([profile.md](../profiling/profile.md)) midió cuántos viajes quedan con perfil:

| Archivo de usuarios | Usuarios con viajes | Viajes cubiertos | Viajes por usuario |
|---|---|---|---|
| Altas 2025 | 140.533 | 860.741 (27,3 %) | 6,1 |
| Altas 2024 | 48.268 | 686.780 (21,8 %) | 14,2 |
| **Total** | **188.801** | **1.547.521 (49,0 %)** | 8,2 |

Con solo el archivo de 2025, Q3 y Q4 quedaban apoyadas en un cuarto de los viajes, y además sesgadas hacia usuarios nuevos y menos frecuentes.

## Decisión

- Sumar el archivo de **usuarios con alta en 2024** del mismo portal, lo que lleva la cobertura al 49 %. No se suman años anteriores.
- Cada archivo se carga en su propia tabla bronze (`users_2024`, `users_2025`) con su esquema, porque los dos son distintos: 2024 usa `id_usuario` en vez de `ID Cliente`, no trae la columna de DNI y viene con BOM. Se unifican en `silver.users`, con `signup_year` para distinguirlos y `has_dni = NULL` en 2024.
- `dim_user` incluye a **todos** los usuarios que aparecen en los viajes (286.322), con `has_profile`:
  - `true`: está en alguno de los dos archivos y tiene edad y fecha de alta.
  - `false`: alta anterior a 2024. Edad y fecha de alta quedan en `NULL`; el género sale del más frecuente en sus viajes.
- Q3 y Q4 se calculan sobre `has_profile = true` e informan en su resultado qué porcentaje de los viajes cubren.

## Alternativas consideradas

| Alternativa | Por qué se descartó |
|---|---|
| Usar solo el archivo 2025 del challenge | Cobertura del 27 % y sesgo hacia usuarios nuevos. |
| Sumar todos los años disponibles (2015 en adelante) | Subiría la cobertura (el 51 % restante son altas anteriores a 2024), pero suma un archivo por año, cada uno con un esquema a verificar, como ya pasó entre 2024 y 2025. Se priorizó cerrar el pipeline completo; queda como mejora futura. |
| Descartar de `fct_trips` los viajes sin perfil | Q1, Q2, Q5 y Q6 no necesitan el perfil y perderían el 51 % de los datos. |
| `dim_user` solo con usuarios con perfil y FK nullable en `fct_trips` | Rompe la integridad referencial y obliga a cada consulta a tratar los `NULL` de forma especial. `has_profile` deja la limitación explícita sin perder filas. |

## Consecuencias

- Q3 y Q4 responden para el 49 % de los viajes, y la limitación queda documentada en el README.
- Q4 puede comparar 24 meses de alta en vez de 12. Las métricas por cohorte se definen en la Fase 5.
- Sumar otro año es agregar un archivo y una tabla bronze, más una rama en la unión de `silver.users`.
