"""
core/data/system_repository.py
Capa de datos: CPU, memoria, disco, red, temperatura, batería.
"""

from __future__ import annotations

import os
import platform
import socket
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import psutil


# ---------------------------------------------------------------------------
# CPU
# ---------------------------------------------------------------------------

def fetch_cpu_percent() -> float:
    return psutil.cpu_percent(interval=None)


def fetch_cpu_percent_per_core() -> list[float]:
    try:
        return psutil.cpu_percent(interval=None, percpu=True) or []
    except Exception:
        return []


def fetch_cpu_freq() -> Optional[tuple[float, float, float]]:
    try:
        f = psutil.cpu_freq()
        if f:
            return (f.current or 0.0, f.min or 0.0, f.max or 0.0)
    except Exception:
        pass
    return None


def fetch_cpu_freq_per_core() -> list[Optional[tuple[float, float, float]]]:
    try:
        freqs = psutil.cpu_freq(percpu=True)
        if freqs:
            return [(f.current, f.min, f.max) for f in freqs]
    except Exception:
        pass
    return []


def fetch_cpu_count_physical() -> int:
    return psutil.cpu_count(logical=False) or 0


def fetch_cpu_count_logical() -> int:
    return psutil.cpu_count(logical=True) or 0


def fetch_cpu_name() -> str:
    try:
        if platform.system() == "Darwin":
            import subprocess
            r = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True, text=True, timeout=2
            )
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
        if platform.system() == "Windows":
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                 r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
            name, _ = winreg.QueryValueEx(key, "ProcessorNameString")
            return name.strip()
    except Exception:
        pass
    return platform.processor() or "—"


def fetch_cpu_times() -> dict:
    try:
        t = psutil.cpu_times_percent(interval=None)
        return {
            "user":   getattr(t, "user",   0.0),
            "system": getattr(t, "system", 0.0),
            "idle":   getattr(t, "idle",   0.0),
            "iowait": getattr(t, "iowait", 0.0),
        }
    except Exception:
        return {"user": 0.0, "system": 0.0, "idle": 0.0, "iowait": 0.0}


# ---------------------------------------------------------------------------
# Temperatura y sensores
# ---------------------------------------------------------------------------

def fetch_temperatures() -> dict[str, list[dict]]:
    """
    Temperaturas de sensores de hardware.
    Funciona en Linux y parcialmente en macOS (con psutil ≥ 5.9).
    En Windows se requieren herramientas de terceros.
    """
    result: dict[str, list[dict]] = {}
    try:
        temps = psutil.sensors_temperatures()
        if not temps:
            return result
        for sensor_name, entries in temps.items():
            result[sensor_name] = [
                {
                    "label":    e.label or sensor_name,
                    "current":  round(e.current, 1),
                    "high":     round(e.high, 1) if e.high else None,
                    "critical": round(e.critical, 1) if e.critical else None,
                }
                for e in entries
            ]
    except (AttributeError, Exception):
        pass
    return result


def fetch_battery() -> Optional[dict]:
    """Estado de la batería (portátiles). None si no hay batería."""
    try:
        b = psutil.sensors_battery()
        if b is None:
            return None
        secs = b.secsleft
        if secs == psutil.POWER_TIME_UNLIMITED or secs == psutil.POWER_TIME_UNKNOWN:
            secs = -1
        return {
            "percent": round(b.percent, 1),
            "plugged": b.power_plugged,
            "secs_left": secs,
        }
    except (AttributeError, Exception):
        return None


def fetch_fan_speeds() -> dict[str, list[int]]:
    """Velocidades de ventiladores (RPM). Solo Linux/macOS."""
    result: dict[str, list[int]] = {}
    try:
        fans = psutil.sensors_fans()
        if fans:
            for name, entries in fans.items():
                result[name] = [e.current for e in entries]
    except (AttributeError, Exception):
        pass
    return result


# ---------------------------------------------------------------------------
# Memoria
# ---------------------------------------------------------------------------

def fetch_memory() -> tuple[float, float, float]:
    v = psutil.virtual_memory()
    return v.percent, v.used / (1024 ** 3), v.total / (1024 ** 3)


def fetch_memory_details() -> dict:
    v = psutil.virtual_memory()
    result = {
        "total_gb":     v.total     / (1024 ** 3),
        "available_gb": v.available / (1024 ** 3),
        "used_gb":      v.used      / (1024 ** 3),
        "percent":      v.percent,
        "cached_gb":    getattr(v, "cached",  0) / (1024 ** 3),
        "buffers_gb":   getattr(v, "buffers", 0) / (1024 ** 3),
        "shared_gb":    getattr(v, "shared",  0) / (1024 ** 3),
    }
    try:
        sw = psutil.swap_memory()
        result.update({
            "swap_total_gb": sw.total   / (1024 ** 3),
            "swap_used_gb":  sw.used    / (1024 ** 3),
            "swap_free_gb":  sw.free    / (1024 ** 3),
            "swap_percent":  sw.percent,
        })
    except Exception:
        result.update({"swap_total_gb": 0.0, "swap_used_gb": 0.0,
                        "swap_free_gb": 0.0,  "swap_percent": 0.0})
    return result


def fetch_ram_total_gb() -> float:
    try:
        return psutil.virtual_memory().total / (1024 ** 3)
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# Disco
# ---------------------------------------------------------------------------

