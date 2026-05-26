"""core/services/alerts_service.py"""
from __future__ import annotations
import time
from dataclasses import dataclass
from core.data.alerts_repository import (Alert, AlertLevel, add_alert, count_active,
    dismiss_alert, dismiss_all, clear_all, fetch_alerts)

@dataclass
class AlertThresholds:
    cpu_warning: float = 75.0; cpu_critical: float = 90.0
    memory_warning: float = 80.0; memory_critical: float = 92.0
    disk_warning: float = 85.0; disk_critical: float = 95.0
    gpu_warning: float = 80.0; gpu_critical: float = 95.0

_thresholds = AlertThresholds()
_last_alert_key: dict[str, float] = {}
_DEDUP_SECONDS = 60.0

def get_thresholds(): return _thresholds
def update_thresholds(**kwargs):
    for k, v in kwargs.items():
        if hasattr(_thresholds, k): setattr(_thresholds, k, float(v))

def _check_threshold(category, value, resource_name, value_label):
    cat_base = category.split(":")[0]
    t = _thresholds
    warn_limit = getattr(t, f"{cat_base}_warning",  75.0)
    crit_limit = getattr(t, f"{cat_base}_critical", 90.0)
    if value >= crit_limit:   level = AlertLevel.CRITICAL; title = f"🔴 {resource_name} crítico"
    elif value >= warn_limit: level = AlertLevel.WARNING;  title = f"🟡 {resource_name} elevado"
    else:
        _last_alert_key.pop(f"{category}:{AlertLevel.WARNING}", None)
        _last_alert_key.pop(f"{category}:{AlertLevel.CRITICAL}", None)
        return None
    dedup_key = f"{category}:{level}"
    now = time.monotonic()
    if now - _last_alert_key.get(dedup_key, 0.0) < _DEDUP_SECONDS: return None
    _last_alert_key[dedup_key] = now
    msg = f"{value_label}: {value:.1f}% (umbral {level.value}: {crit_limit if level==AlertLevel.CRITICAL else warn_limit:.0f}%)"
    return add_alert(level, cat_base, title, msg)

def check_cpu(cpu_pct):    return _check_threshold("cpu", cpu_pct, "CPU", "% CPU")
def check_memory(mem_pct): return _check_threshold("memory", mem_pct, "Memoria", "% Memoria")
def check_disk(disk_pct, mountpoint="/"):
    return _check_threshold(f"disk:{mountpoint}", disk_pct, f"Disco ({mountpoint})", f"% Disco {mountpoint}")
def check_gpu(gpu_pct):
    if gpu_pct is None: return None
    return _check_threshold("gpu", gpu_pct, "GPU", "% GPU")
def check_all(cpu_pct, mem_pct, disk_pct, gpu_pct=None, disk_mountpoint="/"):
    return [a for a in [check_cpu(cpu_pct), check_memory(mem_pct),
                        check_disk(disk_pct, disk_mountpoint), check_gpu(gpu_pct)] if a]

def add_process_alert(title, message, level=AlertLevel.INFO):
    return add_alert(level, "process", title, message)
def get_alerts(*, include_dismissed=False): return fetch_alerts(include_dismissed=include_dismissed)
def get_active_count():   return count_active()
def get_critical_count(): return count_active(AlertLevel.CRITICAL)
def dismiss(alert): dismiss_alert(alert)
def dismiss_all_alerts(): dismiss_all()
def clear_alerts(): clear_all()
