"""
ui/tabs/alerts_tab.py
Pestaña de alertas con configuración de umbrales.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from core.data.alerts_repository import Alert, AlertLevel
from core.services.alerts_service import (
    clear_alerts,
    dismiss_all_alerts,
    get_alerts,
    get_thresholds,
    update_thresholds,
)
from core.utils.formatters import timestamp_str


class AlertItem(QFrame):
    _LEVEL_COLORS = {
        AlertLevel.INFO:     ("#60a5fa", "#1e3a5f"),
        AlertLevel.WARNING:  ("#facc15", "#3d2e00"),
        AlertLevel.CRITICAL: ("#ef4444", "#3d0000"),
    }

    def __init__(self, alert: Alert, parent=None):
        super().__init__(parent)
        self.setObjectName("AlertItem")
        color, bg = self._LEVEL_COLORS.get(alert.level, ("#94a3b8", "#1e293b"))
        self.setStyleSheet(
            f"QFrame#AlertItem {{ background:{bg}; border-left:4px solid {color}; "
            f"border-radius:6px; margin:2px 0; }}"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)

        left = QVBoxLayout()
        t = QLabel(alert.title)
        t.setStyleSheet(f"color:{color}; font-weight:700; font-size:10pt;")
        m = QLabel(alert.message)
        m.setStyleSheet("color:#cbd5e1; font-size:9pt;")
        m.setWordWrap(True)
        ts = QLabel(timestamp_str(alert.timestamp))
        ts.setStyleSheet("color:#64748b; font-size:8pt;")
        left.addWidget(t); left.addWidget(m); left.addWidget(ts)
        layout.addLayout(left, stretch=1)

        cat = QLabel(alert.category.upper())
        cat.setStyleSheet(
            f"color:{color}; font-size:8pt; font-weight:600; "
            f"border:1px solid {color}; border-radius:3px; padding:2px 6px;"
        )
        layout.addWidget(cat)


class AlertsTab(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(2000)
        self.refresh()

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter)

        # ── Lista de alertas ───────────────────────────────────────────
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(16, 16, 8, 16)

        hrow = QHBoxLayout()
        title = QLabel("🔔 Alertas del sistema")
        title.setObjectName("PanelTitle")
        self._count_lbl = QLabel("0 activas")
        self._count_lbl.setObjectName("AlertCount")
        hrow.addWidget(title); hrow.addStretch(); hrow.addWidget(self._count_lbl)
        ll.addLayout(hrow)

        brow = QHBoxLayout()
        btn_d = QPushButton("✓ Descartar todas")
        btn_d.clicked.connect(self._dismiss_all)
        btn_c = QPushButton("🗑 Limpiar historial")
        btn_c.clicked.connect(self._clear_all)
        brow.addWidget(btn_d); brow.addWidget(btn_c); brow.addStretch()
        ll.addLayout(brow)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._container = QWidget()
        self._container.setObjectName("AlertsContainer")
        self._alist = QVBoxLayout(self._container)
        self._alist.setContentsMargins(0, 0, 0, 0)
        self._alist.setSpacing(4)
        self._alist.addStretch()
        self._scroll.setWidget(self._container)
        ll.addWidget(self._scroll, stretch=1)
        splitter.addWidget(left)

        # ── Configuración de umbrales ──────────────────────────────────
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(8, 16, 16, 16)

        tgrp = QGroupBox("⚙ Umbrales de alerta")
        tgrp.setObjectName("ThresholdGroup")
        form = QFormLayout(tgrp)
        form.setSpacing(10)
        thresholds = get_thresholds()
        self._tw: dict[str, QDoubleSpinBox] = {}

        for key, label, default in [
            ("cpu_warning",     "CPU — Advertencia (%)",      thresholds.cpu_warning),
            ("cpu_critical",    "CPU — Crítico (%)",           thresholds.cpu_critical),
            ("memory_warning",  "Memoria — Advertencia (%)",   thresholds.memory_warning),
            ("memory_critical", "Memoria — Crítico (%)",       thresholds.memory_critical),
            ("disk_warning",    "Disco — Advertencia (%)",     thresholds.disk_warning),
            ("disk_critical",   "Disco — Crítico (%)",         thresholds.disk_critical),
            ("gpu_warning",     "GPU — Advertencia (%)",       thresholds.gpu_warning),
            ("gpu_critical",    "GPU — Crítico (%)",           thresholds.gpu_critical),
        ]:
            spin = QDoubleSpinBox()
            spin.setRange(1.0, 100.0)
            spin.setSingleStep(5.0)
            spin.setSuffix(" %")
            spin.setValue(default)
            self._tw[key] = spin
            form.addRow(label + ":", spin)

        rl.addWidget(tgrp)
        apply_btn = QPushButton("✅ Aplicar umbrales")
        apply_btn.setObjectName("ApplyButton")
        apply_btn.clicked.connect(self._apply)
        rl.addWidget(apply_btn)

        # Leyenda
        legend = QGroupBox("Leyenda de severidad")
        leg_l = QVBoxLayout(legend)
        for lv, c, txt in [("INFO", "#60a5fa", "Información"),
                            ("WARNING", "#facc15", "Advertencia"),
                            ("CRITICAL", "#ef4444", "Crítico")]:
            row = QHBoxLayout()
            dot = QLabel("●"); dot.setStyleSheet(f"color:{c}; font-size:14pt;")
            row.addWidget(dot); row.addWidget(QLabel(f" {txt}")); row.addStretch()
            leg_l.addLayout(row)
        rl.addWidget(legend)
        rl.addStretch()

        splitter.addWidget(right)
        splitter.setSizes([600, 320])

    def pause_updates(self, should_pause: bool) -> None:
        if should_pause:
            self._timer.stop()
        elif not self._timer.isActive():
            self._timer.start(2000)

    def refresh(self) -> None:
        alerts = get_alerts(include_dismissed=False)
        self._count_lbl.setText(f"{len(alerts)} activas")

        while self._alist.count() > 1:
            item = self._alist.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not alerts:
            empty = QLabel("✅ Sin alertas activas — sistema funcionando correctamente.")
            empty.setObjectName("EmptyAlertsLabel")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._alist.insertWidget(0, empty)
        else:
            for alert in alerts:
                self._alist.insertWidget(self._alist.count() - 1, AlertItem(alert))

    def _dismiss_all(self) -> None:
        dismiss_all_alerts(); self.refresh()

    def _clear_all(self) -> None:
        clear_alerts(); self.refresh()

    def _apply(self) -> None:
        update_thresholds(**{k: w.value() for k, w in self._tw.items()})
