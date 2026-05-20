"""
redshift_to_s3_snapshot.py
==========================
Job diario que congela vistas/tablas de Redshift en S3 como Parquet.
Diseñado para correr en EC2/Linux, credenciales AWS via variables de entorno.

Variables de entorno requeridas:
    AWS_ACCESS_KEY_ID
    AWS_SECRET_ACCESS_KEY
    AWS_DEFAULT_REGION        (ej: us-east-1)
    REDSHIFT_HOST
    REDSHIFT_PORT             (default: 5439)
    REDSHIFT_DB               (default: warehouse)
    REDSHIFT_USER
    REDSHIFT_PASSWORD
    S3_BUCKET                 (ej: libgot-snapshots)
    S3_PREFIX                 (ej: snapshots)  -- opcional, default: snapshots

Uso:
    pip install -r requirements.txt
    python redshift_to_s3_snapshot.py

    # Para correr solo una tabla específica del registro:
    python redshift_to_s3_snapshot.py --nombre ventas_multipais
"""

import os
import io
import sys
import logging
import argparse
from datetime import date

import redshift_connector
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import boto3

from config.tables import TABLAS

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Configuración ──────────────────────────────────────────────────────────────
REDSHIFT_CONFIG = {
    "host":     os.environ["REDSHIFT_HOST"],
    "port":     int(os.environ.get("REDSHIFT_PORT", 5439)),
    "database": os.environ.get("REDSHIFT_DB", "warehouse"),
    "user":     os.environ["REDSHIFT_USER"],
    "password": os.environ["REDSHIFT_PASSWORD"],
}

S3_BUCKET = os.environ["S3_BUCKET"]
S3_PREFIX = os.environ.get("S3_PREFIX", "snapshots")

# Filas por chunk al leer de Redshift (evita explotar la RAM)
CHUNK_SIZE = 50_000


# ── Funciones ──────────────────────────────────────────────────────────────────

def conectar_redshift() -> redshift_connector.Connection:
    log.info("Conectando a Redshift: %s/%s", REDSHIFT_CONFIG["host"], REDSHIFT_CONFIG["database"])
    conn = redshift_connector.connect(**REDSHIFT_CONFIG)
    conn.autocommit = True
    return conn


def query_a_parquet_en_memoria(conn: redshift_connector.Connection, nombre: str, query: str) -> bytes | None:
    """
    Ejecuta el query en Redshift en chunks y serializa el resultado como Parquet en memoria.
    Devuelve los bytes del archivo Parquet listos para subir a S3, o None si no hay filas.
    """
    log.info("  Ejecutando query para: %s", nombre)
    cursor = conn.cursor()
    cursor.execute(query)

    chunks = []
    total_filas = 0

    while True:
        rows = cursor.fetchmany(CHUNK_SIZE)
        if not rows:
            break
        cols = [desc[0] for desc in cursor.description]
        df_chunk = pd.DataFrame(rows, columns=cols)
        chunks.append(df_chunk)
        total_filas += len(df_chunk)
        log.info("    → %d filas leídas hasta ahora...", total_filas)

    cursor.close()

    if not chunks:
        log.warning("  Sin filas: %s", nombre)
        return None

    df = pd.concat(chunks, ignore_index=True)
    log.info("  Total: %d filas, %d columnas", len(df), len(df.columns))

    buffer = io.BytesIO()
    tabla_arrow = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(
        tabla_arrow,
        buffer,
        compression="snappy",
        row_group_size=100_000,
    )
    buffer.seek(0)
    return buffer.read()


def subir_a_s3(parquet_bytes: bytes, nombre: str, universo: str) -> str:
    """
    Sube el Parquet a S3 pisando el archivo del día anterior:
    s3://BUCKET/PREFIX/NOMBRE/<universo>_platinum.parquet
    """
    archivo = f"{universo}_platinum.parquet"
    s3_key = f"{S3_PREFIX}/{nombre}/{archivo}"
    s3 = boto3.client("s3")

    log.info("  Subiendo a s3://%s/%s (%s KB)", S3_BUCKET, s3_key, len(parquet_bytes) // 1024)
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=s3_key,
        Body=parquet_bytes,
        ContentType="application/octet-stream",
    )
    return f"s3://{S3_BUCKET}/{s3_key}"


def procesar_entrada(conn, nombre: str, config: dict) -> dict:
    resultado = {
        "nombre": nombre,
        "descripcion": config.get("descripcion", ""),
        "status": "ok",
        "s3_path": None,
        "error": None,
    }
    try:
        parquet_bytes = query_a_parquet_en_memoria(conn, nombre, config["query"])
        if parquet_bytes is None:
            resultado["status"] = "vacia"
            return resultado
        universo = config.get("universo", nombre)
        s3_path = subir_a_s3(parquet_bytes, nombre, universo)
        resultado["s3_path"] = s3_path
        log.info("  OK %s → %s", nombre, s3_path)
    except Exception as e:
        resultado["status"] = "error"
        resultado["error"] = str(e)
        log.error("  ERROR en %s: %s", nombre, e)
    return resultado


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Congela tablas/vistas de Redshift en S3 como Parquet")
    parser.add_argument(
        "--nombre",
        help="Procesar solo esta entrada del registro (ej: ventas_multipais)",
        default=None,
    )
    args = parser.parse_args()

    fecha_hoy = date.today().isoformat()
    log.info("=== Snapshot diario — fecha: %s ===", fecha_hoy)

    if args.nombre:
        if args.nombre not in TABLAS:
            log.error("'%s' no existe en config/tables.py. Opciones: %s", args.nombre, list(TABLAS.keys()))
            sys.exit(1)
        tablas_a_procesar = {args.nombre: TABLAS[args.nombre]}
        log.info("Modo piloto: procesando solo '%s'", args.nombre)
    else:
        tablas_a_procesar = TABLAS

    log.info("Tablas a procesar: %d", len(tablas_a_procesar))

    conn = conectar_redshift()
    resultados = []

    for nombre, config in tablas_a_procesar.items():
        log.info("── %s: %s ──", nombre, config.get("descripcion", ""))
        r = procesar_entrada(conn, nombre, config)
        resultados.append(r)

    conn.close()

    # ── Resumen final ──
    log.info("")
    log.info("=== RESUMEN ===")
    ok    = [r for r in resultados if r["status"] == "ok"]
    error = [r for r in resultados if r["status"] == "error"]
    vacia = [r for r in resultados if r["status"] == "vacia"]

    log.info("OK:      %d tablas", len(ok))
    log.info("Vacías:  %d tablas", len(vacia))
    log.info("Errores: %d tablas", len(error))

    for r in ok:
        log.info("  → %s", r["s3_path"])
    for r in error:
        log.error("  ERROR %s: %s", r["nombre"], r["error"])

    if error:
        sys.exit(1)


if __name__ == "__main__":
    main()
