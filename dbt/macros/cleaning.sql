{#-
    Reglas de limpieza compartidas (docs/data-dictionary.md, "Convenciones").
    Todas reciben una columna text de bronze y devuelven NULL si el valor no es válido:
    nunca fallan por un dato sucio, y los modelos deciden si eso es un rechazo.
-#}

{#- `146BAEcobici` -> 146, `1.0` -> 1, `''` -> NULL.
    Una sola expresión regular para validar y un substring para extraer: es ~2x más rápido que
    dos regexp_replace, y se aplica a 6,3 M extremos de viaje. -#}
{% macro clean_id(column) -%}
    case
        when trim({{ column }}) ~ '^[0-9]+(BAEcobici|\.0)?$'
            then substring(trim({{ column }}) from '^[0-9]+')::bigint
    end
{%- endmacro %}

{#- `"3,108"` -> 3108, `-58.4` -> -58.4, `abc` -> NULL. Quita el separador de miles. -#}
{% macro clean_number(column, type='numeric') -%}
    case
        when replace(trim({{ column }}), ',', '') ~ '^-?[0-9]+(\.[0-9]+)?$'
            then replace(trim({{ column }}), ',', '')::{{ type }}
    end
{%- endmacro %}

{#- Texto con trim; vacío -> NULL. -#}
{% macro clean_text(column) -%}
    nullif(trim({{ column }}), '')
{%- endmacro %}

{#- MALE, FEMALE u OTHER (sin importar mayúsculas); cualquier otro valor o vacío -> NULL. -#}
{% macro clean_gender(column) -%}
    case
        when upper(trim({{ column }})) in ('MALE', 'FEMALE', 'OTHER')
            then upper(trim({{ column }}))
    end
{%- endmacro %}

{#- `YYYY-MM-DD` + `HH:MM:SS` (o un único `YYYY-MM-DD HH:MM:SS`) -> timestamp; si el formato
    no coincide -> NULL. Sin zona horaria: hora local de Buenos Aires, como en el origen. -#}
{% macro clean_timestamp(date_column, time_column=none) -%}
    {%- set value -%}
        {%- if time_column -%}
            trim({{ date_column }}) || ' ' || trim({{ time_column }})
        {%- else -%}
            trim({{ date_column }})
        {%- endif -%}
    {%- endset -%}
    case
        when {{ value }} ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}$'
            then ({{ value }})::timestamp
    end
{%- endmacro %}

{#- Coordenada dentro de la caja de CABA (dbt_project.yml, vars.caba_bbox); si no, NULL. -#}
{% macro clean_latitude(column) -%}
    {%- set bbox = var('caba_bbox') -%}
    case
        when {{ clean_number(column) }} between {{ bbox.lat_min }} and {{ bbox.lat_max }}
            then {{ clean_number(column) }}
    end
{%- endmacro %}

{% macro clean_longitude(column) -%}
    {%- set bbox = var('caba_bbox') -%}
    case
        when {{ clean_number(column) }} between {{ bbox.lon_min }} and {{ bbox.lon_max }}
            then {{ clean_number(column) }}
    end
{%- endmacro %}

{#- Punto PostGIS WGS84 a partir de longitud y latitud ya limpias. -#}
{% macro make_point(longitude, latitude) -%}
    case
        when {{ longitude }} is not null and {{ latitude }} is not null
            then st_setsrid(st_makepoint({{ longitude }}, {{ latitude }}), 4326)
    end
{%- endmacro %}
