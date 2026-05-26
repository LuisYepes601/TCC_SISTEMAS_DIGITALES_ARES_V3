"""
ui/main_window.py
Ventana principal — sin IA, con MetricsWorker centralizado.

Un único hilo de fondo (MetricsWorker) alimenta todas las pestañas
mediante señales Qt, eliminando el doble-polling del diseño anterior.
"""

from __future__ import annotations

import os

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QActionGroup
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.services.alerts_service import get_active_count, get_critical_count
from core.services.data_worker import MetricsWorker
from core.services.system_service import (
    get_cpu_percent,
    get_disk_info,
    get_memory_info,
    get_system_health_score,
    get_uptime_str,
)
from core.utils.formatters import health_color, pct_to_status_color
from ui.styles.theme import (
    THEME_DARK,
    THEME_LIGHT,
    apply_theme,
    persist_theme,
    saved_theme,
)
from ui.tabs.alerts_tab      import AlertsTab
from ui.tabs.network_tab     import NetworkTab
from ui.tabs.performance_tab import PerformanceTab
from ui.tabs.processes_tab   import ProcessesTab
from ui.tabs.services_tab    import ServicesTab
from ui.tabs.system_tab      import SystemTab


# ---------------------------------------------------------------------------
# Botón de navegación lateral
# ---------------------------------------------------------------------------

class NavButton(QPushButton):
    def __init__(self, icon: str, label: str, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedHeight(52)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._icon  = icon
        self._label = label
        self._badge = 0
        self._refresh_text()

    def set_badge(self, n: int) -> None:
        self._badge = n
        self._refresh_text()

    def _refresh_text(self) -> None:
        badge = f"  ({self._badge})" if self._badge else ""
        self.setText(f"{self._icon}  {self._label}{badge}")


# ---------------------------------------------------------------------------
# Barra de estado superior
# ---------------------------------------------------------------------------

class TopStatusBar(QWidget):
    def __init__(self, worker: MetricsWorker, parent=None):
        super().__init__(parent)
        self._worker = worker
        self.setFixedHeight(40)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 4, 16, 4)
        layout.setSpacing(20)

        self._cpu   = self._lbl("CPU: —")
        self._mem   = self._lbl("MEM: —")
        self._disk  = self._lbl("DISCO: —")
        self._net   = self._lbl("RED: —")
        self._health = self._lbl("Salud: —", bold=True)

        for w in (self._cpu, self._mem, self._disk, self._net):
            layout.addWidget(w)
        layout.addStretch()
        layout.addWidget(self._health)

        worker.system_ready.connect(self._on_data)

    @staticmethod
    def _lbl(text: str, bold: bool = False) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("StatusBarLabel")
        if bold:
            f = lbl.font(); f.setBold(True); lbl.setFont(f)
        return lbl

    def _on_data(self, d: dict) -> None:
        def cspan(val: float, text: str) -> str:
            c = pct_to_status_color(val)
            return f'<span style="color:{c};font-weight:600">{text}</span>'

        cpu  = d.get("cpu", 0)
        mem  = d.get("mem_pct", 0)
        disk = d.get("disk_pct", 0)
        sr   = d.get("sent_rate", 0)
        rr   = d.get("recv_rate", 0)
        sc   = d.get("health_score", 0)
        desc = d.get("health_desc", "—")

        self._cpu.setText(f"CPU: {cspan(cpu, f'{cpu:.0f}%')}")
        self._cpu.setTextFormat(Qt.TextFormat.RichText)
        self._mem.setText(f"MEM: {cspan(mem, f'{mem:.0f}%')}")
        self._mem.setTextFormat(Qt.TextFormat.RichText)
        self._disk.setText(f"DISCO: {cspan(disk, f'{disk:.0f}%')}")
        self._disk.setTextFormat(Qt.TextFormat.RichText)

        from core.utils.formatters import bytes_per_sec_human
        self._net.setText(
            f"RED: ↑{bytes_per_sec_human(sr)} ↓{bytes_per_sec_human(rr)}")

        hc  = health_color(sc)
        dot = "🟢" if sc >= 70 else ("🟡" if sc >= 50 else "🔴")
        self._health.setText(
            f'{dot} Salud: <span style="color:{hc};font-weight:700">'
            f'{sc:.0f}/100 {desc}</span>')
        self._health.setTextFormat(Qt.TextFormat.RichText)


