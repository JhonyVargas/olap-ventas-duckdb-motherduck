"""Pipeline ETL: genera los datos y los carga al modelo estrella en DuckDB/MotherDuck.

Uso:
    python -m etl.pipeline                 # MotherDuck si existe MOTHERDUCK_TOKEN, si no local
    python -m etl.pipeline --local         # fuerza archivo local data/olap_ventas.duckdb
    python -m etl.pipeline --hasta 2025-12-31
"""
from __future__ import annotations

import argparse
import time
from datetime import date
from pathlib import Path

import duckdb

from etl.db import LOCAL_DB_PATH, describe_target, get_connection
from etl.generar_datos import generar

SCHEMA_SQL = Path(__file__).resolve().parent.parent / "sql" / "schema.sql"
ORDEN_CARGA = ["dim_fecha", "dim_producto", "dim_region", "dim_cliente", "dim_canal", "fact_ventas"]


def cargar(con: duckdb.DuckDBPyConnection, tablas: dict) -> dict[str, int]:
    """Recrea el esquema y carga todas las tablas en una sola transacción."""
    con.execute("BEGIN TRANSACTION")
    try:
        con.execute(SCHEMA_SQL.read_text(encoding="utf-8"))
        for nombre in ORDEN_CARGA:
            df = tablas[nombre]  # noqa: F841  (DuckDB lee el DataFrame por nombre)
            cols = ", ".join(tablas[nombre].columns)
            con.execute(f"INSERT INTO {nombre} ({cols}) SELECT {cols} FROM df")
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    return {n: con.execute(f"SELECT count(*) FROM {n}").fetchone()[0] for n in ORDEN_CARGA}


def ejecutar(hasta: date | None = None, local: bool = False, local_path: Path | str | None = None) -> dict[str, int]:
    destino_local = local_path or (LOCAL_DB_PATH if local else None)
    inicio = time.perf_counter()
    tablas = generar(fecha_fin=hasta)
    con = get_connection(local_path=destino_local)
    try:
        conteos = cargar(con, tablas)
    finally:
        con.close()

    print(f"Destino: {describe_target(local_path=destino_local)}")
    for nombre, filas in conteos.items():
        print(f"  {nombre:<14} {filas:>8,} filas")
    print(f"Listo en {time.perf_counter() - inicio:.1f} s")
    return conteos


def main() -> None:
    parser = argparse.ArgumentParser(description="ETL del cubo OLAP de ventas")
    parser.add_argument("--local", action="store_true", help="cargar en el archivo DuckDB local")
    parser.add_argument("--hasta", type=date.fromisoformat, help="última fecha a generar (YYYY-MM-DD)")
    args = parser.parse_args()
    ejecutar(hasta=args.hasta, local=args.local)


if __name__ == "__main__":
    main()
