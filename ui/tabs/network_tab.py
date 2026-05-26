"""
ui/tabs/network_tab.py
Pestaña de red — auto-refresh, tasas en tiempo real, estadísticas por interfaz.
"""

from __future__ import annotations

from collections import deque, defaultdict

import pyqtgraph as pg
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.services.system_service import (
    get_connections,
    get_net_if_stats,
    get_network_io,
    get_network_io_per_interface,
)
from core.utils.formatters import bytes_to_mb, bytes_per_sec_human, connection_status_label

MAX_PTS = 60


class NetworkTab(QWidget):
    def __init__(self, worker=None):
        super().__init__()
        self._worker = worker
        self._paused = False

        # Histórico de tasas por interfaz: iface → deque de (sent_rate, recv_rate)
        self._if_history: dict[str, deque] = defaultdict(lambda: deque(maxlen=MAX_PTS))
        self._if_prev: dict[str, tuple[int, int]] = {}   # iface → (sent, recv) anterior

        # Tasas globales para el gráfico principal
        self._sent_hist = deque(maxlen=MAX_PTS)
        self._recv_hist = deque(maxlen=MAX_PTS)

        self._build_ui()

        if worker:
            worker.system_ready.connect(self._on_system_data)
            worker.net_if_ready.connect(self._on_if_data)
        else:
            self._timer = QTimer(self)
            self._timer.timeout.connect(self._fallback_refresh)
            self._timer.start(2000)
            self._fallback_refresh()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # ── Fila superior: totales acumulados ──────────────────────────
        totals_row = QHBoxLayout()
        self._lbl_sent  = self._stat_card("↑ Enviado",   "—")
        self._lbl_recv  = self._stat_card("↓ Recibido",  "—")
        self._lbl_speed = self._stat_card("⚡ Velocidad actual", "—")
        self._lbl_conns = self._stat_card("🔗 Conexiones", "—")
        for w in (self._lbl_sent, self._lbl_recv, self._lbl_speed, self._lbl_conns):
            totals_row.addWidget(w)
        root.addLayout(totals_row)

        # ── Splitter vertical: gráfico + tablas ────────────────────────
        vsplit = QSplitter(Qt.Orientation.Vertical)

        # Gráfico de tasas globales
        graph_frame = QFrame()
        graph_frame.setFrameShape(QFrame.Shape.StyledPanel)
        gfl = QVBoxLayout(graph_frame)
        gfl.setContentsMargins(8, 8, 8, 8)
        gfl.setSpacing(4)

        gh = QHBoxLayout()
        gh.addWidget(QLabel("📈 Tráfico de red en tiempo real"))
        gh.addStretch()
        self._lbl_sent_rate = QLabel("↑ 0 B/s")
        self._lbl_sent_rate.setStyleSheet("color:#4ade80; font-weight:700;")
        self._lbl_recv_rate = QLabel("↓ 0 B/s")
        self._lbl_recv_rate.setStyleSheet("color:#22d3ee; font-weight:700;")
        gh.addWidget(self._lbl_sent_rate)
        gh.addSpacing(16)
        gh.addWidget(self._lbl_recv_rate)
        gfl.addLayout(gh)

        self._net_plot = pg.PlotWidget()
        self._net_plot.setFixedHeight(130)
        self._net_plot.setYRange(0, 1)
        self._net_plot.setMouseEnabled(False, False)
        self._net_plot.getViewBox().setBorder(None)
        self._net_plot.showGrid(x=True, y=True, alpha=0.12)
        self._net_plot.setLabel("left", "KB/s")
        self._net_plot.getAxis("bottom").hide()

        self._curve_sent = self._net_plot.plot(
            pen=pg.mkPen("#4ade80", width=2),
            fillLevel=0, fillBrush=pg.mkBrush("#4ade8033"), name="↑ Envío"
        )
        self._curve_recv = self._net_plot.plot(
            pen=pg.mkPen("#22d3ee", width=2),
            fillLevel=0, fillBrush=pg.mkBrush("#22d3ee33"), name="↓ Recepción"
        )
        legend = self._net_plot.addLegend(offset=(10, 10))
        gfl.addWidget(self._net_plot)
        vsplit.addWidget(graph_frame)

        # ── Splitter horizontal: interfaces + conexiones ───────────────
        hsplit = QSplitter(Qt.Orientation.Horizontal)

        # Tabla de interfaces
        if_grp = QGroupBox("🌐 Interfaces de red")
        ifl = QVBoxLayout(if_grp)
        ifl.setContentsMargins(6, 6, 6, 6)

        self._if_table = QTableWidget()
        self._if_table.setColumnCount(7)
        self._if_table.setHorizontalHeaderLabels(
            ["Interfaz", "Estado", "↑ Envío", "↓ Recepción",
             "Pkts ↑", "Pkts ↓", "Velocidad max"])
        self._if_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents)
        self._if_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents)
        for c in (2, 3):
            self._if_table.horizontalHeader().setSectionResizeMode(
                c, QHeaderView.ResizeMode.Stretch)
        self._if_table.setAlternatingRowColors(True)
        self._if_table.setSortingEnabled(True)
        self._if_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._if_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        ifl.addWidget(self._if_table)
        hsplit.addWidget(if_grp)

        # Tabla de conexiones
        conn_grp = QGroupBox("🔗 Conexiones activas (TCP/UDP IPv4)")
        cl = QVBoxLayout(conn_grp)
        cl.setContentsMargins(6, 6, 6, 6)

        btn_bar = QHBoxLayout()
        self._btn_refresh_conn = QPushButton("↻ Actualizar conexiones")
        self._btn_refresh_conn.clicked.connect(self._refresh_connections)
        btn_bar.addWidget(self._btn_refresh_conn)
        btn_bar.addStretch()
        self._lbl_conn_count = QLabel("")
        btn_bar.addWidget(self._lbl_conn_count)
        cl.addLayout(btn_bar)

        self._conn_table = QTableWidget()
        self._conn_table.setColumnCount(5)
        self._conn_table.setHorizontalHeaderLabels(
            ["Dirección local", "Dirección remota", "Proto", "Estado", "PID"])
        self._conn_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        self._conn_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch)
        self._conn_table.setAlternatingRowColors(True)
        self._conn_table.setSortingEnabled(True)
        self._conn_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        cl.addWidget(self._conn_table)
        hsplit.addWidget(conn_grp)
        hsplit.setSizes([420, 500])

        vsplit.addWidget(hsplit)
        vsplit.setSizes([160, 400])
        root.addWidget(vsplit, stretch=1)

        # Actualizar conexiones al inicio
        self._refresh_connections()

    # ------------------------------------------------------------------
    # Slots de datos
    # ------------------------------------------------------------------

    def _on_system_data(self, d: dict) -> None:
        if self._paused:
            return

        sent_rate = d.get("sent_rate", 0)
        recv_rate = d.get("recv_rate", 0)

        # Historial para el gráfico
        self._sent_hist.append(sent_rate / 1024)   # KB/s
        self._recv_hist.append(recv_rate / 1024)

        xs = list(range(len(self._sent_hist)))
        self._curve_sent.setData(xs, list(self._sent_hist))
        self._curve_recv.setData(xs, list(self._recv_hist))

        # Ajustar Y automáticamente
        max_y = max(max(self._sent_hist, default=1), max(self._recv_hist, default=1))
        self._net_plot.setYRange(0, max_y * 1.1 or 1)

        # Labels de velocidad en tiempo real
        self._lbl_sent_rate.setText(f"↑ {bytes_per_sec_human(sent_rate)}")
        self._lbl_recv_rate.setText(f"↓ {bytes_per_sec_human(recv_rate)}")

        # Totales acumulados (obtenidos del worker directamente)
        sent_total, recv_total = get_network_io()
        self._lbl_sent.findChild(QLabel, "val").setText(bytes_to_mb(sent_total))
        self._lbl_recv.findChild(QLabel, "val").setText(bytes_to_mb(recv_total))
        mbps = (sent_rate + recv_rate) * 8 / (1024 * 1024)
        self._lbl_speed.findChild(QLabel, "val").setText(f"{mbps:.2f} Mbit/s")

    def _on_if_data(self, data: dict) -> None:
        if self._paused:
            return
        stats = get_net_if_stats()

        self._if_table.setSortingEnabled(False)
        self._if_table.setRowCount(len(data))

        for row, (iface, counters) in enumerate(sorted(data.items())):
            st = stats.get(iface, {})
            is_up  = st.get("isup", False)
            speed  = st.get("speed", 0)

            # Calcular tasa delta
            sent_now = counters["bytes_sent"]
            recv_now = counters["bytes_recv"]
            if iface in self._if_prev:
                s_prev, r_prev = self._if_prev[iface]
                s_rate = max(0, sent_now - s_prev)
                r_rate = max(0, recv_now - r_prev)
            else:
                s_rate = r_rate = 0
            self._if_prev[iface] = (sent_now, recv_now)

            self._if_table.setItem(row, 0, QTableWidgetItem(iface))
            status_item = QTableWidgetItem("● Activa" if is_up else "○ Inactiva")
            status_item.setForeground(
                __import__("PyQt6.QtGui", fromlist=["QColor"]).QColor(
                    "#22c55e" if is_up else "#94a3b8"))
            self._if_table.setItem(row, 1, status_item)
            self._if_table.setItem(row, 2, QTableWidgetItem(bytes_per_sec_human(s_rate)))
            self._if_table.setItem(row, 3, QTableWidgetItem(bytes_per_sec_human(r_rate)))
            self._if_table.setItem(row, 4,
                QTableWidgetItem(f"{counters['packets_sent']:,}"))
            self._if_table.setItem(row, 5,
                QTableWidgetItem(f"{counters['packets_recv']:,}"))
            speed_str = f"{speed} Mbit/s" if speed else "—"
            self._if_table.setItem(row, 6, QTableWidgetItem(speed_str))

        self._if_table.setSortingEnabled(True)

    # ------------------------------------------------------------------
    # Conexiones (refresh manual + auto cada 5 s)
    # ------------------------------------------------------------------

    def _refresh_connections(self) -> None:
        self._btn_refresh_conn.setEnabled(False)
        self._btn_refresh_conn.setText("Cargando…")
        try:
            conns = get_connections(kind="inet")
            self._conn_table.setSortingEnabled(False)
            self._conn_table.setRowCount(len(conns))

            for row, c in enumerate(conns):
                self._conn_table.setItem(row, 0, QTableWidgetItem(c["laddr"]))
                self._conn_table.setItem(row, 1, QTableWidgetItem(c["raddr"]))
                self._conn_table.setItem(row, 2, QTableWidgetItem(c.get("proto", "TCP")))
                st_item = QTableWidgetItem(connection_status_label(str(c["status"])))
                color_map = {
                    "ESTABLISHED": "#22c55e",
                    "LISTEN":      "#60a5fa",
                    "TIME_WAIT":   "#fb923c",
                    "CLOSE_WAIT":  "#facc15",
                }
                col = color_map.get(str(c["status"]).upper(), "#94a3b8")
                st_item.setForeground(
                    __import__("PyQt6.QtGui", fromlist=["QColor"]).QColor(col))
                self._conn_table.setItem(row, 3, st_item)
                self._conn_table.setItem(row, 4, QTableWidgetItem(str(c["pid"])))

            self._conn_table.setSortingEnabled(True)
            self._lbl_conn_count.setText(f"{len(conns)} conexiones")
            self._lbl_conns.findChild(QLabel, "val").setText(str(len(conns)))
        except Exception as e:
            self._lbl_conn_count.setText(f"Error: {e}")
        finally:
            self._btn_refresh_conn.setEnabled(True)
            self._btn_refresh_conn.setText("↻ Actualizar conexiones")

    def _fallback_refresh(self) -> None:
        """Actualización sin worker: tasas manuales."""
        import time as _t
        if not hasattr(self, "_fb_prev_t"):
            self._fb_prev_t = _t.perf_counter()
            self._fb_prev_io = get_network_io()
            return

        now = _t.perf_counter()
        sent, recv = get_network_io()
        el = now - self._fb_prev_t
        if el > 0:
            s_rate = (sent - self._fb_prev_io[0]) / el
            r_rate = (recv - self._fb_prev_io[1]) / el
        else:
            s_rate = r_rate = 0.0
        self._fb_prev_io = (sent, recv)
        self._fb_prev_t  = now

        fake = {"sent_rate": s_rate, "recv_rate": r_rate}
        self._on_system_data(fake)
        if_data = get_network_io_per_interface()
        self._on_if_data(if_data)

        # Actualizar conexiones cada 5 llamadas
        if not hasattr(self, "_fb_tick"):
            self._fb_tick = 0
        self._fb_tick += 1
        if self._fb_tick % 5 == 0:
            self._refresh_connections()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def pause_updates(self, should_pause: bool) -> None:
        self._paused = should_pause
        if hasattr(self, "_timer"):
            if should_pause:
                self._timer.stop()
            else:
                self._timer.start(2000)

    @staticmethod
    def _stat_card(title: str, value: str) -> QFrame:
        """Mini tarjeta con título y valor."""
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setMinimumWidth(140)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)
        tlbl = QLabel(title)
        tlbl.setStyleSheet("color:#94a3b8; font-size:8.5pt;")
        vlbl = QLabel(value)
        vlbl.setObjectName("val")
        vlbl.setStyleSheet("font-weight:700; font-size:11pt;")
        layout.addWidget(tlbl)
        layout.addWidget(vlbl)
        return frame