def fetch_disk(path: Optional[str] = None) -> tuple[float, float, float]:
    if path is None:
        path = "C:\\" if os.name == "nt" else "/"
    if os.name == "nt":
        drive, _ = os.path.splitdrive(path)
        path = f"{drive.upper()}\\" if drive else "C:\\"
    d = psutil.disk_usage(path)
    return d.percent, d.used / (1024 ** 3), d.total / (1024 ** 3)


def fetch_disk_io() -> dict:
    try:
        io = psutil.disk_io_counters()
        if io:
            return {
                "read_bytes":  io.read_bytes,
                "write_bytes": io.write_bytes,
                "read_count":  io.read_count,
                "write_count": io.write_count,
                "read_time":   getattr(io, "read_time",  0),
                "write_time":  getattr(io, "write_time", 0),
            }
    except Exception:
        pass
    return {"read_bytes": 0, "write_bytes": 0, "read_count": 0,
            "write_count": 0, "read_time": 0, "write_time": 0}


def fetch_disk_mount_choices() -> list[str]:
    if os.name == "nt":
        drives: list[str] = []
        try:
            for part in psutil.disk_partitions(all=False):
                m = part.mountpoint
                if m and len(m) >= 2 and m[1] == ":":
                    drives.append(f"{m[0].upper()}:\\")
        except Exception:
            pass
        return sorted(set(drives)) or ["C:\\"]

    if sys.platform == "darwin":
        paths = ["/"]
        try:
            vol = Path("/Volumes")
            if vol.is_dir():
                for child in sorted(vol.iterdir()):
                    if not child.is_dir():
                        continue
                    try:
                        psutil.disk_usage(str(child))
                        paths.append(str(child))
                    except (PermissionError, OSError):
                        continue
        except OSError:
            pass
        return paths

    return ["/"]


def fetch_disks() -> list[dict]:
    result = []
    try:
        for part in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(part.mountpoint)
                result.append({
                    "mountpoint": part.mountpoint,
                    "device":     part.device,
                    "fstype":     part.fstype or "",
                    "total_gb":   usage.total / (1024 ** 3),
                    "used_gb":    usage.used  / (1024 ** 3),
                    "free_gb":    usage.free  / (1024 ** 3),
                    "percent":    usage.percent,
                })
            except (PermissionError, OSError):
                continue
    except Exception:
        pass
    return result


# ---------------------------------------------------------------------------
# Red
# ---------------------------------------------------------------------------

def fetch_network_io() -> tuple[int, int]:
    try:
        io = psutil.net_io_counters()
        return io.bytes_sent, io.bytes_recv
    except Exception:
        return 0, 0


def fetch_network_io_per_interface() -> dict[str, dict]:
    result: dict[str, dict] = {}
    try:
        for iface, c in (psutil.net_io_counters(pernic=True) or {}).items():
            result[iface] = {
                "bytes_sent":   c.bytes_sent,
                "bytes_recv":   c.bytes_recv,
                "packets_sent": c.packets_sent,
                "packets_recv": c.packets_recv,
                "errin":        c.errin,
                "errout":       c.errout,
                "dropin":       getattr(c, "dropin",  0),
                "dropout":      getattr(c, "dropout", 0),
            }
    except Exception:
        pass
    return result


def fetch_connections(kind: str = "inet") -> list[dict]:
    result = []
    try:
        for c in psutil.net_connections(kind=kind):
            laddr = f"{c.laddr.ip}:{c.laddr.port}" if c.laddr else "—"
            raddr = f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else "—"
            result.append({
                "laddr":  laddr,
                "raddr":  raddr,
                "status": c.status or "—",
                "pid":    c.pid or "—",
                "type":   "IPv6" if ":" in (c.laddr.ip if c.laddr else "") else "IPv4",
                "proto":  "TCP" if c.type and c.type.name == "SOCK_STREAM" else "UDP",
            })
    except (psutil.AccessDenied, PermissionError):
        pass
    return result


def fetch_network_interfaces() -> list[str]:
    try:
        return list(psutil.net_io_counters(pernic=True).keys())
    except Exception:
        return []


def fetch_net_if_stats() -> dict[str, dict]:
    """Velocidad máxima y estado de cada interfaz."""
    result: dict[str, dict] = {}
    try:
        for iface, stats in (psutil.net_if_stats() or {}).items():
            result[iface] = {
                "isup":  stats.isup,
                "speed": stats.speed,   # Mbit/s
                "duplex": str(stats.duplex).split(".")[-1],
                "mtu":   stats.mtu,
            }
    except Exception:
        pass
    return result


# ---------------------------------------------------------------------------
# Sistema / hardware
# ---------------------------------------------------------------------------

def fetch_hostname() -> str:
    try:
        return platform.node() or socket.gethostname() or "—"
    except Exception:
        return "—"


def fetch_os_info() -> str:
    try:
        return f"{platform.system()} {platform.release()} ({platform.version()})"
    except Exception:
        return "—"


def fetch_architecture() -> str:
    return platform.machine() or "—"


def fetch_boot_time() -> Optional[datetime]:
    try:
        return datetime.fromtimestamp(psutil.boot_time())
    except Exception:
        return None


def fetch_process_count() -> int:
    try:
        return len(psutil.pids())
    except Exception:
        return 0


def fetch_users() -> list[dict]:
    """Usuarios con sesión activa."""
    result = []
    try:
        for u in psutil.users():
            result.append({
                "name":     u.name,
                "terminal": u.terminal or "—",
                "host":     u.host or "local",
                "started":  datetime.fromtimestamp(u.started).strftime("%d/%m %H:%M"),
            })
    except Exception:
        pass
    return result
