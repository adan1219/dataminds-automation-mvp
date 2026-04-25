import os
from openai import OpenAI
import pandas as pd

from dotenv import load_dotenv
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def _shorten_series(x, n=5):
    # Convierte Series/DataFrame a texto breve y legible
    if isinstance(x, pd.Series):
        return x.head(n).to_dict()
    if isinstance(x, pd.DataFrame):
        return x.head(n).to_dict(orient="list")
    return x

def summarize(kpis=None, top_productos=None, top_clientes=None, mode="short"):
    """
    Genera un resumen con IA basado en KPIs, productos y clientes.
    mode: "short" (3 bullets) o "long" (texto más extenso)
    """
    # Prepara contexto
    kpis_txt = kpis if not isinstance(kpis, dict) else {k: float(v) if isinstance(v, (int, float)) else str(v) for k, v in kpis.items()}
    tp = _shorten_series(top_productos)
    tc = _shorten_series(top_clientes)

    context = (
        "Resumen de negocio\n"
        f"- KPIs: {kpis_txt}\n"
        f"- Top productos: {tp}\n"
        f"- Top clientes: {tc}\n"
    )

    prompt = f"""
A partir de la información siguiente:

{context}

Entregá {'exactamente 3 recomendaciones breves, numeradas y accionables' if mode=='short' else 'un análisis breve (5-8 líneas) y 3-5 recomendaciones accionables, numeradas'}.
Usa lenguaje claro, sin tecnicismos innecesarios.
"""

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Eres un analista financiero para PyMEs, directo y accionable."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=220 if mode == "short" else 420,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        # Devuelve un mensaje claro si falla la API
        return f"[Error al generar resumen con IA: {e}]"