-- =============================================================
--  Consultas OLAP de ejemplo sobre el cubo de ventas
--  Ejecutar en DuckDB local:  duckdb data/olap_ventas.duckdb
--  o en el editor web de MotherDuck (base olap_ventas).
-- =============================================================

-- 1) ROLL-UP: de mes a año (subimos en la jerarquía de tiempo)
SELECT anio, sum(monto_venta) AS ventas
FROM v_ventas
GROUP BY anio
ORDER BY anio;

-- 2) DRILL-DOWN: de año a trimestre y mes (bajamos al detalle)
SELECT anio, trimestre, mes, sum(monto_venta) AS ventas
FROM v_ventas
WHERE anio = 2025
GROUP BY anio, trimestre, mes
ORDER BY anio, trimestre, mes;

-- 3) SLICE: fijamos UNA dimensión en un valor (canal = 'Online')
SELECT categoria, sum(monto_venta) AS ventas
FROM v_ventas
WHERE canal = 'Online'
GROUP BY categoria
ORDER BY ventas DESC;

-- 4) DICE: filtramos VARIAS dimensiones a la vez (sub-cubo)
SELECT departamento, categoria, sum(monto_venta) AS ventas
FROM v_ventas
WHERE anio IN (2024, 2025)
  AND macroregion IN ('Sur', 'Norte')
  AND categoria   IN ('Tecnología', 'Muebles')
GROUP BY departamento, categoria
ORDER BY departamento, categoria;

-- 5) PIVOT: rotamos el cubo (macroregiones en filas, categorías en columnas)
PIVOT v_ventas
ON categoria
USING sum(monto_venta)
GROUP BY macroregion
ORDER BY macroregion;

-- 6) GROUP BY ROLLUP: subtotales por año + total general en una sola consulta
SELECT anio, trimestre, sum(monto_venta) AS ventas, GROUPING(anio, trimestre) AS nivel
FROM v_ventas
GROUP BY ROLLUP (anio, trimestre)
ORDER BY anio NULLS LAST, trimestre NULLS LAST;

-- 7) GROUP BY CUBE: todas las combinaciones de macroregión × canal
SELECT macroregion, canal, sum(monto_venta) AS ventas
FROM v_ventas
GROUP BY CUBE (macroregion, canal)
ORDER BY macroregion NULLS LAST, canal NULLS LAST;

-- 8) GROUPING SETS: solo las agregaciones que nos interesan
SELECT categoria, segmento, sum(ganancia) AS ganancia
FROM v_ventas
GROUP BY GROUPING SETS ((categoria), (segmento), ())
ORDER BY categoria NULLS LAST, segmento NULLS LAST;

-- 9) Función de ventana: ranking de productos por ventas dentro de cada categoría
SELECT categoria, producto, ventas,
       rank() OVER (PARTITION BY categoria ORDER BY ventas DESC) AS puesto
FROM (
    SELECT categoria, producto, sum(monto_venta) AS ventas
    FROM v_ventas GROUP BY ALL
)
QUALIFY puesto <= 3
ORDER BY categoria, puesto;

-- 10) Crecimiento interanual (YoY) por categoría
SELECT categoria, anio, ventas,
       round(100 * (ventas / lag(ventas) OVER (PARTITION BY categoria ORDER BY anio) - 1), 1) AS crec_pct
FROM (
    SELECT categoria, anio, sum(monto_venta) AS ventas
    FROM v_ventas GROUP BY ALL
)
ORDER BY categoria, anio;
