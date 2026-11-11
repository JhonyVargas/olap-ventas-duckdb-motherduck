"""Genera datos sintéticos de ventas de una cadena retail en Perú.

Cada día se genera con su propia semilla, por lo que el histórico es
estable: si el pipeline corre mañana, los días anteriores salen idénticos
y solo se agregan las ventas del día nuevo (simula una carga diaria).
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

SEMILLA = 2025
FECHA_INICIO = date(2023, 1, 1)
VENTAS_DIARIAS_BASE = 35

REGIONES = [  # departamento, macroregión, peso de clientes
    ("Lima", "Lima", 0.35),
    ("Arequipa", "Sur", 0.10),
    ("La Libertad", "Norte", 0.08),
    ("Piura", "Norte", 0.07),
    ("Cusco", "Sur", 0.07),
    ("Tacna", "Sur", 0.06),
    ("Junín", "Centro", 0.06),
    ("Lambayeque", "Norte", 0.06),
    ("Loreto", "Oriente", 0.04),
    ("Puno", "Sur", 0.04),
    ("Ica", "Centro", 0.04),
    ("San Martín", "Oriente", 0.03),
]

PRODUCTOS = [  # producto, subcategoría, categoría, precio lista (S/), ratio costo
    ("Laptop 15 pulgadas Core i5", "Laptops", "Tecnología", 2800, 0.82),
    ("Laptop 14 pulgadas Ryzen 7", "Laptops", "Tecnología", 3500, 0.80),
    ("Smartphone gama media", "Celulares", "Tecnología", 1200, 0.78),
    ("Smartphone gama alta", "Celulares", "Tecnología", 3200, 0.83),
    ("Mouse inalámbrico", "Accesorios", "Tecnología", 80, 0.55),
    ("Audífonos bluetooth", "Accesorios", "Tecnología", 250, 0.60),
    ("Teclado mecánico", "Accesorios", "Tecnología", 220, 0.58),
    ("Silla ergonómica", "Sillas", "Muebles", 650, 0.65),
    ("Silla gamer", "Sillas", "Muebles", 900, 0.68),
    ("Escritorio de melamina", "Escritorios", "Muebles", 450, 0.60),
    ("Escritorio elevable", "Escritorios", "Muebles", 1500, 0.70),
    ("Estante de 5 niveles", "Estantes", "Muebles", 320, 0.62),
    ("Resma de papel A4", "Papelería", "Oficina", 25, 0.70),
    ("Cuaderno anillado", "Papelería", "Oficina", 12, 0.55),
    ("Caja de lapiceros x12", "Útiles", "Oficina", 18, 0.50),
    ("Engrapadora metálica", "Útiles", "Oficina", 35, 0.52),
    ("Archivador de palanca", "Útiles", "Oficina", 15, 0.50),
    ("Tóner de impresora", "Impresión", "Oficina", 280, 0.72),
    ("Impresora multifuncional", "Impresión", "Oficina", 950, 0.78),
    ("Licuadora", "Electrodomésticos", "Hogar", 230, 0.66),
    ("Horno microondas", "Electrodomésticos", "Hogar", 420, 0.70),
    ("Hervidor eléctrico", "Electrodomésticos", "Hogar", 120, 0.60),
    ("Lámpara LED de escritorio", "Iluminación", "Hogar", 60, 0.50),
    ("Foco inteligente WiFi", "Iluminación", "Hogar", 45, 0.52),
]

SEGMENTOS = (["Consumidor", "Pyme", "Corporativo"], [0.55, 0.30, 0.15])
CANALES = (["Tienda física", "Online", "Marketplace"], [0.55, 0.35, 0.10])
N_CLIENTES = 600

MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
         "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

# Estacionalidad del volumen de ventas por mes (Perú)
FACTOR_MES = {3: 1.15, 7: 1.30, 11: 1.25, 12: 1.60}   # clases, Fiestas Patrias, Black Friday, Navidad
FACTOR_DIA = {5: 1.20, 6: 0.80}                        # sábado / domingo
CRECIMIENTO_ANUAL = 0.12
DESCUENTOS = np.array([0.0, 0.0, 0.0, 0.05, 0.10, 0.15, 0.20])


def construir_dimensiones() -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(SEMILLA)

    dim_region = pd.DataFrame(
        [(i + 1, d, m) for i, (d, m, _) in enumerate(REGIONES)],
        columns=["region_id", "departamento", "macroregion"],
    )
    dim_producto = pd.DataFrame(
        [(i + 1, *p) for i, p in enumerate(PRODUCTOS)],
        columns=["producto_id", "producto", "subcategoria", "categoria", "precio_lista", "ratio_costo"],
    )
    pesos_region = np.array([r[2] for r in REGIONES])
    dim_cliente = pd.DataFrame({
        "cliente_id": np.arange(1, N_CLIENTES + 1),
        "cliente": [f"Cliente {i:04d}" for i in range(1, N_CLIENTES + 1)],
        "segmento": rng.choice(SEGMENTOS[0], size=N_CLIENTES, p=SEGMENTOS[1]),
        "region_id": rng.choice(dim_region["region_id"], size=N_CLIENTES, p=pesos_region / pesos_region.sum()),
    })
    dim_canal = pd.DataFrame({"canal_id": [1, 2, 3], "canal": CANALES[0]})
    return {"dim_region": dim_region, "dim_producto": dim_producto,
            "dim_cliente": dim_cliente, "dim_canal": dim_canal}


def construir_dim_fecha(inicio: date, fin: date) -> pd.DataFrame:
    fechas = pd.date_range(inicio, fin, freq="D")
    return pd.DataFrame({
        "fecha_id": fechas.strftime("%Y%m%d").astype(int),
        "fecha": fechas.date,
        "anio": fechas.year,
        "semestre": np.where(fechas.month <= 6, 1, 2),
        "trimestre": fechas.quarter,
        "mes": fechas.month,
        "nombre_mes": [MESES[m - 1] for m in fechas.month],
        "dia": fechas.day,
        "dia_semana": fechas.dayofweek + 1,
        "nombre_dia": [DIAS[d] for d in fechas.dayofweek],
        "es_fin_semana": fechas.dayofweek >= 5,
    })


def _pesos_productos(dim_producto: pd.DataFrame, mes: int) -> np.ndarray:
    # Productos baratos se venden más seguido; algunas categorías tienen su temporada.
    pesos = 1 / np.sqrt(dim_producto["precio_lista"].to_numpy(dtype=float))
    cat = dim_producto["categoria"].to_numpy()
    if mes == 3:
        pesos = np.where(cat == "Oficina", pesos * 2.5, pesos)
    if mes == 12:
        pesos = np.where(np.isin(cat, ["Tecnología", "Hogar"]), pesos * 1.5, pesos)
    return pesos / pesos.sum()


def generar_ventas_dia(dia: date, dims: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rng = np.random.default_rng(SEMILLA + dia.toordinal())
    años = dia.year - FECHA_INICIO.year + (dia.timetuple().tm_yday / 365)
    lam = (VENTAS_DIARIAS_BASE * FACTOR_MES.get(dia.month, 1.0)
           * FACTOR_DIA.get(dia.weekday(), 1.0) * (1 + CRECIMIENTO_ANUAL) ** años)
    n = int(rng.poisson(lam))
    if n == 0:
        return pd.DataFrame()

    prod = dims["dim_producto"]
    clientes = dims["dim_cliente"]
    idx_prod = rng.choice(len(prod), size=n, p=_pesos_productos(prod, dia.month))
    idx_cli = rng.integers(0, len(clientes), size=n)

    precio = prod["precio_lista"].to_numpy(dtype=float)[idx_prod]
    ratio = prod["ratio_costo"].to_numpy(dtype=float)[idx_prod]
    cantidad = np.where(precio < 100, rng.integers(1, 11, size=n), rng.integers(1, 4, size=n))
    descuento = rng.choice(DESCUENTOS, size=n)
    if dia.month == 11:  # Black Friday / Cyber: más descuentos
        descuento = np.maximum(descuento, rng.choice([0.10, 0.15, 0.25], size=n))

    bruto = cantidad * precio
    monto = np.round(bruto * (1 - descuento), 2)
    costo = np.round(bruto * ratio, 2)

    return pd.DataFrame({
        "fecha_id": int(dia.strftime("%Y%m%d")),
        "producto_id": prod["producto_id"].to_numpy()[idx_prod],
        "region_id": clientes["region_id"].to_numpy()[idx_cli],
        "cliente_id": clientes["cliente_id"].to_numpy()[idx_cli],
        "canal_id": rng.choice([1, 2, 3], size=n, p=CANALES[1]),
        "cantidad": cantidad,
        "precio_unitario": precio,
        "descuento": descuento,
        "monto_venta": monto,
        "costo": costo,
        "ganancia": np.round(monto - costo, 2),
    })


def generar(fecha_fin: date | None = None, fecha_inicio: date = FECHA_INICIO) -> dict[str, pd.DataFrame]:
    """Genera todas las tablas del modelo estrella hasta `fecha_fin` (por defecto, ayer)."""
    fecha_fin = fecha_fin or (date.today() - timedelta(days=1))
    dims = construir_dimensiones()
    dims["dim_fecha"] = construir_dim_fecha(fecha_inicio, fecha_fin)

    dias = (fecha_inicio + timedelta(days=i) for i in range((fecha_fin - fecha_inicio).days + 1))
    fact = pd.concat([generar_ventas_dia(d, dims) for d in dias], ignore_index=True)
    fact.insert(0, "venta_id", np.arange(1, len(fact) + 1, dtype=np.int64))
    dims["fact_ventas"] = fact
    return dims


if __name__ == "__main__":
    tablas = generar()
    for nombre, df in tablas.items():
        print(f"{nombre:<14} {len(df):>8,} filas")