# ---------------------------------------------------------------------------
# Ventana principal
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ares — Administrador de Tareas")
        self.setMinimumSize(1100, 680)
        self.resize(1320, 780)

        # Iniciar el worker de métricas centralizado
        self._worker = MetricsWorker()
        self._worker.start()

        self._build_menu()
        self._build_ui()

        # Timer de badge de alertas (cada 2 s)
        self._alert_timer = QTimer(self)
        self._alert_timer.timeout.connect(self._refresh_alert_badge)
        self._alert_timer.start(2000)

    # ------------------------------------------------------------------
    # Construcción
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Status bar
        status_bar = TopStatusBar(self._worker)
        status_bar.setObjectName("TopStatusBar")
        root.addWidget(status_bar)

        sep = QWidget(); sep.setFixedHeight(1); sep.setObjectName("StatusSeparator")
        root.addWidget(sep)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        root.addLayout(body, stretch=1)

        # ── Sidebar ────────────────────────────────────────────────────
        sidebar = QWidget()
        sidebar.setFixedWidth(192)
        sidebar.setObjectName("Sidebar")
        sl = QVBoxLayout(sidebar)
        sl.setContentsMargins(10, 16, 10, 16)
        sl.setSpacing(4)

        title = QLabel("⚙ ARES")
        title.setObjectName("SidebarTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sl.addWidget(title)

        subtitle = QLabel("v3.0 · Task Manager")
        subtitle.setObjectName("SidebarSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sl.addWidget(subtitle)
        sl.addSpacing(16)

        nav_items = [
            ("⚡", "Procesos"),
            ("📊", "Rendimiento"),
            ("🌐", "Red"),
            ("🖥",  "Sistema"),
            ("🔔", "Alertas"),
        ]
        if os.name == "nt":
            nav_items.insert(4, ("⚙", "Servicios"))

        self._nav_btns: list[NavButton] = []
        for icon, label in nav_items:
            btn = NavButton(icon, label)
            btn.setObjectName("NavButton")
            btn.clicked.connect(lambda _, l=label: self._navigate(l))
            sl.addWidget(btn)
            self._nav_btns.append(btn)

        sl.addStretch()

        self._uptime_lbl = QLabel("⏱ —")
        self._uptime_lbl.setObjectName("SidebarUptime")
        self._uptime_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sl.addWidget(self._uptime_lbl)

        self._worker.system_ready.connect(
            lambda d: self._uptime_lbl.setText(f"⏱ {d.get('uptime', '—')}")
        )

        body.addWidget(sidebar)

        vsep = QWidget(); vsep.setFixedWidth(1); vsep.setObjectName("SidebarSeparator")
        body.addWidget(vsep)

        # ── Stack de páginas ───────────────────────────────────────────
        self._stack = QStackedWidget()
        self._stack.setObjectName("ContentStack")
        body.addWidget(self._stack, stretch=1)

        self._pages: dict[str, QWidget] = {}
        self._perf_tab   = PerformanceTab(worker=self._worker)
        self._alerts_tab = AlertsTab()

        pages = [
            ("Procesos",    ProcessesTab(worker=self._worker)),
            ("Rendimiento", self._perf_tab),
            ("Red",         NetworkTab(worker=self._worker)),
            ("Sistema",     SystemTab(worker=self._worker)),
            ("Alertas",     self._alerts_tab),
        ]
        if os.name == "nt":
            pages.insert(4, ("Servicios", ServicesTab()))

        for name, widget in pages:
            self._stack.addWidget(widget)
            self._pages[name] = widget

        self._navigate("Procesos")

    # ------------------------------------------------------------------
    # Navegación
    # ------------------------------------------------------------------

    def _navigate(self, name: str) -> None:
        widget = self._pages.get(name)
        if widget is None:
            return
        for page_name, page in self._pages.items():
            if hasattr(page, "pause_updates"):
                page.pause_updates(page_name != name)
        self._stack.setCurrentWidget(widget)
        for btn in self._nav_btns:
            btn.setChecked(btn._label == name)

    # ------------------------------------------------------------------
    # Menú
    # ------------------------------------------------------------------

    def _build_menu(self) -> None:
        mb       = self.menuBar()
        app_menu = mb.addMenu("Aplicación")

        appearance = app_menu.addMenu("🎨 Apariencia")
        group = QActionGroup(self)
        group.setExclusive(True)

        self._act_light = QAction("☀ Modo claro",  self, checkable=True)
        self._act_dark  = QAction("🌙 Modo oscuro", self, checkable=True)
        group.addAction(self._act_light)
        group.addAction(self._act_dark)
        appearance.addAction(self._act_light)
        appearance.addAction(self._act_dark)
        self._act_light.triggered.connect(lambda: self._set_theme(THEME_LIGHT))
        self._act_dark.triggered.connect(lambda:  self._set_theme(THEME_DARK))

        cur = saved_theme()
        self._act_light.setChecked(cur == THEME_LIGHT)
        self._act_dark.setChecked(cur == THEME_DARK)

        app_menu.addSeparator()
        about = QAction("ℹ Acerca de Ares…", self)
        about.triggered.connect(self._show_about)
        app_menu.addAction(about)

    def _set_theme(self, theme: str) -> None:
        app = QApplication.instance()
        if app:
            apply_theme(app, theme)
            persist_theme(theme)
        self._act_light.setChecked(theme == THEME_LIGHT)
        self._act_dark.setChecked(theme == THEME_DARK)
        self._perf_tab.set_app_theme(theme)

    def _show_about(self) -> None:
        QMessageBox.about(
            self, "Acerca de Ares v3.0",
            "<b>Administrador de Tareas Ares v3.0</b><br><br>"
            "Monitor de sistema de alto rendimiento.<br><br>"
            "<b>Mejoras v3.0:</b><br>"
            "• Hilo único de métricas (sin doble-polling)<br>"
            "• Tabla de procesos con modelo virtualizado (3–5× más rápido)<br>"
            "• Detalles extendidos: Mem MB, I/O, conexiones por proceso<br>"
            "• Temperaturas, batería y ventiladores en tiempo real<br>"
            "• Red: gráfico en vivo + estadísticas por interfaz<br>"
            "• Sistema: usuarios, sensores, swap detallado<br><br>"
            "Licencia: MIT"
        )

    # ------------------------------------------------------------------
    # Badge de alertas
    # ------------------------------------------------------------------

    def _refresh_alert_badge(self) -> None:
        count = get_active_count()
        crit  = get_critical_count()
        for btn in self._nav_btns:
            if btn._label == "Alertas":
                btn.set_badge(count)
                # Resaltar en rojo si hay críticas
                if crit:
                    btn.setStyleSheet("QPushButton#NavButton:checked { color: #ef4444; }")
                break

    # ------------------------------------------------------------------
    # Limpieza al cerrar
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        self._worker.stop()
        self._worker.wait(2000)
        super().closeEvent(event)
