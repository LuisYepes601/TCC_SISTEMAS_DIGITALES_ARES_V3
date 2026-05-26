# ⚙ Administrador de Tareas Ares v3.0

Monitor avanzado de procesos del sistema — rápido, detallado y sin dependencias de IA.
Compatible con **Windows** y **macOS**.

---

## ✨ Novedades v3.0

### ⚡ Rendimiento 3-5× mayor
- **MetricsWorker** — un único hilo de fondo reemplaza N timers de UI.  
  Las pestañas se suscriben a señales Qt y nunca bloquean el hilo principal.
- **ProcessModel** (`QAbstractTableModel`) — vista virtualizada: solo se renderizan  
  las filas visibles. Sin `QTableWidgetItem` por celda → 90 % menos allocations.
- **Caché con TTL** en la capa de servicios evita llamadas duplicadas a psutil.
- Intervalos diferenciados: métricas del sistema cada 1 s, procesos cada 3 s.

### 🌡 Sensores de hardware
- Temperaturas de CPU/GPU en tiempo real (Linux y parcialmente macOS/Windows)
- Estado de batería con porcentaje y tiempo restante (portátiles)
- Velocidades de ventiladores en RPM
- Todo visible en la pestaña **Sistema**

### 📊 Procesos más detallados
| Campo nuevo | Descripción |
|-------------|-------------|
| **Mem MB**  | Uso real de RAM en megabytes (RSS) |
| **Usuario** | Cuenta de usuario propietaria del proceso |
| I/O Disco   | MB leídos/escritos (en diálogo de detalles) |
| Conexiones  | Nº de sockets abiertos por proceso |

### 🌐 Red mejorada
- Gráfico en tiempo real de envío/recepción (con área rellena)
- Tabla de interfaces con estado, velocidad y tasas por adaptador
- Contador de conexiones TCP/UDP activas en vivo
- Etiquetas de velocidad instantánea (KB/s o MB/s)

### 🖥 Sistema completo
- RAM con desglose: usado, libre, swap, caché, búferes
- Barra de uso de RAM con color dinámico
- Sesiones de usuarios activos
- Discos con barras de uso individuales

---

## 🏗 Arquitectura

```
┌─────────────────────────────────────────────────────────┐
│  PRESENTACIÓN  (ui/)                                    │
│  main_window.py         Ventana + MetricsWorker         │
│  tabs/                  Pestañas (suscritas a señales)  │
│  models/process_model.py  QAbstractTableModel           │
│  widgets/, styles/      Componentes y temas QSS         │
├─────────────────────────────────────────────────────────┤
│  SERVICIOS  (core/services/)                            │
│  data_worker.py   ← NUEVO: hilo único de métricas       │
│  system_service.py     CPU, RAM, disco, red, sensores   │
│  process_service.py    Procesos + I/O + usuario         │
│  alerts_service.py     Umbrales + deduplicación         │
│  gpu_service.py        Detección NVIDIA/AMD/Intel       │
├─────────────────────────────────────────────────────────┤
│  DATOS  (core/data/)                                    │
│  system_repository.py  psutil + temps + batería + fans  │
│  process_repository.py psutil (mem_mb, username, I/O)   │
│  alerts_repository.py  Almacén en memoria               │
│  gpu_repository.py     nvidia-smi / typeperf / profiler │
└─────────────────────────────────────────────────────────┘
```

---

## 📱 Pestañas

| Pestaña | Descripción |
|---------|-------------|
| ⚡ **Procesos** | Tabla virtualizada · CPU, Mem %, Mem MB, usuario, I/O · Filtros combinados |
| 📊 **Rendimiento** | Gráficos CPU/RAM/Disco/Red/GPU · Barras por núcleo · I/O de disco |
| 🌐 **Red** | Gráfico tráfico en vivo · Tabla por interfaz · Conexiones activas |
| 🖥 **Sistema** | Temps · Batería · Ventiladores · RAM detallada · Usuarios · Discos |
| 🔔 **Alertas** | Umbrales configurables · Deduplicación · Historial |
| ⚙ **Servicios** | *(solo Windows)* Iniciar/detener con permisos de admin |

---

## 🚀 Instalación

### macOS / Linux
```bash
git clone https://github.com/tu-usuario/ares.git && cd ares
chmod +x run.sh && ./run.sh
```

### Windows
```powershell
# Doble clic en run.bat  — o desde PowerShell:
.\run.bat
```

### Manual
```bash
python3 -m venv venv && source venv/bin/activate   # venv\Scripts\activate en Windows
pip install -r requirements.txt
python main.py
```

---

## 📋 Requisitos

| Requisito | Versión |
|-----------|---------|
| Python    | ≥ 3.10  |
| SO        | Windows 10+ · macOS 10.14+ |
| RAM       | ~80 MB en reposo |

**Sin `anthropic`** — Ares v3.0 no requiere API keys ni conexión a internet.

---

## 🧪 Tests

```bash
pip install -r requirements-dev.txt
pytest            # ejecutar toda la suite
pytest -v         # salida detallada
pytest -k cpu     # solo tests de CPU
```

---

## 🔧 Diagnóstico rápido

| Síntoma | Solución |
|---------|----------|
| GPU no aparece | Instala drivers NVIDIA/AMD actualizados |
| "Access Denied" en procesos | Ejecutar como Administrador (Windows) |
| Temperaturas no disponibles | Normal en macOS/Windows sin drivers especiales |
| Servicios no aparecen | Solo disponible en Windows como Administrador |

---

## 📄 Licencia · MIT
