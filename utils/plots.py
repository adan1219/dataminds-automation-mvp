import pandas as pd
import plotly.express as px

def monthly_line(series: pd.Series):
    if series is None or series.empty:
        return None
    # series viene con índice datetime (nombre suele ser 'fecha') y valor (p.ej. 'monto')
    df = series.reset_index()

    # Detectamos nombres reales de columnas tras reset_index()
    date_col = df.columns[0]   # normalmente 'fecha'
    val_col  = df.columns[1]   # normalmente 'monto'

    # Aseguramos tipo datetime y construimos una columna 'mes' (inicio del mes)
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df["mes"] = df[date_col].dt.to_period("M").dt.to_timestamp()

    fig = px.line(df, x="mes", y=val_col, markers=True, title="Ventas mensuales")
    fig.update_layout(xaxis_title="Mes", yaxis_title="Monto")
    return fig

def bar_top(series: pd.Series, title: str):
    if series is None or series.empty:
        return None
    df = series.reset_index()
    df.columns = ["item","monto"]
    fig = px.bar(df, x="item", y="monto", title=title)
    return fig

def pareto(series: pd.Series):
    if series is None or series.empty:
        return None
    df = series.reset_index()
    df.columns = ["item","monto"]
    df["cum_pct"] = (df["monto"].cumsum() / df["monto"].sum()) * 100
    fig = px.bar(df, x="item", y="monto", title="Pareto 80/20")
    fig.add_scatter(x=df["item"], y=df["cum_pct"], mode="lines+markers", yaxis="y2", name="% acumulado")
    fig.update_layout(
        yaxis2=dict(overlaying="y", side="right", range=[0,100], title="%")
    )
    return fig

def heatmap(df_pivot: pd.DataFrame):
    if df_pivot is None or df_pivot.empty:
        return None
    fig = px.imshow(df_pivot, aspect="auto", title="Heatmap por día-hora (monto)")
    return fig