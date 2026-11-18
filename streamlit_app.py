"""Dashboard OLAP de ventas: DuckDB + MotherDuck + Streamlit.

Operaciones OLAP demostradas: roll-up, drill-down, slice, dice, pivot,
y los operadores SQL ROLLUP / CUBE.
"""
from __future__ import annotations

import os

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st

from etl.db import DB_NAME, LOCAL_DB_PATH, get_connection

st.set_page_config(page_title="Cubo OLAP de Ventas", page_icon="🧊", layout="wide")

# ---------------------------------------------------------------- paleta
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
SECUENCIAL = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
COLORES = {  # el color sigue a la entidad, no a su posición
    "categoria": dict(zip(["Tecnología", "Muebles", "Oficina", "Hogar"], SERIES)),
    "macroregion": dict(zip(["Lima", "Norte", "Centro", "Sur", "Oriente"], SERIES)),
    "canal": dict(zip(["Tienda física", "Online", "Marketplace"], SERIES)),
    "segmento": dict(zip(["Consumidor", "Pyme", "Corporativo"], SERIES)),
}
MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
DIAS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]

DIMENSIONES = {
    "Año": "anio", "Trimestre": "trimestre", "Mes": "mes", "Día de la semana": "dia_semana",
    "Macroregión": "macroregion", "Departamento": "departamento",
    "Categoría": "categoria", "Subcategoría": "subcategoria", "Producto": "producto",
    "Canal": "canal", "Segmento": "segmento",
}
MEDIDAS = {
    "Ventas (S/)": "sum(monto_venta)::DOUBLE",
    "Ganancia (S/)": "sum(ganancia)::DOUBLE",
    "Unidades": "sum(cantidad)::DOUBLE",
    "N° de ventas": "count(*)::DOUBLE",
    "Margen (%)": "(100.0 * sum(ganancia) / nullif(sum(monto_venta), 0))::DOUBLE",
    "Ticket promedio (S/)": "avg(monto_venta)::DOUBLE",
}


def estilo(fig, alto: int = 380, leyenda: bool = True):
    fig.update_layout(
        height=alto, margin=dict(l=80, r=16, t=84 if leyenda else 48, b=56),
        paper_bgcolor="#fcfcfb", plot_bgcolor="#fcfcfb",
        font=dict(family="system-ui, -apple-system, 'Segoe UI', sans-serif", color="#0b0b0b", size=13),
        title=dict(x=0, xanchor="left", font=dict(size=15)), legend_title_text="", showlegend=leyenda,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        bargap=0.35, barcornerradius=4, hoverlabel=dict(bgcolor="white"),
    )
    # autotypenumbers="strict": textos como "2023" se tratan como categorías, no como números
    # (si no, Plotly dibuja un eje numérico con medios años: 2022.5, 2023.5...)
    fig.update_xaxes(automargin=True, showgrid=False, linecolor="#c3c2b7", tickfont_color="#52514e",
                     title_font_color="#52514e", autotypenumbers="strict")
    fig.update_yaxes(automargin=True, gridcolor="#e1e0d9", zeroline=False, tickformat="~s", tickfont_color="#52514e",
                     title_font_color="#52514e", autotypenumbers="strict")
    return fig


def soles(x: float) -> str:
    if abs(x) >= 1e6:
        return f"S/ {x / 1e6:,.2f} M"
    if abs(x) >= 1e3:
        return f"S/ {x / 1e3:,.1f} mil"
    return f"S/ {x:,.0f}"


def mostrar(fig):
    st.plotly_chart(fig, width="stretch", theme=None)


