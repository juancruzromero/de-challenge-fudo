-- Extensiones de la base analítica. Corre una sola vez, al crear el volumen de Postgres.
-- PostGIS asigna la comuna de cada estación por punto en polígono (ADR 001).
create extension if not exists postgis;
