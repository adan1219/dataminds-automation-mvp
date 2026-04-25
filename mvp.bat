@echo off
REM Activar entorno virtual
call .venv\Scripts\activate

REM Ejecutar la app de Streamlit
python -m streamlit run app.py

REM Mantener la ventana abierta al terminar
pause