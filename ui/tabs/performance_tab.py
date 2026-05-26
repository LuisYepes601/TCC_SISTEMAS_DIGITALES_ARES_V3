"""
ui/tabs/performance_tab.py
Pestaña de rendimiento — usa señales del MetricsWorker.
Sin timer propio: elimina el doble-polling del sistema anterior.
"""

from __future__ import annotations

from collections import deque

import pyqtgraph as pg
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from core.services.system_service import (
    get_cpu_count_logical,
    get_cpu_count_physical,
    get_cpu_name,
    get_disk_mount_choices,
    get_gpu_info,
)
from ui.styles.performance_palette import (
    COLOR_CPU, COLOR_DISK, COLOR_GPU, COLOR_MEM, COLOR_WIFI,
    palette_for_theme,
)
from ui.styles.theme import THEME_DARK, THEME_LIGHT, saved_theme
from ui.widgets.resource_card import ResourceCard

pg.setConfigOptions(antialias=True)
MAX_POINTS = 60


class PerformanceTab(QWidget):
    def __init__(self, worker=None):
        super().__init__()
        self._worker   = worker
        self._theme    = saved_theme()
        self._palette  = palette_for_theme(self._theme)
        self._paused   = False

        self.disk_path    = get_disk_mount_choices()[0]
        self.wifi_max_mbps = 100.0

        self.cpu_data  = deque(maxlen=MAX_POINTS)
        self.mem_data  = deque(maxlen=MAX_POINTS)
        self.disk_data = deque(maxlen=MAX_POINTS)
        self.wifi_data = deque(maxlen=MAX_POINTS)
        self.gpu_data  = deque(maxlen=MAX_POINTS)

        self._build_ui()
        self._connect_worker()

    # ------------------------------------------------------------------
    # Construcción de UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(8)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(splitter)

        # ── Panel izquierdo: tarjetas ──────────────────────────────────
        scroll_left = QScrollArea()
        scroll_left.setMinimumWidth(310)
        scroll_left.setMaximumWidth(330)
        scroll_left.setWidgetResizable(False)
        scroll_left.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_left.setFrameShape(QFrame.Shape.NoFrame)

        left_frame = QFrame()
        left_layout = QVBoxLayout(left_frame)
        left_layout.setSpacing(10)
        left_layout.setContentsMargins(10, 10, 10, 10)

        p = self._palette
        self.card_cpu  = ResourceCard("cpu",  "CPU",     COLOR_CPU,  p)
        self.card_mem  = ResourceCard("mem",  "Memoria", COLOR_MEM,  p)
        self.card_disk = ResourceCard("disk", "Disco",   COLOR_DISK, p)
        self.card_wifi = ResourceCard("wifi", "Red",     COLOR_WIFI, p)
        self.card_gpu  = ResourceCard("gpu",  "GPU",     COLOR_GPU,  p)
        self.cards = [self.card_cpu, self.card_mem, self.card_disk,
                      self.card_wifi, self.card_gpu]

        for card in self.cards:
            card.on_click = self._on_card_click
            card.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            card.setFixedSize(138, 126)

        grid = QGridLayout()
        grid.setSpacing(8)
        for i, card in enumerate(self.cards):
            grid.addWidget(card, i // 2, i % 2)
        left_layout.addLayout(grid)
        left_layout.addSpacing(8)

        # Salud del sistema
        hf = QFrame()
        hl = QVBoxLayout(hf)
        hl.setContentsMargins(8, 8, 8, 8)
        hl.setSpacing(4)
        ht = QLabel("🏥 Salud del sistema")
        ht.setObjectName("HealthTitle")
        self._health_bar = QProgressBar()
        self._health_bar.setRange(0, 100)
        self._health_bar.setTextVisible(True)
        self._health_bar.setObjectName("HealthBar")
        self._health_desc = QLabel("—")
        self._health_desc.setObjectName("HealthDesc")
        hl.addWidget(ht)
        hl.addWidget(self._health_bar)
        hl.addWidget(self._health_desc)
        left_layout.addWidget(hf)
        left_layout.addStretch()
        scroll_left.setWidget(left_frame)
        splitter.addWidget(scroll_left)

        # ── Panel derecho: detalle ─────────────────────────────────────
        scroll_right = QScrollArea()
        scroll_right.setWidgetResizable(True)
        scroll_right.setFrameShape(QFrame.Shape.NoFrame)

        self._detail = QFrame()
        self._detail.setMinimumWidth(320)
        dl = QVBoxLayout(self._detail)
        dl.setContentsMargins(10, 10, 10, 10)
        dl.setSpacing(6)

        # Título + subtítulo
        tr = QHBoxLayout()
        self._main_title = QLabel("CPU")
        self._main_sub   = QLabel("% de uso")
        tr.addWidget(self._main_title)
        tr.addStretch()
        tr.addWidget(self._main_sub)
        dl.addLayout(tr)
        self._comp_info = QLabel("")
        dl.addWidget(self._comp_info)

        # Configuraciones
        cfg_grp = QGroupBox("Configuraciones")
        cfg_layout = QVBoxLayout(cfg_grp)
        cfg_layout.setSpacing(3)
        cfg_layout.setContentsMargins(6, 6, 6, 6)

        self._disk_row = QHBoxLayout()
        self._disk_lbl = QLabel("Unidad:")
        self._disk_combo = QComboBox()
        for d in get_disk_mount_choices():
            self._disk_combo.addItem(d)
        self._disk_combo.currentTextChanged.connect(self._on_disk_changed)
        self._disk_row.addWidget(self._disk_lbl)
        self._disk_row.addWidget(self._disk_combo)
        self._disk_row.addStretch()
        cfg_layout.addLayout(self._disk_row)

        self._wifi_row = QHBoxLayout()
        self._wifi_lbl = QLabel("Vel. máx.:")
        self._wifi_combo = QComboBox()
        for val in ["50", "100", "300", "600", "1000"]:
            self._wifi_combo.addItem(f"{val} Mbit/s", float(val))
        self._wifi_combo.setCurrentIndex(1)
        self._wifi_combo.currentIndexChanged.connect(self._on_wifi_changed)
        self._wifi_row.addWidget(self._wifi_lbl)
        self._wifi_row.addWidget(self._wifi_combo)
        self._wifi_row.addStretch()
        cfg_layout.addLayout(self._wifi_row)

        self._cfg_placeholder = QLabel("Sin configuraciones adicionales")
        self._cfg_placeholder.setStyleSheet("color: #9ca3af; font-size: 9pt;")
        cfg_layout.addWidget(self._cfg_placeholder)
        dl.addWidget(cfg_grp)

        # Gráfico principal
        self._plot = pg.PlotWidget()
        self._plot.setMinimumHeight(100)
        self._plot.setMaximumHeight(160)
        self._plot.setYRange(0, 100)
        self._plot.setMouseEnabled(False, False)
        self._plot.getViewBox().setBorder(None)
        self._curve = self._plot.plot(
            pen=pg.mkPen(COLOR_CPU, width=2.5),
            fillLevel=0,
            fillBrush=pg.mkBrush(self._palette.fill_cpu),
        )
        dl.addWidget(self._plot)

        # Estadísticas
        stats_grp = QGroupBox("Estadísticas")
        sg = QGridLayout(stats_grp)
        sg.setSpacing(3)
        sg.setContentsMargins(6, 6, 6, 6)
        self._stat_keys: list[QLabel] = []
        self._stat_vals: dict[str, QLabel] = {}
        for i, (key, lbl) in enumerate([
            ("uso",    "Uso"),
            ("vel",    "Velocidad"),
            ("e1",     "Núcleos físicos"),
            ("e2",     "Núcleos lógicos"),
            ("e3",     "Desglose"),
        ]):
            kl = QLabel(lbl)
            kl.setStyleSheet("padding-right:8px;")
            sg.addWidget(kl, i, 0)
            self._stat_keys.append(kl)
            vl = QLabel("—")
            vl.setWordWrap(True)
            sg.addWidget(vl, i, 1)
            self._stat_vals[key] = vl
        dl.addWidget(stats_grp)
        dl.addSpacing(8)

        # Barras por núcleo
        self._cores_grp = QGroupBox("Núcleos de CPU")
        cl = QVBoxLayout(self._cores_grp)
        cl.setContentsMargins(6, 6, 6, 6)
        cl.setSpacing(2)
        self._core_grid = QGridLayout()
        self._core_grid.setSpacing(4)
        cl.addLayout(self._core_grid)
        self._core_widgets: list[tuple[QLabel, QProgressBar]] = []
        self._init_core_bars()
        dl.addWidget(self._cores_grp)
        dl.addSpacing(20)

        scroll_right.setWidget(self._detail)
        splitter.addWidget(scroll_right)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([330, 600])

        # Estado inicial
        self.selected = "cpu"
        self.card_cpu.set_selected(True)
        self._update_detail_visibility()
        self._apply_styles()

    def _init_core_bars(self) -> None:
        count = get_cpu_count_logical() or 4
        cols  = 4 if count > 4 else 2
        self._core_widgets.clear()
        for i in range(count):
            row, col = divmod(i, cols)
            lbl = QLabel(f"C{i}")
            lbl.setObjectName("CoreLabel")
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setFixedHeight(14)
            bar.setTextVisible(False)
            bar.setObjectName("CoreBar")
            cell_w = QWidget()
            cell_l = QVBoxLayout(cell_w)
            cell_l.setSpacing(1)
            cell_l.setContentsMargins(0, 0, 0, 0)
            cell_l.addWidget(lbl)
            cell_l.addWidget(bar)
            self._core_grid.addWidget(cell_w, row, col)
            self._core_widgets.append((lbl, bar))

    # ------------------------------------------------------------------
    # Conexión con el worker
    # ------------------------------------------------------------------

    def _connect_worker(self) -> None:
        if self._worker:
            self._worker.system_ready.connect(self._on_data)

    # ------------------------------------------------------------------
    # Slot principal de datos
    # ------------------------------------------------------------------

    def _on_data(self, d: dict) -> None:
        if self._paused:
            return

        cpu       = d.get("cpu", 0)
        cores     = d.get("cpu_cores", [])
        mem_pct   = d.get("mem_pct", 0)
        mem_used  = d.get("mem_used", 0)
        mem_total = d.get("mem_total", 0)
        mem_det   = d.get("mem_details", {})
        disk_pct  = d.get("disk_pct", 0)
        disk_used = d.get("disk_used", 0)
        disk_total = d.get("disk_total", 0)
        gpu_pct   = d.get("gpu_pct")
        gpu_name  = d.get("gpu_name", "GPU")
        wifi_pct  = d.get("wifi_pct", 0)
        total_mbps = d.get("total_mbps", 0)
        sent_rate  = d.get("sent_rate", 0)
        recv_rate  = d.get("recv_rate", 0)
        score      = d.get("health_score", 0)
        hdesc      = d.get("health_desc", "—")
        freq       = d.get("cpu_freq")
        cpu_times  = d.get("cpu_times", {})
        read_mbs   = d.get("disk_read_mbs", 0)
        write_mbs  = d.get("disk_write_mbs", 0)

        gpu_val = gpu_pct if gpu_pct is not None else 0.0

        # Acumular histórico
        self.cpu_data.append(cpu)
        self.mem_data.append(mem_pct)
        self.disk_data.append(disk_pct)
        self.wifi_data.append(wifi_pct)
        self.gpu_data.append(gpu_val)

        # Tarjetas
        freq_str = f"{freq[0] / 1000:.2f} GHz" if freq and freq[0] else "—"
        self.card_cpu.update_data(list(self.cpu_data))
        self.card_cpu.stats_label.setText(f"{cpu:.0f}%  {freq_str}")
        self.card_mem.update_data(list(self.mem_data))
        self.card_mem.stats_label.setText(f"{mem_used:.1f}/{mem_total:.1f} GB ({mem_pct:.0f}%)")
        self.card_disk.update_data(list(self.disk_data))
        self.card_disk.stats_label.setText(
            f"{disk_used:.1f}/{disk_total:.1f} GB ({disk_pct:.0f}%)")
        self.card_wifi.update_data(list(self.wifi_data))
        self.card_wifi.stats_label.setText(f"{wifi_pct:.1f}%  {total_mbps:.1f} Mbit/s")
        self.card_gpu.update_data(list(self.gpu_data))
        self.card_gpu.stats_label.setText(
            f"{gpu_val:.0f}%" if gpu_pct is not None else "Sin métricas")

        # Barras de núcleo
        for i, (_, bar) in enumerate(self._core_widgets):
            v = int(cores[i]) if i < len(cores) else 0
            bar.setValue(v)
            c = "#ef4444" if v >= 90 else ("#fb923c" if v >= 75 else COLOR_CPU)
            bar.setStyleSheet(
                f"QProgressBar::chunk {{ background:{c}; border-radius:3px; }}")

        # Salud
        self._health_bar.setValue(int(score))
        self._health_bar.setFormat(f"{score:.0f}%")
        self._health_desc.setText(hdesc)
        hc = "#22c55e" if score >= 70 else ("#facc15" if score >= 50 else "#ef4444")
        self._health_bar.setStyleSheet(
            f"QProgressBar::chunk {{ background:{hc}; border-radius:4px; }}")

        # Gráfico y estadísticas del recurso seleccionado
        self._update_curve()
        r = self.selected
        if r == "cpu":
            self._stat_vals["uso"].setText(f"{cpu:.1f}%")
            self._stat_vals["vel"].setText(freq_str)
            self._stat_vals["e1"].setText(str(get_cpu_count_physical()))
            self._stat_vals["e2"].setText(str(get_cpu_count_logical()))
            u = cpu_times.get("user", 0); s = cpu_times.get("system", 0)
            io = cpu_times.get("iowait", 0)
            self._stat_vals["e3"].setText(f"U:{u:.0f}%  S:{s:.0f}%  IO:{io:.0f}%")
        elif r == "mem":
            swap_u = mem_det.get("swap_used_gb", 0)
            swap_t = mem_det.get("swap_total_gb", 0)
            swap_p = mem_det.get("swap_percent", 0)
            buf = mem_det.get("buffers_gb", 0)
            cach = mem_det.get("cached_gb", 0)
            self._stat_vals["uso"].setText(f"{mem_pct:.1f}%")
            self._stat_vals["vel"].setText(f"Libre: {mem_det.get('available_gb', 0):.2f} GB")
            self._stat_vals["e1"].setText(f"Usado: {mem_used:.2f} GB")
            self._stat_vals["e2"].setText(f"Total: {mem_total:.2f} GB")
            self._stat_vals["e3"].setText(
                f"Swap: {swap_u:.1f}/{swap_t:.1f} GB ({swap_p:.0f}%)  "
                f"Buf: {buf:.2f}  Caché: {cach:.2f} GB")
        elif r == "disk":
            self._stat_vals["uso"].setText(f"{disk_pct:.1f}%")
            self._stat_vals["vel"].setText(
                f"▲ {read_mbs:.2f} MB/s  ▼ {write_mbs:.2f} MB/s")
            self._stat_vals["e1"].setText(f"Usado: {disk_used:.2f} GB")
            self._stat_vals["e2"].setText(f"Total: {disk_total:.2f} GB")
            self._stat_vals["e3"].setText(f"Libre: {disk_total - disk_used:.2f} GB")
        elif r == "wifi":
            self._stat_vals["uso"].setText(f"{wifi_pct:.1f}%")
            self._stat_vals["vel"].setText(f"{total_mbps:.2f} Mbit/s")
            self._stat_vals["e1"].setText(f"↑ Envío:    {sent_rate/1024:.1f} KB/s")
            self._stat_vals["e2"].setText(f"↓ Recep.:   {recv_rate/1024:.1f} KB/s")
            self._stat_vals["e3"].setText("—")
        else:  # gpu
            if gpu_pct is not None:
                self._stat_vals["uso"].setText(f"{gpu_val:.1f}%")
                self._stat_vals["vel"].setText(gpu_name)
            else:
                self._stat_vals["uso"].setText("—")
                self._stat_vals["vel"].setText(f"{gpu_name} (sin datos)")
            for k in ("e1", "e2", "e3"):
                self._stat_vals[k].setText("—")

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def pause_updates(self, should_pause: bool) -> None:
        self._paused = should_pause
        self._plot.setUpdatesEnabled(not should_pause)

    def set_app_theme(self, theme: str) -> None:
        self._theme   = theme
        self._palette = palette_for_theme(theme)
        for card in self.cards:
            card.set_palette(self._palette)
        self._apply_styles()
        self._update_curve_style()

    # ------------------------------------------------------------------
    # Slots internos
    # ------------------------------------------------------------------

    def _on_card_click(self, resource_id: str) -> None:
        self.selected = resource_id
        for card in self.cards:
            card.set_selected(card.resource_id == resource_id)
        self._update_detail_visibility()
        self._update_curve_style()
        self._update_stat_headers()

    def _on_disk_changed(self, drive: str) -> None:
        if drive:
            self.disk_path = drive
            if self._worker:
                self._worker.update_disk_path(drive)

    def _on_wifi_changed(self, idx: int) -> None:
        v = self._wifi_combo.itemData(idx)
        self.wifi_max_mbps = float(v) if v else 100.0
        if self._worker:
            self._worker.wifi_max_mbps = self.wifi_max_mbps

    # ------------------------------------------------------------------
    # Helpers de UI
    # ------------------------------------------------------------------

    def _update_detail_visibility(self) -> None:
        r = self.selected
        for wid in (self._disk_lbl, self._disk_combo):
            wid.setVisible(r == "disk")
        for wid in (self._wifi_lbl, self._wifi_combo):
            wid.setVisible(r == "wifi")
        self._cfg_placeholder.setVisible(r not in ("disk", "wifi"))
        self._cores_grp.setVisible(r == "cpu")

        titles = {
            "cpu":  ("CPU",     "% de uso"),
            "mem":  ("Memoria", "uso RAM"),
            "disk": ("Disco",   "I/O"),
            "wifi": ("Red",     "tráfico"),
            "gpu":  ("GPU",     "% de uso"),
        }
        t, s = titles.get(r, ("—", ""))
        self._main_title.setText(t)
        self._main_sub.setText(s)

        if r == "cpu":
            self._comp_info.setText(get_cpu_name())
        elif r == "gpu":
            _, gname = get_gpu_info()
            self._comp_info.setText(gname)
        else:
            self._comp_info.setText("")

    def _update_curve_style(self) -> None:
        p = self._palette
        fill_map = {
            "cpu":  (COLOR_CPU,  p.fill_cpu),
            "mem":  (COLOR_MEM,  p.fill_mem),
            "disk": (COLOR_DISK, p.fill_disk),
            "wifi": (COLOR_WIFI, p.fill_wifi),
            "gpu":  (COLOR_GPU,  p.fill_gpu),
        }
        lc, fc = fill_map.get(self.selected, (COLOR_CPU, p.fill_cpu))
        self._curve.setPen(pg.mkPen(lc, width=2.5))
        self._curve.setBrush(pg.mkBrush(fc))

    def _update_curve(self) -> None:
        data = {
            "cpu":  list(self.cpu_data),
            "mem":  list(self.mem_data),
            "disk": list(self.disk_data),
            "wifi": list(self.wifi_data),
            "gpu":  list(self.gpu_data),
        }.get(self.selected, [])
        self._curve.setData(list(range(len(data))), data)

    def _update_stat_headers(self) -> None:
        labels = {
            "cpu":  ["Uso", "Velocidad", "Núcleos físicos", "Núcleos lógicos", "Desglose (U/S/IO)"],
            "mem":  ["Uso", "Libre", "Usado", "Total", "Swap / Buf / Caché"],
            "disk": ["Uso", "Velocidad I/O", "Usado", "Total", "Libre"],
            "wifi": ["Uso", "Velocidad", "↑ Envío", "↓ Recepción", "—"],
            "gpu":  ["Uso", "Modelo", "—", "—", "—"],
        }
        for lbl, text in zip(self._stat_keys, labels.get(self.selected, [])):
            lbl.setText(text)

    def _apply_styles(self) -> None:
        p = self._palette
        self.setStyleSheet(f"background-color:{p.bg}; color:{p.text_primary};")
        self._detail.setStyleSheet(
            f"QFrame {{ background-color:{p.bg_elevated}; border-radius:16px; "
            f"border:1px solid {p.card_border}; }}"
        )
        self._plot.setBackground(p.bg_elevated)
        self._plot.showGrid(x=True, y=True, alpha=p.grid_alpha)
        self._plot.getAxis("bottom").setPen(pg.mkPen(p.axis_color, width=1))
        self._plot.getAxis("left").setPen(pg.mkPen(p.axis_color, width=1))
        self._main_title.setStyleSheet(
            f"color:{p.text_primary}; font-size:15pt; font-weight:600;")
        self._main_sub.setStyleSheet(f"color:{p.text_secondary}; font-size:10pt;")
        self._comp_info.setStyleSheet(f"color:{p.text_secondary}; font-size:9pt;")
        for lbl in self._stat_keys:
            lbl.setStyleSheet(f"color:{p.text_secondary}; font-size:9pt;")
        for val in self._stat_vals.values():
            val.setStyleSheet(
                f"color:{p.text_primary}; font-size:11pt; font-weight:bold;")
