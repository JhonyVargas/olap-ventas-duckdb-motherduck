-- =============================================================
--  Modelo estrella (star schema) para el cubo OLAP de ventas
--  Hechos: fact_ventas  |  Dimensiones: fecha, producto, region,
--  cliente, canal
-- =============================================================

DROP VIEW  IF EXISTS v_ventas;
DROP TABLE IF EXISTS fact_ventas;
DROP TABLE IF EXISTS dim_fecha;
DROP TABLE IF EXISTS dim_producto;
DROP TABLE IF EXISTS dim_region;
DROP TABLE IF EXISTS dim_cliente;
DROP TABLE IF EXISTS dim_canal;

CREATE TABLE dim_fecha (
    fecha_id      INTEGER PRIMARY KEY,   -- yyyymmdd
    fecha         DATE    NOT NULL,
    anio          INTEGER NOT NULL,
    semestre      INTEGER NOT NULL,
    trimestre     INTEGER NOT NULL,
    mes           INTEGER NOT NULL,
    nombre_mes    VARCHAR NOT NULL,
    dia           INTEGER NOT NULL,
    dia_semana    INTEGER NOT NULL,      -- 1 = lunes ... 7 = domingo
    nombre_dia    VARCHAR NOT NULL,
    es_fin_semana BOOLEAN NOT NULL
);

CREATE TABLE dim_producto (
    producto_id     INTEGER PRIMARY KEY,
    producto        VARCHAR NOT NULL,
    subcategoria    VARCHAR NOT NULL,
    categoria       VARCHAR NOT NULL,
    precio_lista    DECIMAL(10, 2) NOT NULL,
    ratio_costo     DECIMAL(4, 2)  NOT NULL
);

CREATE TABLE dim_region (
    region_id     INTEGER PRIMARY KEY,
    departamento  VARCHAR NOT NULL,
    macroregion   VARCHAR NOT NULL
);

CREATE TABLE dim_cliente (
    cliente_id  INTEGER PRIMARY KEY,
    cliente     VARCHAR NOT NULL,
    segmento    VARCHAR NOT NULL,
    region_id   INTEGER NOT NULL
);

CREATE TABLE dim_canal (
    canal_id  INTEGER PRIMARY KEY,
    canal     VARCHAR NOT NULL
);

CREATE TABLE fact_ventas (
    venta_id         BIGINT  PRIMARY KEY,
    fecha_id         INTEGER NOT NULL,
    producto_id      INTEGER NOT NULL,
    region_id        INTEGER NOT NULL,
    cliente_id       INTEGER NOT NULL,
    canal_id         INTEGER NOT NULL,
    cantidad         INTEGER NOT NULL,
    precio_unitario  DECIMAL(10, 2) NOT NULL,
    descuento        DECIMAL(4, 2)  NOT NULL,
    monto_venta      DECIMAL(12, 2) NOT NULL,
    costo            DECIMAL(12, 2) NOT NULL,
    ganancia         DECIMAL(12, 2) NOT NULL
);

-- Vista "aplanada" del cubo: une los hechos con todas sus dimensiones.
CREATE VIEW v_ventas AS
SELECT
    f.venta_id,
    d.fecha, d.anio, d.semestre, d.trimestre, d.mes, d.nombre_mes,
    d.dia_semana, d.nombre_dia, d.es_fin_semana,
    p.categoria, p.subcategoria, p.producto,
    r.macroregion, r.departamento,
    c.segmento, c.cliente,
    ca.canal,
    f.cantidad, f.precio_unitario, f.descuento,
    f.monto_venta, f.costo, f.ganancia
FROM fact_ventas f
JOIN dim_fecha    d  USING (fecha_id)
JOIN dim_producto p  USING (producto_id)
JOIN dim_region   r  USING (region_id)
JOIN dim_cliente  c  USING (cliente_id)
JOIN dim_canal    ca USING (canal_id);
