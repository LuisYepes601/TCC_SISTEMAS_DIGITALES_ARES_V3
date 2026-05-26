@echo off
title Ares v3.0
echo.
echo  +==========================================================+
echo  |   Administrador de Tareas Ares v3.0                     |
echo  +==========================================================+
echo.

python --version >nul 2>&1 || (echo ERROR: Python no instalado. && pause && exit /b 1)

if not exist "venv" (
    echo Creando entorno virtual...
    python -m venv venv
)
call venv\Scripts\activate.bat

python -c "import PyQt6" 2>nul || (
    echo Instalando dependencias...
    pip install --upgrade pip
    pip install -r requirements.txt
)

echo Iniciando Ares...
python main.py
pause
