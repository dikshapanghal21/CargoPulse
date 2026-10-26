-- Runs once when the Postgres volume is first initialised.
-- Creates the database used by the pytest suite (`docker compose run --rm api pytest`).
CREATE DATABASE cargopulse_test;
