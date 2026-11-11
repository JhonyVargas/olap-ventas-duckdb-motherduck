# Guion del video (máx. 5 minutos)

| Tiempo | Qué se muestra en pantalla | Qué decir |
|---|---|---|
| 0:00 – 0:20 | Dashboard abierto en la URL pública | "Hola, en este video les muestro cómo construí un cubo OLAP con DuckDB, MotherDuck y Streamlit, sin usar AWS." |
| 0:20 – 0:50 | README: diagrama de arquitectura | "Los datos se generan con Python, GitHub Actions los prueba y los carga a MotherDuck, que es DuckDB en la nube, y Streamlit Cloud publica el dashboard." |
| 0:50 – 1:30 | `sql/schema.sql` en VS Code | "Usé un modelo estrella: una tabla de hechos de ventas y cinco dimensiones: fecha, producto, región, cliente y canal. La vista v_ventas une todo y funciona como el cubo." |
| 1:30 – 2:00 | `etl/generar_datos.py` y `etl/db.py` | "Los datos simulan una cadena retail peruana con picos en Fiestas Patrias, Black Friday y Navidad. La misma conexión sirve para local o para la nube, según exista el token." |
| 2:00 – 2:45 | GitHub → pestaña Actions → ejecutar *Run workflow*; mostrar los jobs *pruebas* y *carga* y el resumen | "Esta es la automatización: en cada push y todos los días a las 6 de la mañana se ejecutan 8 pruebas y, si pasan, se recarga el cubo en MotherDuck." |
| 2:45 – 3:00 | MotherDuck web UI: base `olap_ventas` y una consulta `PIVOT` | "Aquí están las tablas ya cargadas en MotherDuck." |
| 3:00 – 4:30 | Dashboard: (1) cambiar Año → Mes (roll-up/drill-down); (2) bajar Tecnología → Laptops; (3) Slice Año = 2025; (4) filtros laterales Sur + Tecnología (dice); (5) Pivot y botón Rotar; (6) pestaña ROLLUP/CUBE y "Ver SQL" | Explicar cada operación OLAP mientras se hace clic. |
| 4:30 – 5:00 | Repo en GitHub | "El repositorio es público, el enlace está en la descripción junto con el artículo. ¡Gracias!" |

**Consejos de grabación:** OBS Studio o la Xbox Game Bar (Win + G), resolución 1080p, zoom del navegador al 110 %, y tener las pestañas abiertas antes de grabar.
