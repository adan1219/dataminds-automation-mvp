import os, io, hashlib
import streamlit as st
import pandas as pd
import hashlib
from dotenv import load_dotenv

from utils.etl import clean_data, compute_kpis, prepare_heatmap
from utils.plots import monthly_line, bar_top, pareto, heatmap
from utils.pdf_report import create_report
from utils.ai_summary import summarize

load_dotenv()

st.set_page_config(page_title="DataMinds – Análisis Express", layout="wide")

# --- Auth simple por clave compartida ---
APP_SECRET = os.getenv("APP_SECRET", "")
if not APP_SECRET:
    st.warning("APP_SECRET no configurado. Define APP_SECRET en .env para proteger el acceso.")

def check_auth():
    if not APP_SECRET:
        return True
    if "auth_ok" in st.session_state and st.session_state["auth_ok"]:
        return True
    with st.sidebar:
        st.header("Acceso")
        key = st.text_input("Contraseña", type="password")
        if st.button("Entrar"):
            if key == APP_SECRET:
                st.session_state["auth_ok"] = True
                st.rerun()
            else:
                st.error("Contraseña incorrecta")
    return st.session_state.get("auth_ok", False)

if not check_auth():
    st.stop()

st.title("DataMinds – Subir → Procesar → Reporte")
st.caption("MVP: limpia tu archivo, calcula KPIs y genera un informe con IA.")

# --- Subida de archivo ---
uploaded = st.file_uploader("Sube tu archivo CSV o Excel", type=["csv","xlsx","xls"])
max_mb = 50
if uploaded and uploaded.size > max_mb * 1024 * 1024:
    st.error(f"Archivo supera {max_mb} MB.")
    st.stop()

@st.cache_data(show_spinner=False)
def process_file(file_bytes: bytes, file_name: str, file_hash: str):
    import io
    from utils.etl import clean_data, compute_kpis
    bio = io.BytesIO(file_bytes)
    bio.name = file_name  # para que ETL detecte CSV/Excel por extensión
    df, errs = clean_data(bio)
    kpis = compute_kpis(df) if errs == [] else {}
    return df, errs, kpis

if uploaded:
    file_bytes = uploaded.getvalue()
    file_name  = uploaded.name
    file_hash  = hashlib.md5(file_bytes).hexdigest()  # clave única por contenido

    df, errs, kpis = process_file(file_bytes, file_name, file_hash)

    # (Opcional de diagnóstico)
    st.caption(f"Archivo: {file_name}  |  Hash: {file_hash[:8]}…")

    if errs:
        st.error("Problemas detectados:")
        for e in errs:
            st.write("- ", e)
    else:
        st.success("Archivo válido ✓")
#aqui controlo el numeorro de filas maximo para mostrar
        with st.expander("Vista previa de datos", expanded=False):
            st.dataframe(df.head(100), use_container_width=True)


# === KPIs seleccionables (extendidos) ===
        
        # === KPIs seleccionables (catálogo dinámico) ===
        st.subheader("KPIs")

        def fmt_money(x): return f"$ {x:,.2f}" if x is not None else "–"
        def fmt_int(x):    return f"{int(x):,}" if x is not None else "–"
        def fmt_pct(x):    return f"{x:.1f} %"   if x is not None else "–"

        kpi_catalog = {
            "ventas_totales":            ("Ventas totales", fmt_money),
            "ventas_mes_actual":         ("Ventas mes actual", fmt_money),
            "ventas_mes_anterior":       ("Ventas mes anterior", fmt_money),
            "variacion_mom_pct":         ("% variación vs mes anterior", fmt_pct),
            "ticket_promedio":           ("Ticket promedio", fmt_money),
            "ticket_mediano":            ("Ticket mediano", fmt_money),
            "ticket_p95":                ("Ticket P95 (alto)", fmt_money),
            "n_transacciones":           ("# transacciones", fmt_int),
            "clientes_unicos":           ("Clientes únicos", fmt_int),
            "repeticion_clientes_pct":   ("% clientes repetidores", fmt_pct),
            "productos_unicos":          ("Productos únicos", fmt_int),
            "ventas_promedio_diaria":    ("Promedio diario", fmt_money),
            "dias_activos":              ("Días con ventas", fmt_int),
            "monto_mejor_dia":           ("Monto mejor día", fmt_money),
            "hora_pico":                 ("Hora pico (24h)", fmt_int),
            "venta_maxima":              ("Venta máxima", fmt_money),
            "porcentaje_devoluciones":   ("% devoluciones", fmt_pct),
        }

        default_keys = [
            "ventas_totales", "ventas_mes_actual", "variacion_mom_pct",
            "ticket_promedio", "n_transacciones", "clientes_unicos"
        ]

        with st.expander("Elegir KPIs a mostrar", expanded=True):
            available = [k for k in kpi_catalog if k in kpis]
            cols = st.columns(3)
            selections = {}
            for i, key in enumerate(available):
                label, _fmt = kpi_catalog[key]
                selections[key] = cols[i % 3].checkbox(label, value=(key in default_keys))

        # Render
        render_cols = st.columns(3)
        slot = 0
        for key, show in selections.items():
            if show:
                label, formatter = kpi_catalog[key]
                value = kpis.get(key)
                render_cols[slot % 3].metric(label, formatter(value))
                slot += 1

