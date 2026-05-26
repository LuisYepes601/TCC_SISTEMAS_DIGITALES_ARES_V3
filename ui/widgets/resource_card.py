"""ui/widgets/resource_card.py"""
import pyqtgraph as pg
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QLabel, QSizePolicy, QVBoxLayout
from ui.styles.performance_palette import PerformancePalette

class ResourceCard(QFrame):
    def __init__(self, resource_id, title, line_color, palette, parent=None):
        super().__init__(parent)
        self.setObjectName("ResourceCard"); self.resource_id = resource_id
        self.line_color = line_color; self._palette = palette; self.on_click = None
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(self); layout.setSpacing(4); layout.setContentsMargins(8,8,8,8)
        self.title_label = QLabel(title); layout.addWidget(self.title_label)
        self.mini_plot = pg.PlotWidget(); self.mini_plot.setFixedHeight(48)
        self.mini_plot.setYRange(0,100); self.mini_plot.setMouseEnabled(False,False)
        self.mini_plot.getViewBox().setBorder(None)
        for ax in ("left","bottom"): self.mini_plot.getAxis(ax).setPen(pg.mkPen("transparent"))
        pen = pg.mkPen(line_color, width=1.5); pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        self.mini_curve = self.mini_plot.plot(pen=pen); self.mini_curve.setCurveClickable(False)
        layout.addWidget(self.mini_plot)
        self.stats_label = QLabel("--"); layout.addWidget(self.stats_label)
        self._apply_styles()
    def set_palette(self, p): self._palette = p; self._apply_styles()
    def set_selected(self, sel):
        self.setProperty("selected","true" if sel else "false")
        self.style().unpolish(self); self.style().polish(self)
    def update_data(self, data): self.mini_curve.setData(list(range(len(data))), data)
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.on_click: self.on_click(self.resource_id)
        super().mousePressEvent(e)
    def _apply_styles(self):
        p = self._palette; lc = self.line_color
        self.setStyleSheet(f"""
            #ResourceCard{{background-color:{p.bg_card};border:1px solid {p.card_border};border-radius:10px;padding:10px;}}
            #ResourceCard:hover{{background-color:{p.card_hover};}}
            #ResourceCard[selected="true"]{{background-color:{p.card_selected};border-color:{lc};}}""")
        self.title_label.setStyleSheet(f"color:{p.text_primary};font-weight:600;font-size:10pt;")
        self.mini_plot.setBackground(p.bg_elevated); self.mini_plot.showGrid(x=True,y=True,alpha=p.grid_alpha)
        self.stats_label.setStyleSheet(f"color:{p.text_secondary};font-size:9pt;")
