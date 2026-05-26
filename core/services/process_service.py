"""core/services/process_service.py — Gestión de procesos."""
import csv, io
from core.data.process_repository import (
    NICE_PRESETS, fetch_process_details, fetch_processes, fetch_process_exe,
    kill_process_tree, open_exe_folder, resume_process,
    set_process_priority, suspend_process, terminate_process,
)

SORT_BY_CPU    = "cpu"
SORT_BY_MEMORY = "memory"
SORT_BY_NAME   = "name"
SORT_BY_PID    = "pid"

def get_processes(sort_by: str = SORT_BY_CPU) -> list[dict]:
    processes = fetch_processes()
    if sort_by == SORT_BY_CPU:      processes.sort(key=lambda x: x["cpu"],    reverse=True)
    elif sort_by == SORT_BY_MEMORY: processes.sort(key=lambda x: x["memory"], reverse=True)
    elif sort_by == SORT_BY_NAME:   processes.sort(key=lambda x: (x["name"] or "").lower())
    else:                           processes.sort(key=lambda x: x["pid"] or 0)
    return processes

def get_process_exe_path(pid): return fetch_process_exe(pid)
def get_process_details(pid):  return fetch_process_details(pid)
def kill_process(pid):         return terminate_process(pid)
def kill_process_and_children(pid): return kill_process_tree(pid)
def change_priority(pid, label):
    nice = NICE_PRESETS.get(label)
    if nice is None: return False, f"Prioridad desconocida: '{label}'"
    return set_process_priority(pid, nice)
def suspend(pid):  return suspend_process(pid)
def resume(pid):   return resume_process(pid)
def open_process_folder(path): return open_exe_folder(path)
def get_priority_options():    return list(NICE_PRESETS.keys())
def export_processes_csv() -> str:
    processes = get_processes(sort_by=SORT_BY_CPU)
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["pid","name","cpu","memory","mem_mb","status","threads","nice","user"], extrasaction="ignore")
    writer.writeheader(); writer.writerows(processes)
    return output.getvalue()
def get_top_processes(n=5, by=SORT_BY_CPU): return get_processes(sort_by=by)[:n]
