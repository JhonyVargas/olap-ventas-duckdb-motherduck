# Cómo construir un cubo OLAP gratis con DuckDB, MotherDuck y Streamlit (sin AWS)

*Roll-up, drill-down, slice, dice y pivot sobre un modelo estrella, desplegado en la nube y automatizado con GitHub Actions.*

---

Cuando se habla de OLAP (*Online Analytical Processing*) se suele pensar en servidores enormes y licencias caras. Hoy no hace falta nada de eso. En este artículo armamos una solución OLAP completa con herramientas **gratuitas**:

- **DuckDB**: base de datos analítica columnar que corre dentro de Python.
- **MotherDuck**: DuckDB en la nube, con plan gratuito.
- **Streamlit Community Cloud**: publica un dashboard en una URL pública.
- **GitHub Actions**: automatiza las pruebas y la carga de datos.

📦 **Repositorio:** `<enlace a tu repo>`
🌐 **Demo en vivo:** `<enlace a tu app de Streamlit>`

---

## 1. ¿Qué es OLAP y por qué DuckDB?

Los sistemas **OLTP** (los de una tienda online o un banco) están pensados para muchas transacciones pequeñas: insertar un pedido, actualizar un saldo. Los sistemas **OLAP**, en cambio, están pensados para **analizar**: sumar millones de filas, agrupar por año, comparar regiones.

Para eso conviene un motor **columnar**: guarda cada columna por separado, así que si calculas `sum(monto_venta)` solo lee esa columna. DuckDB es justamente eso, un "SQLite para análisis": no necesita servidor, se instala con `pip install duckdb` y entiende operadores OLAP como `ROLLUP`, `CUBE`, `GROUPING SETS` y `PIVOT`.

MotherDuck lleva DuckDB a la nube: el mismo código funciona en local o en la nube cambiando solo la cadena de conexión.

## 2. Arquitectura

```
GitHub (push / cron diario)
        │
        ▼
GitHub Actions ──► pytest ──► ETL en Python ──► MotherDuck (modelo estrella)
                                                      │
                                                      ▼
                                       Streamlit Cloud (dashboard público)
```

## 3. El modelo estrella

El caso de uso es una cadena retail peruana que vende tecnología, muebles, artículos de oficina y hogar en 12 departamentos. El modelo tiene una **tabla de hechos** con las medidas numéricas y **cinco dimensiones** que dan contexto:

| Tabla | Contenido |
|---|---|
| `fact_ventas` | cantidad, monto_venta, costo, ganancia |
| `dim_fecha` | año, semestre, trimestre, mes, día |
| `dim_producto` | categoría → subcategoría → producto |
| `dim_region` | macroregión → departamento |
| `dim_cliente` | segmento (Consumidor, Pyme, Corporativo) |
| `dim_canal` | Tienda física, Online, Marketplace |

```sql
CREATE TABLE fact_ventas (
    venta_id     BIGINT PRIMARY KEY,
    fecha_id     INTEGER NOT NULL,
    producto_id  INTEGER NOT NULL,
    region_id    INTEGER NOT NULL,
    cliente_id   INTEGER NOT NULL,
    canal_id     INTEGER NOT NULL,
    cantidad     INTEGER NOT NULL,
    monto_venta  DECIMAL(12, 2) NOT NULL,
    costo        DECIMAL(12, 2) NOT NULL,
    ganancia     DECIMAL(12, 2) NOT NULL
);
```

Encima creamos una vista `v_ventas` que une los hechos con todas las dimensiones. Esa vista es nuestro "cubo".

### Datos realistas

Los datos son sintéticos pero tienen patrones reales del mercado peruano: picos en **julio** (Fiestas Patrias), **noviembre** (Black Friday, con más descuentos) y **diciembre** (Navidad), más venta de útiles de oficina en **marzo** (regreso a clases), y un crecimiento anual de ~12 %.

Un detalle importante: **cada día se genera con su propia semilla aleatoria**. Así, cuando el pipeline corre mañana, los días anteriores salen idénticos y solo se agrega el día nuevo, como en una carga incremental real.

```python
def generar_ventas_dia(dia, dims):
    rng = np.random.default_rng(SEMILLA + dia.toordinal())
    lam = (VENTAS_DIARIAS_BASE
           * FACTOR_MES.get(dia.month, 1.0)      # estacionalidad
           * FACTOR_DIA.get(dia.weekday(), 1.0)  # sábados más, domingos menos
           * (1 + CRECIMIENTO_ANUAL) ** años)
    n = rng.poisson(lam)
    ...
```

## 4. Una sola conexión para local y nube

```python
def get_connection(token=None, local_path=None):
    token = token or os.getenv("MOTHERDUCK_TOKEN")
    if token and local_path is None:
        con = duckdb.connect(f"md:?motherduck_token={token}")
        con.execute("CREATE DATABASE IF NOT EXISTS olap_ventas")
        con.execute("USE olap_ventas")
        return con
    return duckdb.connect("data/olap_ventas.duckdb")
```

Si existe la variable `MOTHERDUCK_TOKEN`, los datos van a la nube; si no, a un archivo local. El resto del código no cambia.

La carga se hace en **una sola transacción**: si algo falla, no queda el cubo a medias. DuckDB puede leer un DataFrame de pandas directamente por su nombre de variable:

```python
con.execute("BEGIN TRANSACTION")
con.execute(open("sql/schema.sql").read())
for nombre in ORDEN_CARGA:
    df = tablas[nombre]
    con.execute(f"INSERT INTO {nombre} SELECT * FROM df")
con.execute("COMMIT")
```

