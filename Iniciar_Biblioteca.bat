@echo off
setlocal
cd /d "%~dp0"
python -c "import streamlit, pandas" >nul 2>&1
if errorlevel 1 (
    echo Instale o Python e as dependencias antes de iniciar:
    echo python -m pip install -r requirements.txt
    pause
    exit /b 1
)
python -m streamlit run app.py
if errorlevel 1 pause