def etiquetar(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """Convierte códigos numéricos de mes/día en nombres (manteniendo el orden)."""
    if col == "mes":
        df[col] = pd.Categorical([MESES[m - 1] for m in df[col]], categories=MESES, ordered=True)
    elif col == "dia_semana":
        df[col] = pd.Categorical([DIAS[d - 1] for d in df[col]], categories=DIAS, ordered=True)
    elif col == "trimestre":
        df[col] = "T" + df[col].astype(str)
    elif col == "anio":
        df[col] = df[col].astype(str)
    return df


# ---------------------------------------------------------------- conexión
def _token() -> str | None:
    try:
        token = st.secrets.get("MOTHERDUCK_TOKEN")
    except Exception:  # no hay secrets.toml
        token = None
    return token or os.getenv("MOTHERDUCK_TOKEN")


@st.cache_resource(show_spinner="Conectando al cubo OLAP…")
def conexion() -> tuple[duckdb.DuckDBPyConnection, str]:
    token = _token()
    if token:
        return get_connection(token=token), f"MotherDuck · md:{DB_NAME}"

    # Sin token: base local (solo lectura). Si aún no existe, se construye al vuelo.
    if LOCAL_DB_PATH.exists():
        con = duckdb.connect(str(LOCAL_DB_PATH), read_only=True)
        if con.execute("SELECT count(*) FROM information_schema.tables "
                       "WHERE table_name = 'fact_ventas'").fetchone()[0]:
            return con, "DuckDB local"
        con.close()
    from etl.generar_datos import generar
    from etl.pipeline import cargar
    con = get_connection(local_path=LOCAL_DB_PATH)
    cargar(con, generar())
    return con, "DuckDB local"


@st.cache_data(ttl=600, show_spinner=False)
def consultar(sql: str, params: dict | None = None) -> pd.DataFrame:
    con, _ = conexion()
    return con.cursor().execute(sql, params or {}).df()


# ---------------------------------------------------------------- filtros (DICE)
con, origen = conexion()
valores = {
    col: consultar(f"SELECT DISTINCT {col} FROM v_ventas ORDER BY 1")[col].tolist()
    for col in ["anio", "macroregion", "categoria", "canal", "segmento"]
}

with st.sidebar:
    st.header("🎲 Dice (filtros)")
    st.caption("Selecciona varios valores en varias dimensiones a la vez para obtener un sub-cubo.")
    filtros = {
        "anio": st.multiselect("Año", valores["anio"], default=valores["anio"]),
        "macroregion": st.multiselect("Macroregión", valores["macroregion"], placeholder="Todas"),
        "categoria": st.multiselect("Categoría", valores["categoria"], placeholder="Todas"),
        "canal": st.multiselect("Canal", valores["canal"], placeholder="Todas"),
        "segmento": st.multiselect("Segmento", valores["segmento"], placeholder="Todas"),
    }
    st.caption("Vacío = todos los valores.")
    st.divider()
    st.caption(f"Fuente de datos: **{origen}**")
    if st.button("🔄 Refrescar datos"):
        st.cache_data.clear()
        st.rerun()

condiciones = [f"list_contains(${col}, {col})" for col, sel in filtros.items() if sel]
WHERE = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""
PARAMS = {col: sel for col, sel in filtros.items() if sel}

# ---------------------------------------------------------------- encabezado + KPIs
st.title("🧊 Cubo OLAP de Ventas Retail · Perú")
st.caption("Modelo estrella en DuckDB/MotherDuck · ETL automatizado con GitHub Actions · Dashboard en Streamlit")

kpi = consultar(f"""
    SELECT sum(monto_venta)::DOUBLE AS ventas, sum(ganancia)::DOUBLE AS ganancia,
           sum(cantidad)::DOUBLE AS unidades, count(*) AS n, avg(monto_venta)::DOUBLE AS ticket,
           max(fecha) AS ultima
    FROM v_ventas {WHERE}""", PARAMS).iloc[0]

if not kpi["n"]:
    st.warning("No hay datos para la combinación de filtros elegida.")
    st.stop()

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Ventas", soles(kpi["ventas"]), help=f"S/ {kpi['ventas']:,.2f}")
c2.metric("Ganancia", soles(kpi["ganancia"]), help=f"S/ {kpi['ganancia']:,.2f}")
c3.metric("Margen", f"{100 * kpi['ganancia'] / kpi['ventas']:.1f} %")
c4.metric("N° de ventas", f"{kpi['n']:,}")
c5.metric("Ticket promedio", f"S/ {kpi['ticket']:,.0f}")
st.caption(f"Datos hasta el {pd.Timestamp(kpi['ultima']):%d/%m/%Y}")

tab_tiempo, tab_prod, tab_slice, tab_pivot, tab_sql = st.tabs([
    "📈 Roll-up / Drill-down (tiempo)", "🔍 Drill-down (producto)", "🔪 Slice", "🔄 Pivot", "🧮 ROLLUP / CUBE",
])

# ---------------------------------------------------------------- 1. tiempo
with tab_tiempo:
    st.markdown("**Roll-up** sube en la jerarquía (Día → Mes → Trimestre → Año) agregando los datos; "
                "**drill-down** baja para ver más detalle.")
    a, b = st.columns([2, 1])
    nivel = a.radio("Nivel de la jerarquía de tiempo", ["Año", "Trimestre", "Mes", "Día"], index=2, horizontal=True)
    medida = b.selectbox("Medida", list(MEDIDAS), key="medida_tiempo")
    en_curso = st.checkbox("Incluir periodo en curso (incompleto)", value=False,
                           help="Los datos se cargan a diario, así que el último mes/trimestre/año aún no termina.")

    periodo = {
        "Año": "CAST(anio AS VARCHAR)",
        "Trimestre": "anio || '-T' || trimestre",
        "Mes": "strftime(date_trunc('month', fecha), '%Y-%m')",
        "Día": "CAST(fecha AS VARCHAR)",
    }[nivel]
    unidad = {"Año": "year", "Trimestre": "quarter", "Mes": "month"}.get(nivel)
    corte = (f"fecha < date_trunc('{unidad}', (SELECT max(fecha) + 1 FROM v_ventas))"
             if unidad and not en_curso else "")
    where_t = " AND ".join(x for x in [WHERE.removeprefix("WHERE "), corte] if x)
    where_t = f"WHERE {where_t}" if where_t else ""
    sql = f"""SELECT {periodo} AS periodo, {MEDIDAS[medida]} AS valor
FROM v_ventas {where_t}
GROUP BY periodo ORDER BY periodo"""
    df = consultar(sql, PARAMS)
    if nivel in ("Año", "Trimestre"):
        fig = px.bar(df, x="periodo", y="valor", color_discrete_sequence=SERIES)
    else:
        fig = px.line(df, x="periodo", y="valor", color_discrete_sequence=SERIES)
        fig.update_traces(line_width=2)
    fig.update_traces(hovertemplate="%{x}<br>" + medida + ": %{y:,.0f}<extra></extra>")
    mostrar(estilo(fig.update_layout(title=f"{medida} por {nivel.lower()}", xaxis_title="", yaxis_title=medida),
                   leyenda=False))
    with st.expander("Ver SQL"):
        st.code(sql, language="sql")

    st.markdown("**Estacionalidad:** cada año desglosado por mes (drill-down Año → Mes).")
    corte_mes = "" if en_curso else "fecha < date_trunc('month', (SELECT max(fecha) + 1 FROM v_ventas))"
    where_mes = " AND ".join(x for x in [WHERE.removeprefix("WHERE "), corte_mes] if x)
    where_mes = f"WHERE {where_mes}" if where_mes else ""
    est = etiquetar(consultar(f"""SELECT anio, mes, {MEDIDAS[medida]} AS valor
        FROM v_ventas {where_mes} GROUP BY anio, mes ORDER BY anio, mes""", PARAMS), "mes")
    est["anio"] = est["anio"].astype(str)
    fig = px.line(est, x="mes", y="valor", color="anio", markers=True, color_discrete_sequence=SERIES)
    fig.update_traces(line_width=2, marker_size=8,
                      hovertemplate="%{x} %{fullData.name}<br>" + medida + ": %{y:,.0f}<extra></extra>")
    mostrar(estilo(fig.update_layout(title=f"{medida} por mes y año", xaxis_title="", yaxis_title=medida)))

# ---------------------------------------------------------------- 2. producto
with tab_prod:
    st.markdown("Jerarquía de producto: **Categoría → Subcategoría → Producto**. "
                "Elige un valor para bajar (drill-down) o deja *Todas* para subir (roll-up).")
    a, b, c = st.columns(3)
    medida_p = c.selectbox("Medida", list(MEDIDAS), key="medida_prod")
    cats = ["(Todas)"] + valores["categoria"]
    cat = a.selectbox("Categoría", cats)
    params_p = dict(PARAMS)
    extra = []
    if cat != "(Todas)":
        params_p["cat_sel"] = cat
        extra.append("categoria = $cat_sel")
        subcats = consultar("SELECT DISTINCT subcategoria FROM v_ventas WHERE categoria = $c ORDER BY 1",
                            {"c": cat})["subcategoria"].tolist()
        sub = b.selectbox("Subcategoría", ["(Todas)"] + subcats)
    else:
        sub = b.selectbox("Subcategoría", ["(Todas)"], disabled=True)
    if sub != "(Todas)":
        params_p["sub_sel"] = sub
        extra.append("subcategoria = $sub_sel")

    nivel_p = "producto" if sub != "(Todas)" else ("subcategoria" if cat != "(Todas)" else "categoria")
    clausulas = condiciones + extra
    where_p = ("WHERE " + " AND ".join(clausulas)) if clausulas else ""
    sql = f"""SELECT {nivel_p}, {MEDIDAS[medida_p]} AS valor
FROM v_ventas {where_p}
GROUP BY {nivel_p} ORDER BY valor DESC"""
    df = consultar(sql, params_p)
    color = COLORES["categoria"].get(cat, SERIES[0])
    fig = px.bar(df, x="valor", y=nivel_p, orientation="h", color_discrete_sequence=[color])
    fig.update_traces(hovertemplate="%{y}<br>" + medida_p + ": %{x:,.0f}<extra></extra>")
    fig.update_yaxes(autorange="reversed", title="")
    ruta = " › ".join(x for x in ["Todas", cat if cat != "(Todas)" else "", sub if sub != "(Todas)" else ""] if x)
    mostrar(estilo(fig.update_layout(title=f"{medida_p} · {ruta}", xaxis_title=medida_p),
                   alto=max(300, 42 * len(df) + 80), leyenda=False))
    with st.expander("Ver SQL"):
        st.code(sql, language="sql")

# ---------------------------------------------------------------- 3. slice
with tab_slice:
    st.markdown("**Slice** fija **una** dimensión en **un solo valor** y analiza la \"rebanada\" resultante del cubo.")
    a, b, c = st.columns(3)
    dim_slice = a.selectbox("Dimensión a fijar", ["Año", "Macroregión", "Categoría", "Canal", "Segmento"])
    col_slice = DIMENSIONES[dim_slice]
    valor_slice = b.selectbox("Valor", valores[col_slice], index=len(valores[col_slice]) - 1
                              if col_slice == "anio" else 0)
    medida_s = c.selectbox("Medida", list(MEDIDAS), key="medida_slice")

    opciones = [d for d in ["Macroregión", "Categoría", "Canal", "Segmento"] if d != dim_slice]
    a, b = st.columns(2)
    eje = a.selectbox("Desglosar por", ["Departamento"] + opciones)
    # Un departamento pertenece a una sola macroregión: colorear por ella no aporta.
    color_dim = b.selectbox("Color por", [d for d in opciones if d != eje
                                          and not (eje == "Departamento" and d == "Macroregión")])
    col_eje, col_color = DIMENSIONES[eje], DIMENSIONES[color_dim]

    sql = f"""SELECT {col_eje}, {col_color}, {MEDIDAS[medida_s]} AS valor
FROM v_ventas
WHERE {col_slice} = $valor_slice   -- el corte (slice)
GROUP BY ALL ORDER BY valor DESC"""
    df = consultar(sql, {"valor_slice": valor_slice})
    orden = df.groupby(col_eje)["valor"].sum().sort_values(ascending=False).index.tolist()
    aditiva = medida_s not in ("Margen (%)", "Ticket promedio (S/)")
    fig = px.bar(df, x=col_eje, y="valor", color=col_color, barmode="stack" if aditiva else "group",
                 color_discrete_map=COLORES.get(col_color), color_discrete_sequence=SERIES,
                 category_orders={col_eje: orden, col_color: list(COLORES.get(col_color, {}))})
    fig.update_traces(hovertemplate="%{x} · %{fullData.name}<br>" + medida_s + ": %{y:,.0f}<extra></extra>",
                      marker_line_color="#fcfcfb", marker_line_width=2)
    mostrar(estilo(fig.update_layout(title=f"{medida_s} · {dim_slice} = {valor_slice}",
                                     xaxis_title="", yaxis_title=medida_s), alto=420))
    st.caption("Nota: el slice ignora los filtros de la barra lateral para mostrar la rebanada completa.")
    with st.expander("Ver SQL"):
        st.code(sql.replace("$valor_slice", f"'{valor_slice}'"), language="sql")

# ---------------------------------------------------------------- 4. pivot
with tab_pivot:
    st.markdown("**Pivot** rota el cubo: elige qué dimensión va en filas y cuál en columnas.")
    a, b, c, d = st.columns([3, 3, 3, 2], vertical_alignment="bottom")
    filas = a.selectbox("Filas", list(DIMENSIONES), index=list(DIMENSIONES).index("Macroregión"))
    columnas = b.selectbox("Columnas", [x for x in DIMENSIONES if x != filas],
                           index=[x for x in DIMENSIONES if x != filas].index("Categoría")
                           if filas != "Categoría" else 0)
    medida_v = c.selectbox("Medida", list(MEDIDAS), key="medida_pivot")
    rotar = d.toggle("Rotar", help="Intercambia filas y columnas")
    if rotar:
        filas, columnas = columnas, filas
    fcol, ccol = DIMENSIONES[filas], DIMENSIONES[columnas]

    sql = f"""SELECT {fcol}, {ccol}, {MEDIDAS[medida_v]} AS valor
FROM v_ventas {WHERE}
GROUP BY ALL"""
    df = consultar(sql, PARAMS)
    df = etiquetar(etiquetar(df, fcol), ccol)
    tabla = df.pivot_table(index=fcol, columns=ccol, values="valor", aggfunc="sum", observed=True)
    tabla.index.name, tabla.columns.name = filas, columnas

    fig = px.imshow(tabla, color_continuous_scale=SECUENCIAL, aspect="auto",
                    labels=dict(color=medida_v))
    fig.update_traces(hovertemplate=f"{filas}: %{{y}}<br>{columnas}: %{{x}}<br>{medida_v}: %{{z:,.0f}}<extra></extra>",
                      xgap=2, ygap=2)
    mostrar(estilo(fig.update_layout(title=f"{medida_v}: {filas} × {columnas}"),
                   alto=max(320, 30 * len(tabla) + 140)))
    st.dataframe(tabla.style.format("{:,.0f}", na_rep="–"), width="stretch")
    with st.expander("Ver SQL (y su equivalente con PIVOT nativo de DuckDB)"):
        st.code(sql, language="sql")
        st.code(f"PIVOT v_ventas ON {ccol} USING {MEDIDAS[medida_v].split('::')[0]} GROUP BY {fcol};", language="sql")

# ---------------------------------------------------------------- 5. ROLLUP / CUBE
with tab_sql:
    st.markdown("SQL tiene operadores OLAP nativos que calculan **subtotales** y **totales generales** en una sola consulta.")
    a, b = st.columns(2)

    sql_rollup = f"""SELECT
  CASE WHEN GROUPING(anio) = 1 THEN 'TOTAL' ELSE CAST(anio AS VARCHAR) END AS "Año",
  CASE WHEN GROUPING(anio) = 1 THEN ''
       WHEN GROUPING(trimestre) = 1 THEN 'Subtotal'
       ELSE 'T' || trimestre END                                   AS "Periodo",
  sum(monto_venta)::DOUBLE AS "Ventas (S/)",
  sum(ganancia)::DOUBLE    AS "Ganancia (S/)"
FROM v_ventas {WHERE}
GROUP BY ROLLUP (anio, trimestre)
ORDER BY GROUPING(anio), anio, GROUPING(trimestre), trimestre"""
    with a:
        st.subheader("GROUP BY ROLLUP")
        st.caption("Jerarquía Año → Trimestre con subtotal por año y total general.")
        st.dataframe(consultar(sql_rollup, PARAMS).style.format({"Ventas (S/)": "{:,.0f}", "Ganancia (S/)": "{:,.0f}"}),
                     width="stretch", hide_index=True, height=420)
        st.code(sql_rollup, language="sql")

    sql_cube = f"""SELECT
  coalesce(macroregion, '(Todas)') AS "Macroregión",
  coalesce(canal, '(Todos)')       AS "Canal",
  sum(monto_venta)::DOUBLE         AS "Ventas (S/)",
  count(*)                         AS "N° ventas"
FROM v_ventas {WHERE}
GROUP BY CUBE (macroregion, canal)
ORDER BY GROUPING(macroregion), macroregion, GROUPING(canal), canal"""
    with b:
        st.subheader("GROUP BY CUBE")
        st.caption("Todas las combinaciones posibles de Macroregión × Canal, incluidos los totales.")
        st.dataframe(consultar(sql_cube, PARAMS).style.format({"Ventas (S/)": "{:,.0f}", "N° ventas": "{:,}"}),
                     width="stretch", hide_index=True, height=420)
        st.code(sql_cube, language="sql")
