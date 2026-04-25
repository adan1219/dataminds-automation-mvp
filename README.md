# DataMinds MVP – Subir → Procesar → Reporte

MVP funcional en Streamlit con subida de archivo, limpieza básica, KPIs, gráficas, PDF simple y resumen IA.

## Stack
- UI: Streamlit
- ETL: Pandas
- Gráficas: Plotly
- IA: OpenAI (resumen)
- Metadatos: SQLite (opcional, futuro)
- Hosting: Render/Railway

## Estructura
```
dataminds_mvp/
├── app.py
├── requirements.txt
├── .env.example
└── utils/
    ├── etl.py
    ├── plots.py
    ├── pdf_report.py
    └── ai_summary.py
```

## Variables de entorno
Crea un archivo `.env` a partir de `.env.example`:
```
APP_SECRET="cambia-esta-clave"
OPENAI_API_KEY="sk-..."
```

## Ejecutar local
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Despliegue en Render (modo rápido)
1. Crea repositorio en GitHub y sube estos archivos.
2. En Render, crea un **Web Service**:
   - Runtime: Python 3.11+
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`
3. Añade variables de entorno: `APP_SECRET`, `OPENAI_API_KEY`.
4. Activa Deploy on Push.
5. Abre la URL; usa la contraseña definida en `APP_SECRET`.

## Dataset mínimo esperado
CSV/XLSX con columnas: `fecha`, `producto`, `cliente`, `monto`.
- `fecha`: formato YYYY-MM-DD o similar (se intenta parsear automáticamente).
- `monto`: número.
- `producto`, `cliente`: texto.