"""core — Lógica de negocio."""
from core.services.process_service import get_processes, kill_process
from core.services.system_service import get_cpu_percent, get_memory_info, get_disk_info
__all__ = ["get_processes", "kill_process", "get_cpu_percent", "get_memory_info", "get_disk_info"]
