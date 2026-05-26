"""
ui/tabs/processes_tab.py
Pestaña de procesos — reescrita con QAbstractTableModel.

Ventajas sobre QTableWidget:
  • Solo renderiza las filas visibles (virtualización)
  • No crea QTableWidgetItem por celda (90 % menos objetos)
  • Filtrado y ordenación via proxy model (sin reconstruir la tabla)
  • Las actualizaciones del worker no bloquean el scroll
"""

from __future__ import annotations

import os
from datetime import datetime

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from core.services.alerts_service import add_process_alert
from core.services.process_service import (
    change_priority,
    export_processes_csv,
    get_priority_options,
    get_process_details,
    get_process_exe_path,
    kill_process,
    kill_process_and_children,
    open_process_folder,
    resume,
    suspend,
)
from core.utils.formatters import (
    PROCESS_FILTER_KEYS,
    process_status_label,
)
from ui.models.process_model import ProcessFilterProxy, ProcessModel


class ProcessesTab(QWidget):
    """Pestaña de procesos con modelo de alto rendimiento."""

    def __init__(self, worker=None):
        super().__init__()
        self._worker = worker
        self._model  = ProcessModel()
        self._proxy  = ProcessFilterProxy()
        self._proxy.setSourceModel(self._model)
        self._paused = False

        self._build_ui()
        self._connect_signals()

    # ------------------------------------------------------------------
    # Construcción de UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # ── Filtros ────────────────────────────────────────────────────
        fgrp = QGroupBox("Filtros")
        fl = QHBoxLayout(fgrp)
        fl.setSpacing(8)

        fl.addWidget(QLabel("🔍"))
        self._search = QLineEdit()
        self._search.setPlaceholderText("Nombre del proceso…")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._apply_filters)
        fl.addWidget(self._search, stretch=2)

        fl.addWidget(QLabel("CPU >"))
        self._cpu_min = QSpinBox()
        self._cpu_min.setRange(0, 100)
        self._cpu_min.setSuffix(" %")
        self._cpu_min.valueChanged.connect(self._apply_filters)
        fl.addWidget(self._cpu_min)

        fl.addWidget(QLabel("Mem >"))
        self._mem_min = QSpinBox()
        self._mem_min.setRange(0, 100)
        self._mem_min.setSuffix(" %")
        self._mem_min.valueChanged.connect(self._apply_filters)
        fl.addWidget(self._mem_min)

        fl.addWidget(QLabel("Estado:"))
        self._status_combo = QComboBox()
        self._status_combo.addItem("Todos", None)
        for key in PROCESS_FILTER_KEYS:
            self._status_combo.addItem(process_status_label(key), key)
        self._status_combo.currentIndexChanged.connect(self._apply_filters)
        fl.addWidget(self._status_combo)

        fl.addStretch()
        self._count_lbl = QLabel("— procesos")
        self._count_lbl.setObjectName("ProcessCount")
        fl.addWidget(self._count_lbl)

        root.addWidget(fgrp)

        # ── Barra de acciones ──────────────────────────────────────────
        bar = QHBoxLayout()
        bar.setSpacing(6)

        self._btn_pause  = QPushButton("⏸ Pausar")
        self._btn_pause.setCheckable(True)
        self._btn_pause.clicked.connect(self._toggle_pause)

        self._btn_folder  = QPushButton("📁 Ubicación")
        self._btn_folder.clicked.connect(self._open_folder)

        self._btn_details = QPushButton("🔍 Detalles")
        self._btn_details.clicked.connect(self._show_details)

        self._btn_suspend = QPushButton("⏸ Suspender")
        self._btn_suspend.clicked.connect(self._suspend)

        self._btn_resume_p = QPushButton("▶ Reanudar")
        self._btn_resume_p.clicked.connect(self._resume_proc)

        self._btn_kill = QPushButton("✕ Finalizar")
        self._btn_kill.setObjectName("DangerButton")
        self._btn_kill.clicked.connect(self._kill)

        self._btn_export = QPushButton("⬇ Exportar CSV")
        self._btn_export.clicked.connect(self._export_csv)

        for b in (self._btn_pause, self._btn_folder, self._btn_details,
                  self._btn_suspend, self._btn_resume_p, self._btn_kill,
                  self._btn_export):
            bar.addWidget(b)
        bar.addStretch()
        root.addLayout(bar)

        # ── Tabla ──────────────────────────────────────────────────────
        self._view = QTableView()
        self._view.setModel(self._proxy)
        self._view.setSortingEnabled(True)
        self._view.sortByColumn(3, Qt.SortOrder.DescendingOrder)   # CPU desc por defecto
        self._view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._view.setAlternatingRowColors(True)
        self._view.setShowGrid(False)
        self._view.verticalHeader().hide()
        self._view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._view.customContextMenuRequested.connect(self._context_menu)
        self._view.doubleClicked.connect(self._show_details)

        hdr = self._view.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)       # icono
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)     # nombre
        hdr.setSectionResizeMode(9, QHeaderView.ResizeMode.ResizeToContents)
        self._view.setColumnWidth(0, 28)
        self._view.setColumnWidth(1, 68)
        self._view.setColumnWidth(3, 68)
        self._view.setColumnWidth(4, 68)
        self._view.setColumnWidth(5, 80)
        self._view.setColumnWidth(6, 105)
        self._view.setColumnWidth(7, 58)
        self._view.setColumnWidth(8, 90)
        self._view.setRowHeight

        root.addWidget(self._view)

        # Actualizar contador cuando cambia el filtro
        self._proxy.count_changed.connect(
            lambda n: self._count_lbl.setText(f"{n} procesos")
        )

    def _connect_signals(self) -> None:
        if self._worker is not None:
            self._worker.processes_ready.connect(self._on_processes)
        else:
            # Fallback: timer propio si no hay worker
            self._fallback_timer = QTimer(self)
            self._fallback_timer.timeout.connect(self._fallback_refresh)
            self._fallback_timer.start(3000)
            self._fallback_refresh()

    # ------------------------------------------------------------------
    # Slots de datos
    # ------------------------------------------------------------------

    def _on_processes(self, processes: list[dict]) -> None:
        if self._paused:
            return
        self._model.update_processes(processes)
        # Actualizar contador
        self._count_lbl.setText(f"{self._proxy.rowCount()} procesos")

    def _fallback_refresh(self) -> None:
        from core.services.process_service import get_processes
        procs = get_processes(sort_by="cpu")
        self._on_processes(procs)

    # ------------------------------------------------------------------
    # Filtros
    # ------------------------------------------------------------------

    def _apply_filters(self) -> None:
        self._proxy.set_filters(
            name   = self._search.text().strip(),
            cpu    = self._cpu_min.value(),
            mem    = self._mem_min.value(),
            status = self._status_combo.currentData(),
        )

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------

    def _toggle_pause(self) -> None:
        self._paused = self._btn_pause.isChecked()
        self._btn_pause.setText("▶ Reanudar" if self._paused else "⏸ Pausar")

    def pause_updates(self, should_pause: bool) -> None:
        self._paused = should_pause

    def _selected_process(self) -> dict | None:
        rows = self._view.selectionModel().selectedRows()
        if not rows:
            return None
        return self._proxy.process_at(rows[0].row())

    def _kill(self) -> None:
        p = self._selected_process()
        if not p:
            QMessageBox.warning(self, "Finalizar", "Seleccione un proceso.")
            return
        reply = QMessageBox.question(
            self, "Confirmar",
            f'¿Finalizar "{p["name"]}" (PID {p["pid"]})?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        ok, msg = kill_process(p["pid"])
        if ok:
            add_process_alert(f"Proceso finalizado: {p['name']}", f"PID {p['pid']} terminado.")
            QMessageBox.information(self, "Finalizar", msg)
        else:
            QMessageBox.warning(self, "Error", msg)

    def _kill_tree(self) -> None:
        p = self._selected_process()
        if not p:
            return
        reply = QMessageBox.question(
            self, "Confirmar",
            f'¿Finalizar el árbol completo de "{p["name"]}" (PID {p["pid"]}) y todos sus hijos?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        ok, msg = kill_process_and_children(p["pid"])
        if ok:
            add_process_alert(f"Árbol finalizado: {p['name']}", msg)
            QMessageBox.information(self, "Árbol finalizado", msg)
        else:
            QMessageBox.warning(self, "Error", msg)

    def _suspend(self) -> None:
        p = self._selected_process()
        if not p:
            return
        ok, msg = suspend(p["pid"])
        self._result_msg(ok, msg, "Suspender")

    def _resume_proc(self) -> None:
        p = self._selected_process()
        if not p:
            return
        ok, msg = resume(p["pid"])
        self._result_msg(ok, msg, "Reanudar")

    def _open_folder(self) -> None:
        p = self._selected_process()
        if not p:
            QMessageBox.warning(self, "Ubicación", "Seleccione un proceso.")
            return
        path = get_process_exe_path(p["pid"])
        if not path:
            QMessageBox.warning(self, "Ubicación", "No se pudo obtener la ruta del ejecutable.")
            return
        ok, msg = open_process_folder(path)
        if not ok:
            QMessageBox.warning(self, "Ubicación", msg)

    def _show_details(self) -> None:
        p = self._selected_process()
        if not p:
            QMessageBox.warning(self, "Detalles", "Seleccione un proceso.")
            return
        details = get_process_details(p["pid"])
        if not details:
            QMessageBox.warning(self, "Detalles", f"No se pudo obtener info del PID {p['pid']}.")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Detalles — {details.get('name')} (PID {p['pid']})")
        dlg.setMinimumSize(480, 420)
        dlg.resize(520, 460)
        layout = QVBoxLayout(dlg)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.Shape.NoFrame)
        inner = QWidget()
        il = QVBoxLayout(inner)

        from core.utils.formatters import process_status_label, seconds_to_human
        import time as _t

        cpu_t = details.get("cpu_times")
        cpu_str = f"usuario {cpu_t.user:.1f}s / sistema {cpu_t.system:.1f}s" if cpu_t else "—"
        aff = details.get("cpu_affinity")
        aff_str = ", ".join(str(x) for x in (aff or [])) or "—"

        uptime_secs = _t.time() - (details.get("create_time") or _t.time())

        sections = [
            ("🔖 Identificación", [
                ("PID",            str(details.get("pid", "—"))),
                ("Nombre",         details.get("name", "—")),
                ("Usuario",        details.get("username", "—")),
                ("Estado",         process_status_label(details.get("status", ""))),
                ("Tiempo activo",  seconds_to_human(uptime_secs)),
            ]),
            ("🧠 Memoria", [
                ("RSS (real)",     f"{details.get('mem_rss_mb', 0):.1f} MB"),
                ("VMS (virtual)",  f"{details.get('mem_vms_mb', 0):.1f} MB"),
                ("% total",        f"{details.get('mem_pct', 0):.2f} %"),
            ]),
            ("⚙ CPU y hilos", [
                ("Hilos",          str(details.get("num_threads", "—"))),
                ("Tiempo CPU",     cpu_str),
                ("Afinidad CPU",   aff_str),
            ]),
            ("💾 I/O de disco", [
                ("Bytes leídos",   f"{details.get('io_read_mb', 0):.2f} MB"),
                ("Bytes escritos", f"{details.get('io_write_mb', 0):.2f} MB"),
            ]),
            ("🌐 Red", [
                ("Conexiones",     str(details.get("connections", 0))),
            ]),
            ("📋 Procesos hijos", [
                ("PIDs hijos",     ", ".join(str(x) for x in details.get("children", [])) or "Ninguno"),
            ]),
            ("💻 Línea de comandos", [
                ("Cmd",            details.get("cmdline", "—")),
            ]),
        ]

        for sec_title, rows in sections:
            sec_lbl = QLabel(sec_title)
            sec_lbl.setStyleSheet("font-weight:700; font-size:10pt; margin-top:8px;")
            il.addWidget(sec_lbl)
            for key, val in rows:
                row_w = QHBoxLayout()
                k = QLabel(f"  {key}:")
                k.setStyleSheet("color:#94a3b8; min-width:130px;")
                v = QLabel(val)
                v.setWordWrap(True)
                v.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                row_w.addWidget(k)
                row_w.addWidget(v, stretch=1)
                il.addLayout(row_w)

        il.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)

        from PyQt6.QtWidgets import QDialogButtonBox
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(dlg.reject)
        layout.addWidget(bb)
        dlg.exec()

    def _export_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar procesos",
            f"procesos_{datetime.now():%Y%m%d_%H%M}.csv",
            "CSV (*.csv)"
        )
        if not path:
            return
        try:
            csv_data = export_processes_csv()
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(csv_data)
            QMessageBox.information(self, "Exportar", f"Guardado:\n{path}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"No se pudo exportar:\n{e}")

    # ------------------------------------------------------------------
    # Menú contextual
    # ------------------------------------------------------------------

    def _context_menu(self, pos) -> None:
        p = self._selected_process()
        if not p:
            return

        menu = QMenu(self)
        menu.setObjectName("ContextMenu")

        act_details = menu.addAction("🔍 Ver detalles")
        menu.addSeparator()
        act_kill     = menu.addAction("✕ Finalizar proceso")
        act_kill_tree = menu.addAction("✕ Finalizar árbol de procesos")
        menu.addSeparator()
        act_suspend  = menu.addAction("⏸ Suspender")
        act_resume   = menu.addAction("▶ Reanudar")
        menu.addSeparator()
        prio_menu    = menu.addMenu("⬆ Cambiar prioridad")
        for opt in get_priority_options():
            prio_menu.addAction(opt)
        menu.addSeparator()
        act_folder   = menu.addAction("📁 Abrir ubicación")

        action = menu.exec(self._view.viewport().mapToGlobal(pos))
        if action is None:
            return

        if action == act_details:    self._show_details()
        elif action == act_kill:     self._kill()
        elif action == act_kill_tree: self._kill_tree()
        elif action == act_suspend:  self._suspend()
        elif action == act_resume:   self._resume_proc()
        elif action == act_folder:   self._open_folder()
        elif action.parent() == prio_menu:
            ok, msg = change_priority(p["pid"], action.text())
            self._result_msg(ok, msg, "Prioridad")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _result_msg(self, ok: bool, msg: str, title: str) -> None:
        if ok:
            QMessageBox.information(self, title, msg)
        else:
            QMessageBox.warning(self, f"Error — {title}", msg)
