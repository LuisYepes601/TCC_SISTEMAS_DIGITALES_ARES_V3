"""tests/test_alerts_service.py"""
import pytest
from core.data.alerts_repository import AlertLevel, clear_all
from core.services.alerts_service import (
    add_process_alert, check_all, check_cpu, check_disk, check_gpu,
    check_memory, clear_alerts, dismiss_all_alerts, get_active_count,
    get_alerts, get_critical_count, get_thresholds, update_thresholds,
)

@pytest.fixture(autouse=True)
def clean():
    clear_all(); yield; clear_all()

def test_thresholds_exist():
    t = get_thresholds()
    assert hasattr(t, "cpu_warning") and hasattr(t, "cpu_critical")

def test_update_thresholds():
    update_thresholds(cpu_warning=60.0)
    assert get_thresholds().cpu_warning == 60.0

def test_cpu_below():
    update_thresholds(cpu_warning=75.0, cpu_critical=90.0)
    assert check_cpu(50.0) is None

def test_cpu_warning():
    update_thresholds(cpu_warning=75.0, cpu_critical=90.0)
    a = check_cpu(80.0)
    assert a is not None and a.level == AlertLevel.WARNING

def test_cpu_critical():
    update_thresholds(cpu_warning=75.0, cpu_critical=90.0)
    a = check_cpu(95.0)
    assert a is not None and a.level == AlertLevel.CRITICAL

def test_memory_warning():
    update_thresholds(memory_warning=80.0, memory_critical=92.0)
    a = check_memory(85.0)
    assert a is not None and a.level == AlertLevel.WARNING

def test_disk_ok():
    update_thresholds(disk_warning=85.0, disk_critical=95.0)
    assert check_disk(50.0, "/") is None

def test_gpu_none():   assert check_gpu(None) is None
def test_gpu_critical():
    update_thresholds(gpu_warning=80.0, gpu_critical=95.0)
    a = check_gpu(98.0)
    assert a is not None and a.level == AlertLevel.CRITICAL

def test_check_all_no_alerts():
    update_thresholds(cpu_warning=75.0, cpu_critical=90.0,
                      memory_warning=80.0, memory_critical=92.0,
                      disk_warning=85.0, disk_critical=95.0)
    assert check_all(10.0, 20.0, 30.0) == []

def test_process_alert():
    a = add_process_alert("Test", "Mensaje")
    assert a.category == "process"

def test_dismiss_all():
    add_process_alert("T", "M")
    assert get_active_count() > 0
    dismiss_all_alerts()
    assert get_active_count() == 0

def test_clear():
    add_process_alert("T", "M")
    clear_alerts()
    assert len(get_alerts(include_dismissed=True)) == 0

def test_dedup():
    update_thresholds(cpu_warning=5.0, cpu_critical=10.0)
    check_cpu(50.0)
    a2 = check_cpu(50.0)
    assert a2 is None