# === Gráficas seleccionables ===
        st.subheader("Gráficas")
        with st.expander("Elegir gráficas a mostrar", expanded=True):
            g1, g2, g3, g4 = st.columns(4)
            show_monthly = g1.checkbox("Línea mensual", value=True)
            show_top_prod = g2.checkbox("Top productos", value=True)
            show_pareto_cli = g3.checkbox("Pareto clientes", value=True)
            show_heat = g4.checkbox("Heatmap día-hora", value=True)

        # Renderizado condicional
        if show_monthly and "mensual" in kpis:
            fig1 = monthly_line(kpis["mensual"])
            if fig1:
                st.plotly_chart(fig1, use_container_width=True)

        if show_top_prod and "top_productos" in kpis:
            fig2 = bar_top(kpis["top_productos"], "Top productos por monto")
            if fig2:
                st.plotly_chart(fig2, use_container_width=True)

        if show_pareto_cli and "top_clientes" in kpis:
            fig3 = pareto(kpis["top_clientes"])
            if fig3:
                st.plotly_chart(fig3, use_container_width=True)

        if show_heat:
            heat = prepare_heatmap(df)
            fig4 = heatmap(heat)
            if fig4:
                st.plotly_chart(fig4, use_container_width=True)


        # Acciones: PDF + IA
        st.subheader("Exportables")

        modo = st.selectbox("Modo de resumen IA", ["Corto", "Extendido"], index=0)

        acciones_ai = None
        if os.getenv("OPENAI_API_KEY"):
            try:
                # Usa lo que tengas: KPIs + tops le dan contexto a la IA
                acciones_ai = summarize(
                    kpis=kpis,
                    top_productos=kpis.get("top_productos"),
                    top_clientes=kpis.get("top_clientes"),
                    mode="short" if modo == "Corto" else "long",
                )
            except Exception as e:
                st.warning(f"No se pudo generar el resumen con IA: {e}")

        # Texto final que irá al PDF (IA si hay, si no la plantilla fija)
        acciones_texto = acciones_ai or (
            "• Enfocar esfuerzos en top 3 productos.\n"
            "• Revisar clientes con caída vs. mes previo.\n"
            "• Optimizar tickets con bundles."
        )

        acciones = st.text_area(
            "Acciones sugeridas (se incluyen en el PDF)",
            value=acciones_texto,
            height=140,
        )

        if st.button("Generar PDF"):
            pdf_bytes = create_report(df, kpis, acciones, logo_path=None)  # o "assets/logo.png" si tienes logo
            st.download_button(
                "Descargar PDF",
                data=pdf_bytes,
                file_name="reporte.pdf",
                mime="application/pdf"
            )

else:
    st.info("Sube un archivo para comenzar. Formato mínimo: columnas `fecha`, `monto`, opcionales `producto`, `cliente`.")

st.caption("Privacidad: los archivos se procesan en memoria. Configura auto-borrado y logs en despliegue.")