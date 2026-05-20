# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project does

Daily job that reads views/tables from Redshift and writes them to S3 as Parquet (Snappy compressed). Each run overwrites the previous file — no date partitioning, just one current snapshot per table.

S3 path pattern: `s3://data-lake-libgot-externos/platinum_ia/<nombre>/<universo>_platinum.parquet`

## Running

```bat
:: Run all tables
run_snapshot.bat

:: Run a single table by name
.venv\Scripts\python redshift_to_s3_snapshot.py --nombre ventas_multipais
```

The `.bat` loads credentials from `.env` automatically and writes logs to `logs/snapshot_YYYYMMDD.log`.

## Environment setup (new machine)

```bat
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in credentials. Do not copy `.venv/` between machines.

## Adding a new table

Edit only `config/tables.py` — add an entry to the `TABLAS` dict:

```python
"nombre_carpeta_s3": {
    "query":       "SELECT * FROM schema.vista",
    "descripcion": "Descripcion legible",
    "universo":    "ventas",  # prefijo del archivo: ventas_platinum.parquet
},
```

The `universo` field controls the filename. Tables sharing the same `universo` produce files with the same name (intentional — same business domain, different source).

## Architecture

- `config/tables.py` — only file that needs editing to add/remove tables
- `redshift_to_s3_snapshot.py` — reads `TABLAS`, connects to Redshift, fetches in 50k-row chunks into memory, serializes to Parquet via PyArrow, uploads via boto3
- `run_snapshot.bat` — Windows entry point: loads `.env`, runs the script, logs output

Data flows entirely in memory (no temp files on disk). `exit(1)` on any table error so Task Scheduler can detect failures.

## Scheduling

Configured via Windows Task Scheduler pointing to `run_snapshot.bat`. The bat uses `%~dp0` for relative paths so it works from any location.
