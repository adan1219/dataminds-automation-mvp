from __future__ import annotations
import pandas as pd
import numpy as np

REQUIRED_COLUMNS = ["fecha", "monto"]
OPTIONAL_COLUMNS = ["producto", "cliente"]

def read_any(df_or_file):
    if isinstance(df_or_file, pd.DataFrame):
        return df_or_file.copy()
    name = getattr(df_or_file, "name", "")
    if name.lower().endswith(".csv"):
        return pd.read_csv(df_or_file)
    return pd.read_excel(df_or_file)

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lower().replace("\n"," ").replace("  "," ") for c in df.columns]
    rename_map = {
    # fechas
    "date": "fecha", "fecha venta": "fecha", "fechas": "fecha",
    "order date": "fecha",
    # montos
    "amount": "monto", "importe": "monto", "total": "monto",
    "subtotal": "monto", "precio total": "monto", "sales": "monto",
    "valor": "monto", "precio": "monto", "coste": "monto", "ventas": "monto",
    # producto / cliente
    "producto/servicio": "producto", "articulo": "producto", "item": "producto",
    "sku": "producto", "customer": "cliente", "cliente/razon social": "cliente",
    "razon social": "cliente", "company": "cliente",
}
    df = df.rename(columns={k:v for k,v in rename_map.items() if k in df.columns})
    return df