## 5. Las operaciones OLAP en SQL

**Roll-up** (subir en la jerarquía):
```sql
SELECT anio, sum(monto_venta) FROM v_ventas GROUP BY anio;
```

**Drill-down** (bajar al detalle):
```sql
SELECT anio, trimestre, mes, sum(monto_venta)
FROM v_ventas WHERE anio = 2025 GROUP BY ALL;
```

**Slice** (fijar una dimensión):
```sql
SELECT categoria, sum(monto_venta) FROM v_ventas
WHERE canal = 'Online' GROUP BY categoria;
```

**Dice** (filtrar varias dimensiones, un sub-cubo):
```sql
SELECT departamento, categoria, sum(monto_venta) FROM v_ventas
WHERE anio IN (2024, 2025) AND macroregion IN ('Sur', 'Norte')
  AND categoria IN ('Tecnología', 'Muebles')
GROUP BY ALL;
```

**Pivot** (rotar el cubo). DuckDB tiene `PIVOT` nativo:
```sql
PIVOT v_ventas ON categoria USING sum(monto_venta) GROUP BY macroregion;
```

**ROLLUP** calcula subtotales y el total general en **una sola consulta**:
```sql
SELECT anio, trimestre, sum(monto_venta)
FROM v_ventas
GROUP BY ROLLUP (anio, trimestre);
```

**CUBE** genera **todas** las combinaciones de dimensiones:
```sql
SELECT macroregion, canal, sum(monto_venta)
FROM v_ventas
GROUP BY CUBE (macroregion, canal);
```

## 6. El dashboard con Streamlit

El dashboard tiene una pestaña por operación OLAP:

- **Barra lateral → Dice:** filtros por año, macroregión, categoría, canal y segmento.
- **Roll-up / Drill-down (tiempo):** pasa de Año a Trimestre, Mes o Día con un clic.
- **Drill-down (producto):** Categoría → Subcategoría → Producto.
- **Slice:** fija una dimensión y desglosa la "rebanada".
- **Pivot:** eliges filas, columnas y medida, y obtienes un mapa de calor. El botón *Rotar* intercambia los ejes.
- **ROLLUP / CUBE:** las tablas con subtotales calculadas por SQL.

Cada gráfico tiene un desplegable **"Ver SQL"** con la consulta exacta que se ejecutó.

Los filtros se pasan como **parámetros** para evitar inyección SQL. DuckDB permite pasar listas de Python directamente:

```python
condiciones = [f"list_contains(${col}, {col})" for col, sel in filtros.items() if sel]
WHERE = "WHERE " + " AND ".join(condiciones) if condiciones else ""
df = con.execute(f"SELECT ... FROM v_ventas {WHERE}", filtros).df()
```

## 7. Automatización con GitHub Actions

El workflow `.github/workflows/etl.yml` tiene dos jobs:

1. **pruebas:** ejecuta `pytest`. Verifica la integridad referencial, que el total de `ROLLUP` cuadre con la suma de los hechos, que `CUBE` genere todas las combinaciones y que el histórico sea estable.
2. **carga:** solo si las pruebas pasan, ejecuta el ETL contra MotherDuck usando el secreto `MOTHERDUCK_TOKEN`.

```yaml
on:
  push:
    branches: [main]
  schedule:
    - cron: "0 11 * * *"   # 06:00 hora de Perú: carga diaria
  workflow_dispatch:

jobs:
  pruebas:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - uses: actions/setup-python@v6
        with: { python-version: "3.12" }
      - run: pip install -r requirements-dev.txt
      - run: pytest -v
  carga:
    needs: pruebas
    runs-on: ubuntu-latest
    env:
      MOTHERDUCK_TOKEN: ${{ secrets.MOTHERDUCK_TOKEN }}
    steps:
      - uses: actions/checkout@v5
      - uses: actions/setup-python@v6
        with: { python-version: "3.12" }
      - run: pip install -r requirements.txt
      - run: python -m etl.pipeline
```

Gracias al `cron`, todos los días se agregan las ventas del día anterior sin intervención manual.

## 8. Publicarlo en la nube

1. Crea una cuenta en **motherduck.com** y genera un *Access Token*.
2. En GitHub: *Settings → Secrets and variables → Actions* → agrega `MOTHERDUCK_TOKEN`.
3. En *Actions*, ejecuta el workflow con **Run workflow** para la primera carga.
4. En **share.streamlit.io** → *Create app* → elige el repo y `streamlit_app.py`. En *Advanced settings → Secrets* pega:
   ```toml
   MOTHERDUCK_TOKEN = "tu_token"
   ```
5. En un par de minutos tienes una URL pública `https://<tu-app>.streamlit.app`.

## 9. Lo que aprendimos

- Para un proyecto pequeño o mediano no hace falta un clúster: **DuckDB procesa decenas de miles de filas en milisegundos**.
- El **modelo estrella** sigue siendo la mejor forma de organizar datos analíticos: las consultas OLAP salen casi solas.
- `ROLLUP`, `CUBE` y `PIVOT` ahorran mucho código: los subtotales se calculan en la base de datos, no en Python.
- Con **GitHub Actions + MotherDuck + Streamlit Cloud** se tiene un pipeline de datos de punta a punta, gratis y sin AWS.

**¿Siguientes pasos?** Cargar datos reales (por ejemplo, de la Plataforma Nacional de Datos Abiertos del Perú), agregar dbt para las transformaciones o comparar el rendimiento con ClickHouse.

---

*Si te sirvió, deja tu 👏 y revisa el repositorio. ¡Gracias por leer!*
