"""
ui/tabs/services_tab.py
Servicios de Windows — sin cambios funcionales, añadido pause_updates.
"""

import os
from PyQt6.QtWidgets import (
    QHBoxLayout, QHeaderView, QLabel, QMessageBox,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)
from core.services.services_service import get_services, start_service, stop_service
from core.utils.formatters import service_status_label


class ServicesTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        if os.name != "nt":
            layout.addWidget(QLabel("⚠ La gestión de servicios está disponible solo en Windows."))
            return
        layout.addWidget(QLabel("⚙ Servicios de Windows (requiere administrador para iniciar/detener)"))
        bar = QHBoxLayout()
        self.btn_refresh = QPushButton("↻ Actualizar"); self.btn_refresh.clicked.connect(self.refresh)
        self.btn_start = QPushButton("▶ Iniciar"); self.btn_start.clicked.connect(self._start)
        self.btn_stop = QPushButton("⏹ Detener"); self.btn_stop.clicked.connect(self._stop)
        for b in (self.btn_refresh, self.btn_start, self.btn_stop): bar.addWidget(b)
        bar.addStretch(); layout.addLayout(bar)
        self.table = QTableWidget(); self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Nombre", "Nombre para mostrar", "Estado"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True); layout.addWidget(self.table)
        self.refresh()

    def pause_updates(self, _: bool) -> None: pass

    def refresh(self) -> None:
        if os.name != "nt": return
        self.btn_refresh.setEnabled(False); self.btn_refresh.setText("Cargando…")
        try:
            services = get_services(); self.table.setRowCount(len(services))
            for row, s in enumerate(services):
                self.table.setItem(row, 0, QTableWidgetItem(s["name"]))
                self.table.setItem(row, 1, QTableWidgetItem(s["display_name"]))
                self.table.setItem(row, 2, QTableWidgetItem(service_status_label(s["status"])))
        except Exception as e:
            QMessageBox.warning(self, "Error", f"No se pudo cargar la lista:\n{e}")
        finally:
            self.btn_refresh.setEnabled(True); self.btn_refresh.setText("↻ Actualizar")

    def _start(self) -> None:
        name = self._selected_name()
        if not name: return
        ok, msg = start_service(name)
        (QMessageBox.information if ok else QMessageBox.warning)(self, "Servicios", msg)
        if ok: self.refresh()

    def _stop(self) -> None:
        name = self._selected_name()
        if not name: return
        ok, msg = stop_service(name)
        (QMessageBox.information if ok else QMessageBox.warning)(self, "Servicios", msg)
        if ok: self.refresh()

    def _selected_name(self) -> str | None:
        row = self.table.currentRow()
        item = self.table.item(row, 0)
        return item.text().strip() if item and row >= 0 else None
