from __future__ import annotations

import re
import unicodedata

import pandas as pd

REQUIRED_COLUMNS = ["fecha", "monto"]
OPTIONAL_COLUMNS = ["producto", "cliente"]
ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}

COLUMN_ALIASES = {
    "fecha": {"fecha", "date", "order date", "sale date", "created_at", "timestamp", "fecha venta", "fecha de venta"},
    "monto": {"monto", "total", "amount", "importe", "ventas", "venta", "revenue", "price", "precio", "precio total", "total amount", "sales"},
    "producto": {"producto", "product", "item", "articulo", "artículo", "sku", "descripcion", "descripción"},
    "cliente": {"cliente", "customer", "client", "comprador", "buyer", "empresa", "company", "razon social", "razón social", "customer name", "client name"},
}


class ETLError(ValueError):
    """Error controlado de ETL para mensajes claros al usuario."""


def _normalize_text(value: str) -> str:
    text = str(value or "")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.replace("\n", " ").replace("_", " ").replace("-", " ")
    return re.sub(r"\s+", " ", text).strip().lower()


def _build_alias_lookup() -> dict[str, str]:
    lookup: dict[str, str] = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            lookup[_normalize_text(alias)] = canonical
    return lookup


_ALIAS_LOOKUP = _build_alias_lookup()


def read_any(df_or_file):
    if isinstance(df_or_file, pd.DataFrame):
        return df_or_file.copy()

    name = getattr(df_or_file, "name", "")
    ext = ("." + name.split(".")[-1].lower()) if "." in str(name) else ""
    if not ext or ext not in ALLOWED_EXTENSIONS:
        raise ETLError("Formato no soportado. Solo se permiten archivos .csv, .xlsx o .xls.")

    try:
        if ext == ".csv":
            return pd.read_csv(df_or_file)
        return pd.read_excel(df_or_file)
    except Exception as exc:
        raise ETLError("No se pudo leer el archivo. Verifica que no esté corrupto y que sea CSV/Excel válido.") from exc


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    mapped: dict[str, str] = {}
    used_targets: set[str] = set()
    for col in out.columns:
        canonical = _ALIAS_LOOKUP.get(_normalize_text(col))
        if canonical and canonical not in used_targets:
            mapped[col] = canonical
            used_targets.add(canonical)
    return out.rename(columns=mapped)


def _parse_fecha(value):
    if pd.isna(value):
        return pd.NaT
    text = str(value).strip()
    if not text:
        return pd.NaT

    if re.match(r"^\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2})?)?$", text):
        return pd.to_datetime(text, errors="coerce")

    if "/" in text:
        return pd.to_datetime(text, errors="coerce", dayfirst=True)

    first_num = re.match(r"^(\d{1,2})[-\s]", text)
    if first_num and int(first_num.group(1)) > 12:
        return pd.to_datetime(text, errors="coerce", dayfirst=True)

    parsed = pd.to_datetime(text, errors="coerce", dayfirst=False)
    if pd.isna(parsed):
        parsed = pd.to_datetime(text, errors="coerce", dayfirst=True)
    return parsed


def _parse_monto(value) -> float | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    if not text:
        return None

    negative_parentheses = text.startswith("(") and text.endswith(")")
    if negative_parentheses:
        text = text[1:-1].strip()

    text = text.upper()
    text = re.sub(r"\b(COP|MXN|USD)\b", "", text)
    text = re.sub(r"[\$€£]", "", text)
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[^0-9,\.\-]", "", text)

    if text in {"", "-"}:
        return None
    if text.count("-") > 1 or ("-" in text and not text.startswith("-")):
        return None

    comma = text.rfind(",")
    dot = text.rfind(".")

    if comma != -1 and dot != -1:
        if comma > dot:
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif comma != -1:
        right = text.split(",")[-1]
        text = text.replace(",", ".") if len(right) in (1, 2) else text.replace(",", "")
    elif dot != -1 and text.count(".") > 1:
        text = text.replace(".", "")
    elif dot != -1:
        right = text.split(".")[-1]
        if len(right) == 3 and text.replace(".", "").isdigit():
            text = text.replace(".", "")

    try:
        amount = float(text)
    except ValueError:
        return None

    if negative_parentheses and amount > 0:
        amount = -amount
    return amount


