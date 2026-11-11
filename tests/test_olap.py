"""Pruebas del ETL y del cubo OLAP (se ejecutan en GitHub Actions antes de cargar)."""
from datetime import date
from pathlib import Path

import duckdb
import pytest

from etl.generar_datos import generar
from etl.pipeline import cargar

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"
HASTA = date(2025, 12, 31)


@pytest.fixture(scope="module")
def con(tmp_path_factory):
    c = duckdb.connect(str(tmp_path_factory.mktemp("db") / "test.duckdb"))
    cargar(c, generar(fecha_fin=HASTA))
    yield c
    c.close()


def uno(con, sql):
    return con.execute(sql).fetchone()[0]


def test_tablas_con_datos(con):
    for tabla in ["dim_fecha", "dim_producto", "dim_region", "dim_cliente", "dim_canal", "fact_ventas"]:
        assert uno(con, f"SELECT count(*) FROM {tabla}") > 0, tabla


def test_dim_fecha_continua(con):
    assert uno(con, "SELECT count(*) FROM dim_fecha") == (HASTA - date(2023, 1, 1)).days + 1


def test_integridad_referencial(con):
    # Todos los hechos deben encontrar sus dimensiones (la vista hace INNER JOIN)
    assert uno(con, "SELECT count(*) FROM fact_ventas") == uno(con, "SELECT count(*) FROM v_ventas")


def test_medidas_consistentes(con):
    assert uno(con, "SELECT count(*) FROM fact_ventas WHERE cantidad <= 0 OR monto_venta <= 0") == 0
    assert uno(con, "SELECT max(abs(ganancia - (monto_venta - costo))) FROM fact_ventas") <= 0.01


def test_rollup_cuadra_con_total(con):
    total = uno(con, "SELECT sum(monto_venta) FROM fact_ventas")
    gran_total = uno(con, """
        SELECT sum(monto_venta) FROM v_ventas
        GROUP BY ROLLUP (anio, trimestre)
        HAVING GROUPING(anio) = 1""")
    assert gran_total == total


def test_cube_genera_todas_las_combinaciones(con):
    n_macro = uno(con, "SELECT count(DISTINCT macroregion) FROM v_ventas")
    n_canal = uno(con, "SELECT count(DISTINCT canal) FROM v_ventas")
    filas = uno(con, "SELECT count(*) FROM (SELECT 1 FROM v_ventas GROUP BY CUBE (macroregion, canal))")
    assert filas == (n_macro + 1) * (n_canal + 1)


def test_historico_estable():
    # Agregar un día nuevo no debe cambiar los días anteriores (carga incremental simulada)
    a = generar(fecha_fin=date(2023, 3, 31))["fact_ventas"]
    b = generar(fecha_fin=date(2023, 4, 1))["fact_ventas"]
    assert b.iloc[: len(a)].reset_index(drop=True).equals(a.reset_index(drop=True))
    assert len(b) > len(a)


def test_consultas_de_ejemplo_corren(con):
    script = (SQL_DIR / "consultas_olap.sql").read_text(encoding="utf-8")
    sentencias = [s for s in script.split(";")
                  if any(l.strip() and not l.strip().startswith("--") for l in s.splitlines())]
    assert len(sentencias) == 10
    for sentencia in sentencias:
        assert con.execute(sentencia).fetchall()
