{#-
    Por defecto dbt arma el schema como <schema del target>_<schema del modelo> (silver_gold).
    Acá las capas son schemas fijos creados en sql/init: se usa el schema del modelo tal cual.
-#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
