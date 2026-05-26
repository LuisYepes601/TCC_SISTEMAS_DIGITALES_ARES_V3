"""core/utils/formatters.py"""
from datetime import datetime

def bytes_to_mb(b):    return f"{b/(1024*1024):.1f} MB"
def bytes_to_gb(b):    return f"{b/(1024**3):.2f} GB"
def bytes_per_sec_to_kb(bps): return f"{bps/1024:.1f} KB/s"
def bytes_per_sec_human(bps):
    if bps < 1024:       return f"{bps:.0f} B/s"
    if bps < 1024**2:    return f"{bps/1024:.1f} KB/s"
    if bps < 1024**3:    return f"{bps/(1024**2):.1f} MB/s"
    return f"{bps/(1024**3):.1f} GB/s"

def mhz_to_ghz_str(mhz): return f"{mhz/1000:.2f} GHz"
def cpu_freq_str(freq):
    if freq and freq[0]: return mhz_to_ghz_str(freq[0])
    return "—"

def health_color(score):
    if score >= 85: return "#22c55e"
    if score >= 70: return "#86efac"
    if score >= 50: return "#facc15"
    if score >= 30: return "#fb923c"
    return "#ef4444"

def pct_to_status_color(pct):
    if pct >= 90: return "#ef4444"
    if pct >= 75: return "#fb923c"
    if pct >= 50: return "#facc15"
    return "#22c55e"

def seconds_to_human(s):
    if s < 60:    return f"{s:.0f}s"
    if s < 3600:  return f"{s/60:.1f}min"
    if s < 86400: return f"{s/3600:.1f}h"
    return f"{s/86400:.1f}d"

def timestamp_str(dt):
    if dt is None: return "—"
    return dt.strftime("%d/%m/%Y %H:%M:%S")

_PS = {"running":"En ejecución","sleeping":"En reposo","disk-sleep":"Reposo en disco",
       "stopped":"Detenido","tracing-stop":"Detenido (trazas)","dead":"Terminado",
       "zombie":"Zombi","idle":"Inactivo","locked":"Bloqueado","waiting":"En espera","suspended":"Suspendido"}

PROCESS_FILTER_KEYS = ("running","sleeping","disk-sleep","stopped","zombie")

def process_status_label(raw):
    return _PS.get((raw or "").lower(), raw) if raw else "—"

def process_status_color(raw):
    return {"running":"#22c55e","sleeping":"#60a5fa","zombie":"#ef4444","stopped":"#f59e0b","dead":"#94a3b8"}.get((raw or "").lower(), "#94a3b8")

def nice_to_label(nice):
    if nice <= -10: return "Alto"
    if nice < 0:    return "Sobre normal"
    if nice == 0:   return "Normal"
    if nice <= 10:  return "Bajo"
    return "Muy Bajo"

_CS = {"ESTABLISHED":"Establecida","SYN_SENT":"SYN enviado","SYN_RECV":"SYN recibido",
       "FIN_WAIT1":"FIN espera 1","FIN_WAIT2":"FIN espera 2","TIME_WAIT":"Espera tiempo",
       "CLOSE":"Cerrada","CLOSE_WAIT":"Cierre pendiente","LAST_ACK":"Último ACK",
       "LISTEN":"Escuchando","LISTENING":"Escuchando","CLOSING":"Cerrando","NONE":"Ninguna"}

def connection_status_label(status):
    if not status or status in ("-","—"): return status or "—"
    return _CS.get(status.strip().upper(), status)

_SS = {"Running":"En ejecución","Stopped":"Detenido","Paused":"En pausa",
       "StartPending":"Iniciando","StopPending":"Deteniendo","ContinuePending":"Reanudando","PausePending":"Pausando"}

def service_status_label(status):
    return _SS.get((status or "").strip(), (status or "").strip())

def service_status_color(status):
    return {"Running":"#22c55e","Stopped":"#ef4444","Paused":"#f59e0b"}.get((status or "").strip(), "#94a3b8")
