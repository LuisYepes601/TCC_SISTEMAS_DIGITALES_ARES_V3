"""
core/data/process_repository.py
Capa de datos: acceso a psutil para procesos del sistema.
v3: añade mem_mb (RSS real) y username por proceso.
"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Optional

import psutil


PRIORITY_MAP: dict[int, str] = {
    -20: "Tiempo Real",
    -10: "Alto",
      0: "Normal",
     10: "Bajo",
     19: "Muy Bajo",
}

NICE_PRESETS: dict[str, int] = {
    "Tiempo Real": -20,
    "Alto":        -10,
    "Normal":        0,
    "Bajo":         10,
    "Muy Bajo":     19,
}

# Atributos pedidos a psutil en un solo viaje (más eficiente)
_PROC_ATTRS = [
    "pid", "name", "cpu_percent", "memory_percent", "memory_info",
    "status", "nice", "num_threads", "username", "create_time",
]


# ---------------------------------------------------------------------------
# Lectura de procesos
# ---------------------------------------------------------------------------

def fetch_processes() -> list[dict]:
    """
    Lista completa de procesos. Minimiza syscalls pidiendo todos los
    atributos en un único process_iter().
    """
    result: list[dict] = []

    for proc in psutil.process_iter(_PROC_ATTRS):
        try:
            info = proc.info

            pid     = info.get("pid")
            name    = (info.get("name") or "")[:80]
            cpu     = info.get("cpu_percent") or 0.0
            mem_pct = info.get("memory_percent") or 0.0
            status  = info.get("status") or ""
            nice    = info.get("nice") or 0
            threads = info.get("num_threads") or 0

            mem_info = info.get("memory_info")
            mem_mb = (mem_info.rss / (1024 * 1024)) if mem_info else 0.0

            raw_user = info.get("username") or ""
            # En Windows puede venir "DOMINIO\\usuario" — quedarse solo con usuario
            username = raw_user.split("\\")[-1] if "\\" in raw_user else raw_user

            exe_path: Optional[str] = None
            try:
                exe_path = proc.exe()
            except (psutil.NoSuchProcess, psutil.AccessDenied, PermissionError):
                pass

            result.append({
                "pid":      pid,
                "name":     name,
                "cpu":      float(cpu),
                "memory":   float(mem_pct),
                "mem_mb":   float(mem_mb),
                "status":   status,
                "exe_path": exe_path,
                "nice":     nice,
                "threads":  threads,
                "user":     username,
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return result


def fetch_process_exe(pid: int) -> Optional[str]:
    try:
        return psutil.Process(pid).exe()
    except (psutil.NoSuchProcess, psutil.AccessDenied, PermissionError):
        return None


def fetch_process_details(pid: int) -> Optional[dict]:
    """Detalles ampliados: memoria, conexiones, hijos, I/O."""
    try:
        p = psutil.Process(pid)
        mem  = p.memory_info()
        children = p.children(recursive=False)

        # I/O de disco si está disponible
        io_read = io_write = 0
        try:
            io = p.io_counters()
            io_read  = io.read_bytes
            io_write = io.write_bytes
        except (psutil.AccessDenied, AttributeError, Exception):
            pass

        # Conexiones del proceso
        conn_count = 0
        try:
            conn_count = len(p.connections(kind="inet"))
        except (psutil.AccessDenied, Exception):
            pass

        return {
            "pid":          p.pid,
            "name":         p.name(),
            "status":       p.status(),
            "create_time":  p.create_time(),
            "cpu_times":    p.cpu_times(),
            "cpu_affinity": _safe(p.cpu_affinity),
            "mem_rss_mb":   mem.rss / (1024 ** 2),
            "mem_vms_mb":   mem.vms / (1024 ** 2),
            "mem_pct":      p.memory_percent(),
            "num_threads":  p.num_threads(),
            "children":     [c.pid for c in children],
            "username":     _safe(p.username),
            "cmdline":      _safe(lambda: " ".join(p.cmdline())),
            "io_read_mb":   io_read  / (1024 ** 2),
            "io_write_mb":  io_write / (1024 ** 2),
            "connections":  conn_count,
        }
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None


def _safe(fn):
    try:
        return fn() if callable(fn) else fn
    except Exception:
        return "—"


# ---------------------------------------------------------------------------
# Acciones
# ---------------------------------------------------------------------------

def terminate_process(pid: int) -> tuple[bool, str]:
    try:
        psutil.Process(pid).terminate()
        return True, "Proceso terminado correctamente."
    except psutil.NoSuchProcess:
        return False, "El proceso ya no existe."
    except psutil.AccessDenied:
        return False, f"Permisos insuficientes.\n\n{_access_denied_hint()}"
    except Exception as e:
        return False, str(e)


def kill_process_tree(pid: int) -> tuple[bool, str]:
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        for child in children:
            try:
                child.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        parent.kill()
        return True, f"Árbol terminado ({len(children) + 1} proceso(s))."
    except psutil.NoSuchProcess:
        return False, "El proceso ya no existe."
    except psutil.AccessDenied:
        return False, f"Permisos insuficientes.\n\n{_access_denied_hint()}"
    except Exception as e:
        return False, str(e)


def set_process_priority(pid: int, nice: int) -> tuple[bool, str]:
    try:
        psutil.Process(pid).nice(nice)
        return True, f"Prioridad cambiada (nice={nice})."
    except psutil.NoSuchProcess:
        return False, "El proceso ya no existe."
    except psutil.AccessDenied:
        return False, f"Permisos insuficientes.\n\n{_access_denied_hint()}"
    except Exception as e:
        return False, str(e)


def suspend_process(pid: int) -> tuple[bool, str]:
    try:
        psutil.Process(pid).suspend()
        return True, "Proceso suspendido."
    except psutil.NoSuchProcess:
        return False, "El proceso ya no existe."
    except psutil.AccessDenied:
        return False, "Permisos insuficientes."
    except Exception as e:
        return False, str(e)


def resume_process(pid: int) -> tuple[bool, str]:
    try:
        psutil.Process(pid).resume()
        return True, "Proceso reanudado."
    except psutil.NoSuchProcess:
        return False, "El proceso ya no existe."
    except psutil.AccessDenied:
        return False, "Permisos insuficientes."
    except Exception as e:
        return False, str(e)


def open_exe_folder(exe_path: str) -> tuple[bool, str]:
    if not exe_path or not os.path.isfile(exe_path):
        return False, "Ruta no válida."
    try:
        if os.name == "nt":
            subprocess.Popen(["explorer", "/select," + exe_path], shell=False)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", exe_path], shell=False)
        else:
            subprocess.Popen(["xdg-open", os.path.dirname(exe_path)])
        return True, "Ubicación abierta."
    except Exception as e:
        return False, str(e)


def _access_denied_hint() -> str:
    if sys.platform == "darwin":
        return "En macOS algunos procesos del sistema son inaccesibles."
    if os.name == "nt":
        return "Ejecuta Ares como administrador (clic derecho → Ejecutar como administrador)."
    return "Puede ser necesario ejecutar con permisos elevados."
