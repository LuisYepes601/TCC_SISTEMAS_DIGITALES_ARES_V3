"""
Administrador de Tareas Ares v3.0 — Punto de entrada.
"""
import sys
from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow
from ui.styles.theme import apply_theme, saved_theme

def _check_platform() -> None:
    if sys.platform not in ("win32", "darwin"):
        print("Advertencia: Ares está optimizado para Windows y macOS.", file=sys.stderr)

if __name__ == "__main__":
    _check_platform()
    app = QApplication(sys.argv)
    app.setApplicationName("Administrador de Tareas Ares")
    app.setApplicationVersion("3.0.0")
    app.setOrganizationName("Ares")
    apply_theme(app, saved_theme())
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
