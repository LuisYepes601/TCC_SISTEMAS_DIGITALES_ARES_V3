"""
core/services/system_service.py
Capa de servicios: métricas del sistema con caché y nuevos sensores.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Optional

from core.data.system_repository import (
    fetch_architecture,
    fetch_battery,
    fetch_boot_time,
    fetch_connections,
    fetch_cpu_count_logical,
    fetch_cpu_count_physical,
    fetch_cpu_freq,
    fetch_cpu_freq_per_core,
    fetch_cpu_name,
    fetch_cpu_percent,
    fetch_cpu_percent_per_core,
    fetch_cpu_times,
    fetch_disk,
    fetch_disk_io,
    fetch_disk_mount_choices,
    fetch_disks,
    fetch_fan_speeds,
    fetch_hostname,
    fetch_memory,
    fetch_memory_details,
    fetch_net_if_stats,
    fetch_network_interfaces,
    fetch_network_io,
    fetch_network_io_per_interface,
    fetch_os_info,
    fetch_process_count,
    fetch_ram_total_gb,
    fetch_temperatures,
    fetch_users,
)


# ---------------------------------------------------------------------------
# Caché con TTL (evita llamadas duplicadas en el mismo ciclo)
# ---------------------------------------------------------------------------
_CACHE: dict = {}
_CACHE_TTL = 0.8   # segundos


def _cached(key: str, fn, *args):
    now = time.time()
    if key in _CACHE:
        val, ts = _CACHE[key]
        if now - ts < _CACHE_TTL:
            return val
    val = fn(*args)
    _CACHE[key] = (val, now)
    return val


# ---------------------------------------------------------------------------
# CPU
# ---------------------------------------------------------------------------

def get_cpu_percent() -> float:
    return _cached("cpu_pct", fetch_cpu_percent)


def get_cpu_percent_per_core() -> list[float]:
    return _cached("cpu_cores", fetch_cpu_percent_per_core)


def get_cpu_freq() -> Optional[tuple[float, float, float]]:
    return _cached("cpu_freq", fetch_cpu_freq)


def get_cpu_freq_per_core() -> list:
    return _cached("cpu_freq_pc", fetch_cpu_freq_per_core)


def get_cpu_count_physical() -> int:
    return fetch_cpu_count_physical()


def get_cpu_count_logical() -> int:
    return fetch_cpu_count_logical()


def get_cpu_name() -> str:
    return fetch_cpu_name()


def get_cpu_times() -> dict:
    return _cached("cpu_times", fetch_cpu_times)


# ---------------------------------------------------------------------------
# Memoria
# ---------------------------------------------------------------------------

def get_memory_info() -> tuple[float, float, float]:
    return _cached("mem_info", fetch_memory)


def get_memory_details() -> dict:
    return _cached("mem_details", fetch_memory_details)


def get_ram_total_gb() -> float:
    return fetch_ram_total_gb()


# ---------------------------------------------------------------------------
# Disco
# ---------------------------------------------------------------------------

def get_disk_info(path: Optional[str] = None) -> tuple[float, float, float]:
    return fetch_disk(path)


def get_disk_io() -> dict:
    return _cached("disk_io", fetch_disk_io)


def get_disk_mount_choices() -> list[str]:
    return fetch_disk_mount_choices()


def get_disks() -> list[dict]:
    return _cached("disks", fetch_disks)


# ---------------------------------------------------------------------------
# Red
# ---------------------------------------------------------------------------

def get_network_io() -> tuple[int, int]:
    return _cached("net_io", fetch_network_io)


def get_network_io_per_interface() -> dict:
    return _cached("net_if_io", fetch_network_io_per_interface)


def get_network_interfaces() -> list[str]:
    return fetch_network_interfaces()


def get_net_if_stats() -> dict:
    return _cached("net_if_stats", fetch_net_if_stats)


def get_connections(kind: str = "inet") -> list[dict]:
    return fetch_connections(kind)


def compute_network_rates(
    prev_io: tuple[int, int],
    prev_time: float,
    wifi_max_mbps: float = 100.0,
) -> tuple[float, float, float, float]:
    sent, recv = fetch_network_io()
    now = time.perf_counter()
    if prev_time is not None and now > prev_time:
        el        = now - prev_time
        sent_rate = (sent - prev_io[0]) / el
        recv_rate = (recv - prev_io[1]) / el
        total_mbps = (sent_rate + recv_rate) * 8 / (1024 * 1024)
        wifi_pct   = min(100.0, (total_mbps / (wifi_max_mbps or 100.0)) * 100.0)
    else:
        sent_rate = recv_rate = total_mbps = wifi_pct = 0.0
    return sent_rate, recv_rate, total_mbps, wifi_pct


# ---------------------------------------------------------------------------
# Temperatura, batería y ventiladores
# ---------------------------------------------------------------------------

def get_temperatures() -> dict[str, list[dict]]:
    """Temperaturas de sensores. Vacío si no disponible en esta plataforma."""
    return _cached("temps", fetch_temperatures)


def get_battery() -> Optional[dict]:
    """Estado de batería. None si no es portátil o no está disponible."""
    return _cached("battery", fetch_battery)


def get_fan_speeds() -> dict[str, list[int]]:
    return _cached("fans", fetch_fan_speeds)


# ---------------------------------------------------------------------------
# Sistema / hardware
# ---------------------------------------------------------------------------

def get_hostname() -> str:
    return fetch_hostname()


def get_os_info() -> str:
    return fetch_os_info()


def get_architecture() -> str:
    return fetch_architecture()


def get_boot_time() -> Optional[datetime]:
    return fetch_boot_time()


def get_uptime_seconds() -> float:
    boot = fetch_boot_time()
    if not boot:
        return 0.0
    return (datetime.now() - boot).total_seconds()


def get_uptime_str() -> str:
    s = get_uptime_seconds()
    if s <= 0:
        return "—"
    d = int(s // 86400)
    h = int((s % 86400) // 3600)
    m = int((s % 3600) // 60)
    return f"{d}d {h:02d}:{m:02d}" if d > 0 else f"{h:02d}:{m:02d}"


def get_process_count() -> int:
    return fetch_process_count()


def get_users() -> list[dict]:
    return _cached("users", fetch_users)


def get_system_health_score(
    cpu_pct: float,
    mem_pct: float,
    disk_pct: float,
) -> tuple[float, str]:
    """
    Puntaje de salud del sistema 0–100.
    Penaliza uso por encima de umbrales razonables.
    """
    cpu_score  = max(0.0, 100.0 - max(0.0, cpu_pct  - 30.0) * 1.5)
    mem_score  = max(0.0, 100.0 - max(0.0, mem_pct  - 40.0) * 1.5)
    disk_score = max(0.0, 100.0 - max(0.0, disk_pct - 60.0) * 2.0)

    score = max(0.0, min(100.0, cpu_score * 0.4 + mem_score * 0.4 + disk_score * 0.2))

    if score >= 85:   desc = "Excelente"
    elif score >= 70: desc = "Bueno"
    elif score >= 50: desc = "Regular"
    elif score >= 30: desc = "Elevado"
    else:             desc = "Crítico"

    return score, desc