def coerce_types(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "fecha" in df.columns:
        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce", dayfirst=False, infer_datetime_format=True)
    if "monto" in df.columns:
        s = df["monto"].astype(str).str.strip()

        # quita espacios y símbolos de moneda comunes
        s = s.str.replace(r"\s+", "", regex=True)
        s = s.str.replace(r"[\$€£]", "", regex=True)

        # decide separador decimal por mayoría: si hay más comas que puntos, asume decimal=coma
        comma_ct = s.str.count(",").sum()
        dot_ct   = s.str.count("\.").sum()

        if comma_ct > dot_ct:
            # estilo español: "1.234,56" -> "1234.56"
            s = s.str.replace(r"\.", "", regex=True)      # quita miles
            s = s.str.replace(",", ".", regex=False)      # decimal a punto
        else:
            # estilo inglés: "1,234.56" -> "1234.56"
            s = s.str.replace(",", "", regex=False)       # quita miles

        df["monto"] = pd.to_numeric(s, errors="coerce")
        for col in ["producto", "cliente"]:
            if col in df.columns:
             df[col] = df[col].astype(str).str.strip()
    return df

def validate(df: pd.DataFrame) -> list[str]:
    errors = []
    cols = set(df.columns)
    missing = [c for c in REQUIRED_COLUMNS if c not in cols]
    if missing:
        errors.append(f"Faltan columnas obligatorias: {missing}")
    if "fecha" in cols and df["fecha"].isna().all():
        errors.append("Todas las fechas son inválidas o vacías.")
    if "monto" in cols and df["monto"].isna().all():
        errors.append("Todos los montos son inválidos o vacíos.")
    if "monto" in cols and (df["monto"] < 0).any():
        errors.append("Hay montos negativos. Verifica devoluciones/abonos.")
    return errors

def clean_data(df_or_file) -> tuple[pd.DataFrame, list[str]]:
    df = read_any(df_or_file)
    df = normalize_columns(df)
    df = coerce_types(df)
    errs = validate(df)
    # drop obvious junk rows
    if "fecha" in df.columns:
        df = df.dropna(subset=["fecha"])
    if "monto" in df.columns:
        df = df.dropna(subset=["monto"])
    df = df.reset_index(drop=True)
    return df, errs

def compute_kpis(df: pd.DataFrame) -> dict:
    kpis = {}
    if df.empty:
        return {"ventas_totales": 0, "ticket_promedio": 0, "n_transacciones": 0}

    # ===== KPIs base =====
    kpis["ventas_totales"] = float(df["monto"].sum())
    kpis["n_transacciones"] = int(df.shape[0])
    kpis["ticket_promedio"] = float(df["monto"].mean())
    kpis["ticket_mediano"] = float(df["monto"].median())
    kpis["ticket_p95"] = float(df["monto"].quantile(0.95))

    if "producto" in df.columns:
        kpis["top_productos"] = df.groupby("producto")["monto"].sum().sort_values(ascending=False).head(5)
        kpis["productos_unicos"] = int(df["producto"].nunique())

    if "cliente" in df.columns:
        kpis["top_clientes"] = df.groupby("cliente")["monto"].sum().sort_values(ascending=False).head(5)
        kpis["clientes_unicos"] = int(df["cliente"].nunique())
        kpis["repeticion_clientes_pct"] = float((df.groupby("cliente")["monto"].size() >= 2).mean() * 100)

    # Serie mensual para gráficas + MoM
    if "fecha" in df.columns:
        monthly = df.set_index("fecha").resample("M")["monto"].sum().rename("monto")
        kpis["mensual"] = monthly
        if not monthly.empty:
            ventas_mes_actual = float(monthly.iloc[-1])
            ventas_mes_anterior = float(monthly.shift(1).iloc[-1]) if monthly.size >= 2 else 0.0
            kpis["ventas_mes_actual"] = ventas_mes_actual
            kpis["ventas_mes_anterior"] = ventas_mes_anterior
            kpis["variacion_mom_pct"] = float(((ventas_mes_actual - ventas_mes_anterior) / ventas_mes_anterior * 100)
                                              if ventas_mes_anterior > 0 else None)

        # Día/hora
        by_day = df.copy()
        by_day["dia"] = by_day["fecha"].dt.date
        dia_sum = by_day.groupby("dia")["monto"].sum()
        if not dia_sum.empty:
            kpis["mejor_dia"] = str(dia_sum.idxmax())
            kpis["monto_mejor_dia"] = float(dia_sum.max())
            kpis["dias_activos"] = int(dia_sum.size)
            kpis["ventas_promedio_diaria"] = float(dia_sum.mean())

        hora_sum = df.groupby(df["fecha"].dt.hour)["monto"].sum()
        if not hora_sum.empty:
            kpis["hora_pico"] = int(hora_sum.idxmax())

    # ===== Ejemplos de KPIs NUEVOS fáciles =====
    # Mayor venta individual y % de devoluciones si hubiera montos negativos
    kpis["venta_maxima"] = float(df["monto"].max())
    neg = (df["monto"] < 0).mean() * 100
    kpis["porcentaje_devoluciones"] = float(neg)
    kpis = {}
    if df.empty: 
        return {"ventas_totales": 0, "ticket_promedio": 0, "n_transacciones": 0}

    # KPIs base
    kpis["ventas_totales"] = float(df["monto"].sum())
    kpis["n_transacciones"] = int(df.shape[0])
    kpis["ticket_promedio"] = float(df["monto"].mean())

    if "producto" in df.columns:
        kpis["top_productos"] = df.groupby("producto")["monto"].sum().sort_values(ascending=False).head(5)
        kpis["productos_unicos"] = int(df["producto"].nunique())

    if "cliente" in df.columns:
        kpis["top_clientes"] = df.groupby("cliente")["monto"].sum().sort_values(ascending=False).head(5)
        kpis["clientes_unicos"] = int(df["cliente"].nunique())
        # % de repetición: clientes con 2+ compras
        rep = (df.groupby("cliente")["monto"].size() >= 2).mean() * 100
        kpis["repeticion_clientes_pct"] = float(rep)

    # Serie mensual (para línea)
    if "fecha" in df.columns:
        monthly = df.set_index("fecha").resample("M")["monto"].sum().rename("monto")
        kpis["mensual"] = monthly

        # Mes actual vs anterior (MoM)
        if not monthly.empty:
            last_month = monthly.index.max()
            prev_month = (last_month - pd.offsets.MonthBegin(1))
            ventas_mes_actual = float(monthly.loc[last_month])
            ventas_mes_anterior = float(monthly.shift(1).loc[last_month]) if last_month in monthly.index else 0.0
            kpis["ventas_mes_actual"] = ventas_mes_actual
            kpis["ventas_mes_anterior"] = ventas_mes_anterior
            kpis["variacion_mom_pct"] = float(((ventas_mes_actual - ventas_mes_anterior) / ventas_mes_anterior * 100) if ventas_mes_anterior > 0 else None)

        # KPIs por día/hora
        by_day = df.copy()
        by_day["dia"] = by_day["fecha"].dt.date
        dia_sum = by_day.groupby("dia")["monto"].sum()
        if not dia_sum.empty:
            best_day = dia_sum.idxmax()
            kpis["mejor_dia"] = str(best_day)
            kpis["monto_mejor_dia"] = float(dia_sum.max())
            kpis["dias_activos"] = int(dia_sum.size)
            kpis["ventas_promedio_diaria"] = float(dia_sum.mean())

        if df["fecha"].dt.hour.notna().any():
            hora_sum = df.groupby(df["fecha"].dt.hour)["monto"].sum()
            if not hora_sum.empty:
                kpis["hora_pico"] = int(hora_sum.idxmax())

    # Distribución de tickets
    kpis["ticket_mediano"] = float(df["monto"].median())
    kpis["ticket_p95"] = float(df["monto"].quantile(0.95))

    return kpis


def prepare_heatmap(df: pd.DataFrame):
    df = df.copy()
    if "fecha" not in df.columns:
        return None
    df["dia_sem"] = df["fecha"].dt.day_name()
    df["hora"] = df["fecha"].dt.hour
    pivot = df.pivot_table(index="dia_sem", columns="hora", values="monto", aggfunc="sum").fillna(0.0)
    # Reordenar días para vista más natural (Lunes a Domingo)
    orden = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    pivot = pivot.reindex(orden)
    return pivot