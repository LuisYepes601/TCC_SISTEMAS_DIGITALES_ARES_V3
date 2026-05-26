"""tests/test_formatters.py"""
import pytest
from core.utils.formatters import (
    bytes_to_mb, bytes_to_gb, bytes_per_sec_human, connection_status_label,
    cpu_freq_str, health_color, nice_to_label, pct_to_status_color,
    process_status_color, process_status_label, seconds_to_human,
    service_status_color, service_status_label,
)

def test_bytes_to_mb_exact():    assert bytes_to_mb(1_048_576) == "1.0 MB"
def test_bytes_to_mb_zero():     assert bytes_to_mb(0) == "0.0 MB"
def test_bytes_to_gb_exact():    assert bytes_to_gb(1024**3) == "1.00 GB"
def test_bytes_per_sec_bytes():  assert "B/s"  in bytes_per_sec_human(500)
def test_bytes_per_sec_kb():     assert "KB/s" in bytes_per_sec_human(2000)
def test_bytes_per_sec_mb():     assert "MB/s" in bytes_per_sec_human(2*1024*1024)
def test_cpu_freq_str():         assert "GHz" in cpu_freq_str((2500.0, 800.0, 3800.0))
def test_cpu_freq_none():        assert cpu_freq_str(None) == "—"

@pytest.mark.parametrize("raw,exp", [
    ("running","En ejecución"), ("sleeping","En reposo"), ("zombie","Zombi"),
    ("stopped","Detenido"), ("idle","Inactivo"),
])
def test_process_status_label(raw, exp): assert process_status_label(raw) == exp
def test_process_status_empty():         assert process_status_label("") == "—"
def test_process_status_case():          assert process_status_label("RUNNING") == "En ejecución"
def test_process_status_color_ok():      assert process_status_color("running") == "#22c55e"
def test_process_status_color_zombie():  assert process_status_color("zombie") == "#ef4444"

@pytest.mark.parametrize("nice,lbl", [(-20,"Alto"),(0,"Normal"),(10,"Bajo"),(19,"Muy Bajo")])
def test_nice_to_label(nice, lbl): assert nice_to_label(nice) == lbl

@pytest.mark.parametrize("s,e", [("ESTABLISHED","Establecida"),("LISTEN","Escuchando"),("TIME_WAIT","Espera tiempo")])
def test_connection_label(s, e): assert connection_status_label(s) == e
def test_connection_dash():      assert connection_status_label("—") == "—"
def test_service_running():      assert service_status_label("Running") == "En ejecución"
def test_service_stopped():      assert service_status_label("Stopped") == "Detenido"
def test_service_color_run():    assert service_status_color("Running") == "#22c55e"

@pytest.mark.parametrize("score,color", [(90,"#22c55e"),(75,"#86efac"),(60,"#facc15"),(40,"#fb923c"),(10,"#ef4444")])
def test_health_color(score, color): assert health_color(score) == color

def test_pct_critical():    assert pct_to_status_color(95) == "#ef4444"
def test_pct_warning():     assert pct_to_status_color(80) == "#fb923c"
def test_pct_ok():          assert pct_to_status_color(30) == "#22c55e"
def test_seconds_s():       assert "s" in seconds_to_human(45)
def test_seconds_min():     assert "min" in seconds_to_human(90)
def test_seconds_h():       assert "h" in seconds_to_human(7200)
def test_seconds_d():       assert "d" in seconds_to_human(86400*2)
