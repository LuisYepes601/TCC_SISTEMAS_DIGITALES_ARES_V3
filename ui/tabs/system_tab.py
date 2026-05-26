"""
ui/tabs/system_tab.py
Pestaña de sistema — temperatura, batería, ventiladores, usuarios, hardware detallado.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.services.system_service import (
    get_architecture,
    get_battery,
    get_boot_time,
    get_cpu_count_logical,
    get_cpu_count_physical,
    get_cpu_freq,
    get_cpu_name,
    get_disks,
    get_fan_speeds,
    get_hostname,
    get_os_info,
    get_ram_total_gb,
    get_temperatures,
    get_uptime_str,
    get_users,
)
from core.utils.formatters import seconds_to_human, timestamp_str


# ---------------------------------------------------------------------------
# Helpers de construcción
# ---------------------------------------------------------------------------

def _card(title: str, value: str, color: str = "") -> QFrame:
    frame = QFrame()
    frame.setFrameShape(QFrame.Shape.StyledPanel)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(10, 8, 10, 8)
    layout.setSpacing(2)
    t = QLabel(title)
    t.setStyleSheet("color:#94a3b8; font-size:8.5pt;")
    v = QLabel(value)
    v.setWordWrap(True)
    v.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    style = "font-weight:700;"
    if color:
        style += f" color:{color};"
    v.setStyleSheet(style)
    layout.addWidget(t)
    layout.addWidget(v)
    return frame


def _section(title: str) -> QLabel:
    lbl = QLabel(title)
    lbl.setStyleSheet(
        "font-size:11pt; font-weight:700; margin-top:12px; margin-bottom:4px;")
    return lbl


def _temp_color(current: float, high: float | None, critical: float | None) -> str:
    if critical and current >= critical:
        return "#ef4444"
    if high and current >= high:
        return "#fb923c"
    if current >= 80:
        return "#fb923c"
    if current >= 60:
        return "#facc15"
    return "#22c55e"


# ---------------------------------------------------------------------------
# Pestaña principal
# ---------------------------------------------------------------------------

class SystemTab(QWidget):
    def __init__(self, worker=None):
        super().__init__()
        self._worker = worker

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._content = QWidget()
        self._main_layout = QVBoxLayout(self._content)
        self._main_layout.setContentsMargins(12, 12, 12, 12)
        self._main_layout.setSpacing(4)

        self._build_static_sections()
        self._build_dynamic_placeholders()

        self._main_layout.addStretch()
        scroll.setWidget(self._content)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)

        # Actualizar secciones dinámicas (temperatura, batería, etc.)
        if worker:
            worker.system_ready.connect(self._on_data)
        else:
            self._timer = QTimer(self)
            self._timer.timeout.connect(self._refresh_dynamic)
            self._timer.start(3000)
        self._refresh_dynamic()

    # ------------------------------------------------------------------
    # Secciones estáticas (no cambian)
    # ------------------------------------------------------------------

    def _build_static_sections(self) -> None:
        ml = self._main_layout

        # ── Equipo y SO ────────────────────────────────────────────────
        ml.addWidget(_section("🖥 Equipo y sistema operativo"))
        g1 = QGridLayout()
        g1.setSpacing(8)
        g1.addWidget(_card("Nombre del equipo", get_hostname()), 0, 0)
        g1.addWidget(_card("Sistema operativo", get_os_info()), 0, 1)
        g1.addWidget(_card("Arquitectura", get_architecture()), 0, 2)
        ml.addLayout(g1)

        # ── Arranque ───────────────────────────────────────────────────
        ml.addWidget(_section("⏱ Tiempo de actividad"))
        boot = get_boot_time()
        boot_str = boot.strftime("%d/%m/%Y %H:%M:%S") if boot else "—"
        g2 = QGridLayout()
        g2.setSpacing(8)
        g2.addWidget(_card("Último arranque", boot_str), 0, 0)
        self._uptime_card = _card("Tiempo activo", "—")
        g2.addWidget(self._uptime_card, 0, 1)
        self._proc_count_card = _card("Procesos en ejecución", "—")
        g2.addWidget(self._proc_count_card, 0, 2)
        ml.addLayout(g2)

        # ── CPU ────────────────────────────────────────────────────────
        ml.addWidget(_section("⚙ Procesador"))
        cpu_phys = get_cpu_count_physical()
        cpu_log  = get_cpu_count_logical()
        freq     = get_cpu_freq()
        freq_str = f"{freq[0]/1000:.2f} GHz (máx {freq[2]/1000:.2f} GHz)" \
                   if freq and freq[0] else "—"
        g3 = QGridLayout()
        g3.setSpacing(8)
        g3.addWidget(_card("Modelo",           get_cpu_name()), 0, 0, 1, 2)
        g3.addWidget(_card("Núcleos físicos",  str(cpu_phys)), 1, 0)
        g3.addWidget(_card("Núcleos lógicos",  str(cpu_log)),  1, 1)
        g3.addWidget(_card("Frecuencia",       freq_str),      1, 2)
        ml.addLayout(g3)

        # ── Memoria ────────────────────────────────────────────────────
        ml.addWidget(_section("🧠 Memoria RAM"))
        total_gb = get_ram_total_gb()
        self._ram_bar = QProgressBar()
        self._ram_bar.setRange(0, 100)
        self._ram_bar.setFixedHeight(18)
        self._ram_bar.setTextVisible(True)
        ml.addWidget(self._ram_bar)

        g4 = QGridLayout()
        g4.setSpacing(8)
        g4.addWidget(_card("Total", f"{total_gb:.2f} GB"), 0, 0)
        self._ram_used_card  = _card("Usado",     "—")
        self._ram_free_card  = _card("Disponible","—")
        self._swap_card      = _card("Swap",      "—")
        self._cache_card     = _card("Caché+Buf", "—")
        g4.addWidget(self._ram_used_card,  0, 1)
        g4.addWidget(self._ram_free_card,  0, 2)
        g4.addWidget(self._swap_card,      1, 0)
        g4.addWidget(self._cache_card,     1, 1)
        ml.addLayout(g4)

        # ── Discos ─────────────────────────────────────────────────────
        ml.addWidget(_section("💾 Discos y particiones"))
        disks = get_disks()
        self._disk_group = QGroupBox()
        self._disk_group.setFlat(True)
        disk_layout = QVBoxLayout(self._disk_group)
        disk_layout.setSpacing(8)
        disk_layout.setContentsMargins(0, 0, 0, 0)

        if disks:
            for d in disks:
                row = QHBoxLayout()
                lbl = QLabel(
                    f"<b>{d['mountpoint']}</b> ({d['fstype']})  —  "
                    f"{d['used_gb']:.1f} / {d['total_gb']:.1f} GB  "
                    f"({d['percent']:.0f}% usado)"
                )
                lbl.setWordWrap(True)
                bar = QProgressBar()
                bar.setRange(0, 100)
                bar.setValue(int(d["percent"]))
                bar.setFixedHeight(14)
                bar.setTextVisible(False)
                bar.setFixedWidth(160)
                c = "#ef4444" if d["percent"] >= 90 else (
                    "#fb923c" if d["percent"] >= 75 else "#22c55e")
                bar.setStyleSheet(
                    f"QProgressBar::chunk {{ background:{c}; border-radius:3px; }}")
                row.addWidget(lbl, stretch=1)
                row.addWidget(bar)
                disk_layout.addLayout(row)
        else:
            disk_layout.addWidget(QLabel("No se pudo obtener información de discos."))

        ml.addWidget(self._disk_group)

    # ------------------------------------------------------------------
    # Secciones dinámicas (placeholders que se rellenan con datos)
    # ------------------------------------------------------------------

    def _build_dynamic_placeholders(self) -> None:
        ml = self._main_layout

        # Temperatura
        self._temp_section_lbl = _section("🌡 Temperaturas")
        self._temp_section_lbl.setVisible(False)
        ml.addWidget(self._temp_section_lbl)
        self._temp_container = QWidget()
        self._temp_layout = QGridLayout(self._temp_container)
        self._temp_layout.setSpacing(8)
        self._temp_container.setVisible(False)
        ml.addWidget(self._temp_container)

        # Batería
        self._bat_section_lbl = _section("🔋 Batería")
        self._bat_section_lbl.setVisible(False)
        ml.addWidget(self._bat_section_lbl)
        self._bat_container = QWidget()
        bat_l = QHBoxLayout(self._bat_container)
        bat_l.setContentsMargins(0, 0, 0, 0)
        bat_l.setSpacing(8)
        self._bat_pct_card      = _card("Carga",   "—")
        self._bat_status_card   = _card("Estado",  "—")
        self._bat_time_card     = _card("Tiempo restante", "—")
        bat_l.addWidget(self._bat_pct_card)
        bat_l.addWidget(self._bat_status_card)
        bat_l.addWidget(self._bat_time_card)
        bat_l.addStretch()
        self._bat_bar = QProgressBar()
        self._bat_bar.setRange(0, 100)
        self._bat_bar.setFixedHeight(18)
        self._bat_bar.setTextVisible(True)
        bat_l.addWidget(self._bat_bar)
        self._bat_container.setVisible(False)
        ml.addWidget(self._bat_container)

        # Ventiladores
        self._fan_section_lbl = _section("💨 Ventiladores")
        self._fan_section_lbl.setVisible(False)
        ml.addWidget(self._fan_section_lbl)
        self._fan_container = QWidget()
        self._fan_layout = QHBoxLayout(self._fan_container)
        self._fan_layout.setContentsMargins(0, 0, 0, 0)
        self._fan_container.setVisible(False)
        ml.addWidget(self._fan_container)

        # Usuarios
        self._user_section_lbl = _section("👤 Usuarios con sesión activa")
        ml.addWidget(self._user_section_lbl)
        self._user_container = QWidget()
        self._user_layout = QHBoxLayout(self._user_container)
        self._user_layout.setContentsMargins(0, 0, 0, 0)
        ml.addWidget(self._user_container)

    # ------------------------------------------------------------------
    # Actualización dinámica
    # ------------------------------------------------------------------

    def _on_data(self, d: dict) -> None:
        """Recibe datos del MetricsWorker cada 1 s (temperatura, batería)."""
        from core.services.system_service import get_process_count
        self._uptime_card.findChildren(QLabel)[-1].setText(get_uptime_str())
        self._proc_count_card.findChildren(QLabel)[-1].setText(str(get_process_count()))

        mem = d.get("mem_details", {})
        mem_pct = d.get("mem_pct", 0)
        self._ram_bar.setValue(int(mem_pct))
        self._ram_bar.setFormat(f"{mem_pct:.1f}%")
        c = "#ef4444" if mem_pct >= 90 else ("#fb923c" if mem_pct >= 75 else "#22c55e")
        self._ram_bar.setStyleSheet(
            f"QProgressBar::chunk {{ background:{c}; border-radius:4px; }}")
        self._ram_used_card.findChildren(QLabel)[-1].setText(
            f"{mem.get('used_gb', 0):.2f} GB")
        self._ram_free_card.findChildren(QLabel)[-1].setText(
            f"{mem.get('available_gb', 0):.2f} GB")
        self._swap_card.findChildren(QLabel)[-1].setText(
            f"{mem.get('swap_used_gb', 0):.1f} / "
            f"{mem.get('swap_total_gb', 0):.1f} GB "
            f"({mem.get('swap_percent', 0):.0f}%)")
        buf = mem.get("buffers_gb", 0) + mem.get("cached_gb", 0)
        self._cache_card.findChildren(QLabel)[-1].setText(f"{buf:.2f} GB")

        self._update_temps(d.get("temps", {}))
        self._update_battery(d.get("battery"))
        self._update_fans()

    def _refresh_dynamic(self) -> None:
        """Refresh sin worker."""
        from core.services.system_service import (
            get_cpu_percent, get_memory_details, get_memory_info, get_process_count
        )
        self._uptime_card.findChildren(QLabel)[-1].setText(get_uptime_str())
        self._proc_count_card.findChildren(QLabel)[-1].setText(str(get_process_count()))

        mem = get_memory_details()
        mem_pct, _, _ = get_memory_info()
        fake_d = {"mem_pct": mem_pct, "mem_details": mem,
                  "temps": get_temperatures(), "battery": get_battery()}
        self._on_data(fake_d)
        self._update_users()

    def _update_temps(self, temps: dict) -> None:
        if not temps:
            self._temp_section_lbl.setVisible(False)
            self._temp_container.setVisible(False)
            return

        self._temp_section_lbl.setVisible(True)
        self._temp_container.setVisible(True)

        # Limpiar grid anterior
        while self._temp_layout.count():
            item = self._temp_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        col = 0
        row = 0
        for sensor_name, entries in temps.items():
            for e in entries:
                label = e.get("label") or sensor_name
                cur   = e.get("current", 0)
                high  = e.get("high")
                crit  = e.get("critical")
                color = _temp_color(cur, high, crit)
                title = f"🌡 {label}"
                val_str = f"{cur}°C"
                if crit:
                    val_str += f" / {crit}°C crítico"
                card = _card(title, val_str, color)
                self._temp_layout.addWidget(card, row, col)
                col += 1
                if col >= 4:
                    col = 0
                    row += 1

    def _update_battery(self, battery: dict | None) -> None:
        if not battery:
            self._bat_section_lbl.setVisible(False)
            self._bat_container.setVisible(False)
            return

        self._bat_section_lbl.setVisible(True)
        self._bat_container.setVisible(True)

        pct     = battery.get("percent", 0)
        plugged = battery.get("plugged", False)
        secs    = battery.get("secs_left", -1)

        pct_label  = self._bat_pct_card.findChildren(QLabel)[-1]
        stat_label = self._bat_status_card.findChildren(QLabel)[-1]
        time_label = self._bat_time_card.findChildren(QLabel)[-1]

        pct_label.setText(f"{pct:.0f}%")
        stat_label.setText("🔌 Cargando" if plugged else "🔋 Descargando")
        if secs > 0:
            time_label.setText(seconds_to_human(secs))
        elif plugged:
            time_label.setText("Cargando…")
        else:
            time_label.setText("—")

        self._bat_bar.setValue(int(pct))
        self._bat_bar.setFormat(f"{pct:.0f}%")
        c = "#22c55e" if pct >= 60 else ("#facc15" if pct >= 25 else "#ef4444")
        self._bat_bar.setStyleSheet(
            f"QProgressBar::chunk {{ background:{c}; border-radius:4px; }}")

    def _update_fans(self) -> None:
        fans = get_fan_speeds()
        if not fans:
            self._fan_section_lbl.setVisible(False)
            self._fan_container.setVisible(False)
            return

        self._fan_section_lbl.setVisible(True)
        self._fan_container.setVisible(True)

        # Limpiar
        while self._fan_layout.count():
            item = self._fan_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for name, speeds in fans.items():
            for i, rpm in enumerate(speeds):
                lbl = f"{name} #{i+1}" if len(speeds) > 1 else name
                self._fan_layout.addWidget(_card(f"💨 {lbl}", f"{rpm} RPM"))
        self._fan_layout.addStretch()

    def _update_users(self) -> None:
        users = get_users()

        # Limpiar
        while self._user_layout.count():
            item = self._user_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if users:
            for u in users:
                card = _card(
                    f"👤 {u['name']}",
                    f"Terminal: {u['terminal']}  |  Desde: {u['started']}  |  Host: {u['host']}"
                )
                self._user_layout.addWidget(card)
        else:
            self._user_layout.addWidget(QLabel("Sin sesiones activas detectadas."))
        self._user_layout.addStretch()

    def pause_updates(self, should_pause: bool) -> None:
        if hasattr(self, "_timer"):
            if should_pause:
                self._timer.stop()
            else:
                self._timer.start(3000)
