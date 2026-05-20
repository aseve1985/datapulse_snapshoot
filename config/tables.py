"""
config/tables.py
================
Registro de tablas/vistas a congelar diariamente en S3.

Para agregar una tabla nueva, solo añadí una entrada al diccionario TABLAS:

    "nombre_carpeta_s3": {
        "query": "SELECT * FROM schema.tabla",   # podés filtrar, renombrar cols, etc.
        "descripcion": "Descripción legible",
    },

El nombre_carpeta_s3 define la ruta en S3:
    s3://BUCKET/PREFIX/<nombre_carpeta_s3>/fecha=YYYY-MM-DD/data.parquet
"""

TABLAS: dict[str, dict] = {

    # ── Ventas ────────────────────────────────────────────────────────────────
    "ventas_multipais": {
        "query":       "SELECT * FROM platinum_ia.vw_ventas_multipais",
        "descripcion": "Vista de ventas consolidada multi-país",
        "universo":    "ventas",   # → archivo: ventas_YYYY-MM-DD.parquet
    },

    # ── Legales (desactivado - data manejada por otro proceso) ───────────────
    # "legales_uif": {
    #     "query":       "SELECT * FROM platinum_ia.monitor_uif_arg",
    #     "descripcion": "Monitor UIF Argentina",
    #     "universo":    "legales_uif",
    # },

    # ── Proximas tablas (descomentar cuando esten listas) ─────────────────────
    # "cobranzas_arg": {
    #     "query":       "SELECT * FROM collections_arg.tu_tabla",
    #     "descripcion": "Cobranzas Argentina",
    #     "universo":    "cobranzas",
    # },
    # "riesgo_arg": {
    #     "query":       "SELECT * FROM risk_arg.tu_tabla",
    #     "descripcion": "Riesgo Argentina",
    #     "universo":    "riesgo",
    # },
    # "ventas_arg": {
    #     "query":       "SELECT * FROM sales_arg.tu_tabla",
    #     "descripcion": "Ventas Argentina",
    #     "universo":    "ventas",
    # },
    # "cobranzas_col": {
    #     "query":       "SELECT * FROM collections_col.tu_tabla",
    #     "descripcion": "Cobranzas Colombia",
    #     "universo":    "cobranzas",
    # },

}
