#!/bin/bash
echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║   Administrador de Tareas Ares v3.0                 ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

command -v python3 &>/dev/null || { echo "ERROR: Python 3 no encontrado."; exit 1; }

if [ ! -d "venv" ]; then
    echo "Creando entorno virtual..."
    python3 -m venv venv || { echo "ERROR: No se pudo crear venv"; exit 1; }
fi

source venv/bin/activate

python3 -c "import PyQt6" 2>/dev/null || {
    echo "Instalando dependencias (primera vez)..."
    pip install --upgrade pip -q
    pip install -r requirements.txt
}

echo "Iniciando Ares..."
python3 main.py
