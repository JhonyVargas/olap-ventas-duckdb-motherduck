"""Conexión a DuckDB: MotherDuck (nube) si hay token, archivo local si no."""
from __future__ import annotations

import os
from pathlib import Path

import duckdb

DB_NAME = os.getenv("OLAP_DB_NAME", "olap_ventas")
LOCAL_DB_PATH = Path(__file__).resolve().parent.parent / "data" / f"{DB_NAME}.duckdb"


def get_token() -> str | None:
    token = os.getenv("MOTHERDUCK_TOKEN") or os.getenv("motherduck_token")
    return token.strip() if token else None


def get_connection(token: str | None = None, local_path: Path | str | None = None) -> duckdb.DuckDBPyConnection:
    """Devuelve una conexión lista para usar.

    - Con token  -> MotherDuck, base `olap_ventas` (se crea si no existe).
    - Sin token  -> archivo local data/olap_ventas.duckdb.
    """
    token = token or get_token()
    if token and local_path is None:
        with duckdb.connect(f"md:?motherduck_token={token}") as con:
            con.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
        # Conectar directo a la base (y no con USE): un USE solo afecta a esa conexión,
        # mientras que los cursores (con.cursor(), que usa el dashboard) arrancarían en my_db.
        return duckdb.connect(f"md:{DB_NAME}?motherduck_token={token}")

    path = Path(local_path) if local_path else LOCAL_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(path))


def describe_target(token: str | None = None, local_path: Path | str | None = None) -> str:
    token = token or get_token()
    if token and local_path is None:
        return f"MotherDuck (md:{DB_NAME})"
    return f"DuckDB local ({Path(local_path) if local_path else LOCAL_DB_PATH.name})"
