"""core/data/gpu_repository.py — GPU detection."""
import os, platform, subprocess
from typing import Optional

def _run(cmd, timeout=2.0):
    try:
        kw = {"capture_output": True, "text": True, "timeout": timeout}
        if os.name == "nt": kw["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        return subprocess.run(cmd, **kw)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError): return None

def _nvidia_smi():
    out = _run(["nvidia-smi","--query-gpu=utilization.gpu,name","--format=csv,noheader,nounits"])
    if not out or out.returncode != 0 or not out.stdout.strip(): return None
    parts = [p.strip() for p in out.stdout.strip().split("\n")[0].split(",")]
    try:
        return min(100.0, max(0.0, float(parts[0] or 0))), (parts[1] if len(parts)>=2 else "GPU NVIDIA") or "GPU NVIDIA"
    except (ValueError, IndexError): return None

def _wmic_gpu_name():
    out = _run(["wmic","path","win32_videocontroller","get","name"])
    if not out or out.returncode!=0 or not out.stdout: return "GPU"
    for line in out.stdout.splitlines():
        line = line.strip()
        if line and line.lower() != "name": return line
    return "GPU"

def _windows_typeperf():
    if platform.system().lower() != "windows": return None
    out = _run(["typeperf", r"\GPU Engine(*)\Utilization Percentage", "-sc","1"], timeout=3.5)
    name = _wmic_gpu_name()
    if not out or out.returncode!=0 or not out.stdout: return None, name
    lines = [ln for ln in out.stdout.splitlines() if ln.strip()]
    data_line = lines[-1] if len(lines)>=2 else ""
    try:
        parts = [p.strip().strip('"') for p in data_line.split(",")]
        values = []
        for p in parts[1:]:
            try: values.append(float(p))
            except ValueError: continue
        if not values: return None, name
        return min(100.0, max(0.0, max(values))), name
    except Exception: return None, name

def _macos_gpu_name():
    out = _run(["system_profiler","SPDisplaysDataType"], timeout=10.0)
    if not out or out.returncode!=0 or not out.stdout: return "GPU"
    for line in out.stdout.splitlines():
        s = line.strip()
        if "chipset model:" in s.lower() or "modelo de chip:" in s.lower():
            parts = s.split(":",1)
            if len(parts)>=2 and parts[1].strip(): return parts[1].strip()
    return "GPU"

def fetch_gpu_info():
    nvidia = _nvidia_smi()
    if nvidia: return nvidia
    if platform.system().lower() == "windows":
        r = _windows_typeperf()
        if r: return r
        return None, _wmic_gpu_name()
    if platform.system().lower() == "darwin":
        return None, _macos_gpu_name()
    return None, "GPU no disponible"
