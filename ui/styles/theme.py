"""ui/styles/theme.py"""
from pathlib import Path
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication

ORG_NAME = "Ares"; APP_NAME = "AdministradorTareas"; THEME_KEY = "appearance/theme"
THEME_LIGHT = "light"; THEME_DARK = "dark"

def _res(): return Path(__file__).resolve().parent.parent.parent / "resources"
def qss_path_for_theme(theme):
    return _res() / ("style_dark.qss" if theme == THEME_DARK else "style.qss")
def apply_theme(app, theme):
    if theme not in (THEME_LIGHT, THEME_DARK): theme = THEME_LIGHT
    path = qss_path_for_theme(theme)
    app.setStyleSheet(path.read_text(encoding="utf-8") if path.exists() else "")
def saved_theme():
    raw = QSettings(ORG_NAME, APP_NAME).value(THEME_KEY, THEME_DARK)
    s = raw if isinstance(raw, str) else str(raw)
    return s if s in (THEME_LIGHT, THEME_DARK) else THEME_DARK
def persist_theme(theme):
    if theme not in (THEME_LIGHT, THEME_DARK): theme = THEME_DARK
    QSettings(ORG_NAME, APP_NAME).setValue(THEME_KEY, theme)
