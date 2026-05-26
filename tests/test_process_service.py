"""tests/test_process_service.py"""
import pytest
from core.services.process_service import (
    get_processes, get_priority_options, get_top_processes,
    SORT_BY_CPU, SORT_BY_MEMORY, SORT_BY_NAME, SORT_BY_PID,
    kill_process, kill_process_and_children, change_priority, suspend, resume,
)

def test_get_processes_returns_list():
    assert isinstance(get_processes(), list)

def test_get_processes_fields():
    required = {"pid","name","cpu","memory","mem_mb","status","exe_path","nice","threads","user"}
    for p in get_processes():
        for f in required:
            assert f in p, f"Campo '{f}' faltante"

def test_get_processes_types():
    for p in get_processes():
        assert isinstance(p["cpu"], float)
        assert isinstance(p["memory"], float)
        assert isinstance(p["mem_mb"], float)

def test_get_processes_cpu_range():
    for p in get_processes():
        assert 0.0 <= p["cpu"] <= 100.0
        assert 0.0 <= p["memory"] <= 100.0
        assert p["mem_mb"] >= 0.0

def test_sorted_by_cpu():
    procs = get_processes(sort_by=SORT_BY_CPU)
    if len(procs) >= 2: assert procs[0]["cpu"] >= procs[1]["cpu"]

def test_sorted_by_memory():
    procs = get_processes(sort_by=SORT_BY_MEMORY)
    if len(procs) >= 2: assert procs[0]["memory"] >= procs[1]["memory"]

def test_sorted_by_name():
    procs = get_processes(sort_by=SORT_BY_NAME)
    if len(procs) >= 2:
        assert (procs[0]["name"] or "").lower() <= (procs[1]["name"] or "").lower()

def test_top_processes_count():  assert len(get_top_processes(n=3)) <= 3
def test_top_processes_sorted():
    top = get_top_processes(n=5, by=SORT_BY_CPU)
    if len(top) >= 2: assert top[0]["cpu"] >= top[1]["cpu"]

def test_priority_options():
    opts = get_priority_options()
    assert isinstance(opts, list)
    assert {"Normal","Alto","Bajo","Muy Bajo","Tiempo Real"}.issubset(set(opts))

def test_kill_nonexistent():
    ok, msg = kill_process(999_999_999)
    assert ok is False and isinstance(msg, str)

def test_kill_tree_nonexistent():
    ok, _ = kill_process_and_children(999_999_999)
    assert ok is False

def test_change_priority_invalid():
    ok, msg = change_priority(1, "PrioridadInexistente")
    assert ok is False and "desconocida" in msg

def test_suspend_nonexistent():
    ok, _ = suspend(999_999_999)
    assert ok is False

def test_resume_nonexistent():
    ok, _ = resume(999_999_999)
    assert ok is False
