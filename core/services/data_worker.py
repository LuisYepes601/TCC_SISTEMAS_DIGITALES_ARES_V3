"""
core/services/data_worker.py
Hilo de fondo único que recopila todas las métricas del sistema.

Un solo hilo reemplaza N timers de UI, eliminando el bloqueo del hilo principal
causado por llamadas repetidas a psutil. Cada pestaña se suscribe a las señales.
"""

from __future__ import annotations

import time
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal

from core.services.alerts_service import check_all, get_active_count
from core.services.gpu_service import get_gpu_info
from core.services.process_service import get_processes
from core.services.system_service import (
    get_cpu_freq,
    get_cpu_percent,
    get_cpu_percent_per_core,
    get_cpu_times,
    get_disk_info,
    get_disk_io,
    get_memory_details,
    get_memory_info,
    get_network_io,
    get_network_io_per_interface,
    get_process_count,
    get_system_health_score,
    get_temperatures,
    get_battery,
    get_uptime_str,
)


class MetricsWorker(QThread):
    """
    Hilo demonio que emite métricas del sistema cada segundo.

    Señales:
      system_ready    — dict con CPU, mem, disco, red, GPU, salud (1 s)
      processes_ready — list[dict] con todos los procesos (cada 3 s)
      net_if_ready    — dict por interfaz de red (cada 2 s)
    """

    system_ready    = pyqtSignal(dict)
    processes_ready = pyqtSignal(list)
    net_if_ready    = pyqtSignal(dict)

    FAST_S        = 1.0   # intervalo base
    PROC_EVERY_N  = 3     # procesos cada 3 ticks
    NET_IF_EVERY_N = 2    # interfaces cada 2 ticks

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDaemon(True)

        self.disk_path   = "/"
        self.wifi_max_mbps = 100.0

        self._running    = True
        self._paused     = False

        self._last_net   = (0, 0)
        self._last_net_t: Optional[float] = None

        # I/O disco anterior para calcular velocidad
        self._last_disk_io: Optional[dict] = None
        self._last_disk_t:  Optional[float] = None

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def stop(self) -> None:
        self._running = False

    def set_paused(self, paused: bool) -> None:
        self._paused = paused

    def update_disk_path(self, path: str) -> None:
        self.disk_path = path

    # ------------------------------------------------------------------
    # Bucle principal
    # ------------------------------------------------------------------

    def run(self) -> None:
        tick = 0
        while self._running:
            if not self._paused:
                try:
                    self._emit_system()
                except Exception:
                    pass

                if tick % self.PROC_EVERY_N == 0:
                    try:
                        self._emit_processes()
                    except Exception:
                        pass

                if tick % self.NET_IF_EVERY_N == 0:
                    try:
                        self._emit_net_if()
                    except Exception:
                        pass

            tick += 1
            time.sleep(self.FAST_S)

    # ------------------------------------------------------------------
    # Colectores privados
    # ------------------------------------------------------------------

    def _emit_system(self) -> None:
        now = time.perf_counter()

        cpu        = get_cpu_percent()
        cores      = get_cpu_percent_per_core()
        cpu_times  = get_cpu_times()
        freq       = get_cpu_freq()

        mem_pct, mu, mt = get_memory_info()
        mem_details     = get_memory_details()

        disk_pct, du, dt = get_disk_info(self.disk_path)

        # Velocidades I/O de disco (delta)
        disk_io   = get_disk_io()
        read_mbs  = write_mbs = 0.0
        if self._last_disk_io and self._last_disk_t:
            el = now - self._last_disk_t
            if el > 0:
                read_mbs  = (disk_io["read_bytes"]  - self._last_disk_io["read_bytes"])  / el / (1024 * 1024)
                write_mbs = (disk_io["write_bytes"] - self._last_disk_io["write_bytes"]) / el / (1024 * 1024)
        self._last_disk_io = disk_io
        self._last_disk_t  = now

        gpu_pct, gpu_name = get_gpu_info()

        # Velocidades de red (delta)
        sent, recv = get_network_io()
        sent_rate = recv_rate = total_mbps = wifi_pct = 0.0
        if self._last_net_t and now > self._last_net_t:
            el        = now - self._last_net_t
            sent_rate = (sent - self._last_net[0]) / el
            recv_rate = (recv - self._last_net[1]) / el
            total_mbps = (sent_rate + recv_rate) * 8 / (1024 * 1024)
            wifi_pct   = min(100.0, (total_mbps / (self.wifi_max_mbps or 100.0)) * 100.0)
        self._last_net   = (sent, recv)
        self._last_net_t = now

        score, hdesc = get_system_health_score(cpu, mem_pct, disk_pct)
        check_all(cpu, mem_pct, disk_pct, gpu_pct, self.disk_path)

        temps   = get_temperatures()
        battery = get_battery()

        self.system_ready.emit({
            # CPU
            "cpu":          cpu,
            "cpu_cores":    cores,
            "cpu_times":    cpu_times,
            "cpu_freq":     freq,
            # Memoria
            "mem_pct":      mem_pct,
            "mem_used":     mu,
            "mem_total":    mt,
            "mem_details":  mem_details,
            # Disco
            "disk_pct":     disk_pct,
            "disk_used":    du,
            "disk_total":   dt,
            "disk_path":    self.disk_path,
            "disk_io":      disk_io,
            "disk_read_mbs":  max(0.0, read_mbs),
            "disk_write_mbs": max(0.0, write_mbs),
            # GPU
            "gpu_pct":      gpu_pct,
            "gpu_name":     gpu_name,
            # Red
            "sent_rate":    sent_rate,
            "recv_rate":    recv_rate,
            "total_mbps":   total_mbps,
            "wifi_pct":     wifi_pct,
            # Salud
            "health_score": score,
            "health_desc":  hdesc,
            # Misc
            "uptime":       get_uptime_str(),
            "alert_count":  get_active_count(),
            "proc_count":   get_process_count(),
            # Hardware
            "temps":        temps,
            "battery":      battery,
        })

    def _emit_processes(self) -> None:
        procs = get_processes(sort_by="cpu")
        self.processes_ready.emit(procs)

    def _emit_net_if(self) -> None:
        data = get_network_io_per_interface()
        self.net_if_ready.emit(data)
