"""tests/test_system_service.py"""
import pytest
from core.services.system_service import (
    get_architecture, get_battery, get_boot_time, get_cpu_count_logical,
    get_cpu_count_physical, get_cpu_freq, get_cpu_name, get_cpu_percent,
    get_cpu_percent_per_core, get_cpu_times, get_disk_info, get_disk_io,
    get_disk_mount_choices, get_disks, get_hostname, get_memory_details,
    get_memory_info, get_network_io, get_os_info, get_process_count,
    get_ram_total_gb, get_system_health_score, get_temperatures,
    get_uptime_seconds, get_uptime_str,
)

def test_cpu_percent():   assert 0.0 <= get_cpu_percent() <= 100.0
def test_cpu_cores():
    for c in get_cpu_percent_per_core(): assert 0.0 <= c <= 100.0
def test_cpu_counts():
    p, l = get_cpu_count_physical(), get_cpu_count_logical()
    assert p >= 0 and l >= 0
    if p > 0: assert l >= p
def test_cpu_name():      assert isinstance(get_cpu_name(), str) and get_cpu_name()
def test_cpu_times():
    t = get_cpu_times()
    for k in ("user","system","idle"): assert k in t and t[k] >= 0

def test_memory_info():
    pct, used, total = get_memory_info()
    assert 0.0 <= pct <= 100.0 and total > 0 and 0 <= used <= total

def test_memory_details():
    d = get_memory_details()
    for k in ("total_gb","available_gb","used_gb","percent"): assert k in d
    assert d["available_gb"] <= d["total_gb"]

def test_disk_info():
    pct, used, total = get_disk_info()
    assert total > 0 and 0 <= used <= total

def test_disk_io():
    io = get_disk_io()
    for k in ("read_bytes","write_bytes"): assert io[k] >= 0

def test_disk_choices():  assert len(get_disk_mount_choices()) >= 1
def test_get_disks():
    for d in get_disks():
        assert "mountpoint" in d and d["total_gb"] >= 0

def test_network_io():
    s, r = get_network_io()
    assert s >= 0 and r >= 0

def test_hostname():      assert get_hostname() != ""
def test_os_info():       assert get_os_info() != ""
def test_architecture():  assert get_architecture() != ""
def test_uptime():
    assert get_uptime_seconds() >= 0
    assert get_uptime_str() != ""

def test_process_count(): assert get_process_count() > 0
def test_ram_total():     assert get_ram_total_gb() > 0

@pytest.mark.parametrize("cpu,mem,disk,lo,hi", [
    (10,20,30, 70,100), (80,85,70, 0,60), (100,100,100, 0,30),
])
def test_health_score(cpu, mem, disk, lo, hi):
    score, desc = get_system_health_score(cpu, mem, disk)
    assert lo <= score <= hi
    assert desc in ("Excelente","Bueno","Regular","Elevado","Crítico")

def test_temperatures():  assert isinstance(get_temperatures(), dict)
def test_battery():
    b = get_battery()
    if b is not None:
        assert 0 <= b["percent"] <= 100
        assert isinstance(b["plugged"], bool)
