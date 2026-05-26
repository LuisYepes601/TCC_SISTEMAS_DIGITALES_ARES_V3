"""
ui/models/process_model.py
Modelo de datos para la tabla de procesos.

Usa QAbstractTableModel + QSortFilterProxyModel en lugar de QTableWidget,
lo que permite renderizado virtualizado (solo las filas visibles) y
ordenación/filtrado sin reconstruir la tabla completa.
"""

from __future__ import annotations

from PyQt6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QSortFilterProxyModel,
    Qt,
    pyqtSignal,
)
from PyQt6.QtGui import QColor

from core.utils.formatters import nice_to_label, process_status_color, process_status_label


# Columnas: (encabezado, clave_dict, tipo_para_ordenar)
_COLS: list[tuple[str, str | None, type | None]] = [
    ("",          None,        None),       # 0  icono
    ("PID",       "pid",       int),        # 1
    ("Nombre",    "name",      str),        # 2
    ("CPU %",     "cpu",       float),      # 3
    ("Mem %",     "memory",    float),      # 4
    ("Mem MB",    "mem_mb",    float),      # 5
    ("Estado",    "status",    str),        # 6
    ("Hilos",     "threads",   int),        # 7
    ("Prioridad", "nice",      str),        # 8
    ("Usuario",   "user",      str),        # 9
]

# Colores CPU y Mem por umbral
_CPU_COLORS = [(80, "#ef4444"), (60, "#fb923c"), (30, "#facc15")]
_MEM_COLORS = [(85, "#ef4444"), (60, "#fb923c")]


def _threshold_color(value: float, thresholds: list[tuple[float, str]]) -> QColor | None:
    for limit, color in thresholds:
        if value >= limit:
            return QColor(color)
    return None


class ProcessModel(QAbstractTableModel):
    """Modelo de tabla de alto rendimiento para procesos del sistema."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[dict] = []

    # ------------------------------------------------------------------
    # Interfaz obligatoria de QAbstractTableModel
    # ------------------------------------------------------------------

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(_COLS)

    def headerData(self, section: int, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return _COLS[section][0]
        return None

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row, col = index.row(), index.column()
        if row >= len(self._rows):
            return None
        p = self._rows[row]

        if role == Qt.ItemDataRole.DisplayRole:
            return self._display(p, col)

        if role == Qt.ItemDataRole.DecorationRole and col == 0:
            from ui.widgets.process_icon import icon_for_exe
            return icon_for_exe(p.get("exe_path"))

        if role == Qt.ItemDataRole.ForegroundRole:
            return self._foreground(p, col)

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if col in (1, 3, 4, 5, 7):   # numéricos → alinear derecha
                return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        if role == Qt.ItemDataRole.UserRole:
            return self._sort_value(p, col)

        return None

    # ------------------------------------------------------------------
    # Actualización de datos
    # ------------------------------------------------------------------

    def update_processes(self, processes: list[dict]) -> None:
        self.beginResetModel()
        self._rows = processes
        self.endResetModel()

    def process_at_source_row(self, row: int) -> dict | None:
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return None

    # ------------------------------------------------------------------
    # Helpers privados
    # ------------------------------------------------------------------

    def _display(self, p: dict, col: int) -> str | None:
        if col == 0:  return None
        if col == 1:  return str(p.get("pid") or "")
        if col == 2:  return p.get("name") or ""
        if col == 3:  return f"{p.get('cpu', 0):.1f}"
        if col == 4:  return f"{p.get('memory', 0):.1f}"
        if col == 5:
            mb = p.get("mem_mb", 0)
            if mb >= 1024:
                return f"{mb / 1024:.2f} GB"
            return f"{mb:.0f} MB"
        if col == 6:  return process_status_label(p.get("status") or "")
        if col == 7:  return str(p.get("threads") or 0)
        if col == 8:  return nice_to_label(p.get("nice") or 0)
        if col == 9:  return p.get("user") or ""
        return None

    def _foreground(self, p: dict, col: int) -> QColor | None:
        if col == 3:
            return _threshold_color(p.get("cpu", 0), _CPU_COLORS)
        if col == 4:
            return _threshold_color(p.get("memory", 0), _MEM_COLORS)
        if col == 6:
            return QColor(process_status_color(p.get("status") or ""))
        return None

    def _sort_value(self, p: dict, col: int):
        if col == 1:  return p.get("pid") or 0
        if col == 3:  return p.get("cpu") or 0.0
        if col == 4:  return p.get("memory") or 0.0
        if col == 5:  return p.get("mem_mb") or 0.0
        if col == 7:  return p.get("threads") or 0
        return None


# ---------------------------------------------------------------------------
# Proxy con filtrado combinado
# ---------------------------------------------------------------------------

class ProcessFilterProxy(QSortFilterProxyModel):
    """Filtrado por nombre, CPU mínima, memoria mínima y estado."""

    count_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._name   = ""
        self._cpu    = 0.0
        self._mem    = 0.0
        self._status: str | None = None
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

    def set_filters(
        self,
        name: str = "",
        cpu: float = 0.0,
        mem: float = 0.0,
        status: str | None = None,
    ) -> None:
        self._name   = name.lower()
        self._cpu    = float(cpu)
        self._mem    = float(mem)
        self._status = status
        self.invalidateFilter()
        self.count_changed.emit(self.rowCount())

    def filterAcceptsRow(self, src_row: int, src_parent: QModelIndex) -> bool:
        m = self.sourceModel()
        if src_row >= m.rowCount():
            return False
        p = m._rows[src_row]

        if self._name and self._name not in (p.get("name") or "").lower():
            return False
        if p.get("cpu", 0) < self._cpu:
            return False
        if p.get("memory", 0) < self._mem:
            return False
        if self._status and (p.get("status") or "").lower() != self._status:
            return False
        return True

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        lv = left.data(Qt.ItemDataRole.UserRole)
        rv = right.data(Qt.ItemDataRole.UserRole)
        if lv is not None and rv is not None:
            try:
                return float(lv) < float(rv)
            except (TypeError, ValueError):
                pass
        ld = str(left.data(Qt.ItemDataRole.DisplayRole) or "").lower()
        rd = str(right.data(Qt.ItemDataRole.DisplayRole) or "").lower()
        return ld < rd

    def process_at(self, proxy_row: int) -> dict | None:
        src_idx = self.mapToSource(self.index(proxy_row, 0))
        if src_idx.isValid():
            return self.sourceModel().process_at_source_row(src_idx.row())
        return None
