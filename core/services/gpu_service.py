"""core/services/gpu_service.py"""
from typing import Optional
from core.data.gpu_repository import fetch_gpu_info
def get_gpu_info() -> tuple[Optional[float], str]:
    pct, name = fetch_gpu_info()
    return pct, name or "GPU no disponible"
def gpu_usage_available(pct) -> bool: return pct is not None