def coerce_types(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "fecha" in out.columns:
        out["fecha"] = out["fecha"].apply(_parse_fecha)
    if "monto" in out.columns:
        out["monto"] = pd.to_numeric(out["monto"].apply(_parse_monto), errors="coerce")
    for col in OPTIONAL_COLUMNS:
        if col in out.columns:
            out[col] = out[col].astype(str).str.strip().replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
    return out


def _validate_columns(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    cols = set(df.columns)
    missing_required = [c for c in REQUIRED_COLUMNS if c not in cols]
    if missing_required:
        errors.append(
            f"Faltan columnas obligatorias: {', '.join(missing_required)}. El archivo debe incluir al menos una columna de fecha y una columna de monto."
        )

    missing_optional = [c for c in OPTIONAL_COLUMNS if c not in cols]
    if missing_optional:
        warnings.append(
            f"Faltan columnas opcionales ({', '.join(missing_optional)}). Algunas gráficas o análisis pueden no mostrarse."
        )

    return errors, warnings


def clean_data(df_or_file) -> tuple[pd.DataFrame, list[str], list[str]]:
    df = read_any(df_or_file).dropna(how="all")
    df = normalize_columns(df)

    errors, warnings = _validate_columns(df)
    if errors:
        return pd.DataFrame(), errors, warnings

    df = coerce_types(df)
    invalid_dates = int(df["fecha"].isna().sum())
    invalid_amounts = int(df["monto"].isna().sum())

    df = df.dropna(subset=["fecha", "monto"]).reset_index(drop=True)

    if invalid_dates:
        warnings.append(f"Se descartaron {invalid_dates} filas con fecha inválida.")
    if invalid_amounts:
        warnings.append(f"Se descartaron {invalid_amounts} filas con monto inválido.")
    if df.empty:
        errors.append("No quedaron filas válidas tras la limpieza.")

    return df, errors, warnings


def compute_kpis(df: pd.DataFrame) -> dict:
    if df.empty or "monto" not in df.columns:
        return {"ventas_totales": 0.0, "ticket_promedio": 0.0, "n_transacciones": 0}

    kpis = {
        "ventas_totales": float(df["monto"].sum()),
        "n_transacciones": int(df.shape[0]),
        "ticket_promedio": float(df["monto"].mean()),
        "ticket_mediano": float(df["monto"].median()),
        "ticket_p95": float(df["monto"].quantile(0.95)),
        "venta_maxima": float(df["monto"].max()),
        "porcentaje_devoluciones": float((df["monto"] < 0).mean() * 100),
    }

    if "producto" in df.columns and df["producto"].notna().any():
        kpis["top_productos"] = df.groupby("producto", dropna=True)["monto"].sum().sort_values(ascending=False).head(5)
        kpis["productos_unicos"] = int(df["producto"].nunique(dropna=True))

    if "cliente" in df.columns and df["cliente"].notna().any():
        kpis["top_clientes"] = df.groupby("cliente", dropna=True)["monto"].sum().sort_values(ascending=False).head(5)
        kpis["clientes_unicos"] = int(df["cliente"].nunique(dropna=True))
        kpis["repeticion_clientes_pct"] = float((df.groupby("cliente", dropna=True)["monto"].size() >= 2).mean() * 100)

    if "fecha" in df.columns and df["fecha"].notna().any():
        monthly = df.set_index("fecha").resample("M")["monto"].sum().rename("monto")
        kpis["mensual"] = monthly
        if not monthly.empty:
            curr = float(monthly.iloc[-1])
            prev = float(monthly.iloc[-2]) if len(monthly) > 1 else 0.0
            kpis["ventas_mes_actual"] = curr
            kpis["ventas_mes_anterior"] = prev
            kpis["variacion_mom_pct"] = float((curr - prev) / prev * 100) if prev else None

        by_day = df.assign(dia=df["fecha"].dt.date).groupby("dia")["monto"].sum()
        if not by_day.empty:
            kpis["mejor_dia"] = str(by_day.idxmax())
            kpis["monto_mejor_dia"] = float(by_day.max())
            kpis["dias_activos"] = int(by_day.size)
            kpis["ventas_promedio_diaria"] = float(by_day.mean())

        hour = df.groupby(df["fecha"].dt.hour)["monto"].sum()
        if not hour.empty:
            kpis["hora_pico"] = int(hour.idxmax())

    return kpis


def prepare_heatmap(df: pd.DataFrame):
    if df.empty or "fecha" not in df.columns or "monto" not in df.columns:
        return None

    out = df.dropna(subset=["fecha", "monto"]).copy()
    if out.empty:
        return None

    out["dia_sem"] = out["fecha"].dt.day_name()
    out["hora"] = out["fecha"].dt.hour
    pivot = out.pivot_table(index="dia_sem", columns="hora", values="monto", aggfunc="sum").fillna(0.0)
    orden = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    return pivot.reindex(orden)
