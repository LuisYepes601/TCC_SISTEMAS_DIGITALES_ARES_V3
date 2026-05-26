"""ui/widgets/process_icon.py"""
import sys
from pathlib import Path
from PyQt6.QtCore import QFileInfo
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QFileIconProvider
_provider = QFileIconProvider()
def icon_for_exe(exe_path):
    if not exe_path: return _provider.icon(QFileIconProvider.IconType.File)
    path = exe_path.strip()
    if sys.platform == "darwin" and ".app/Contents/MacOS/" in path:
        path = path[:path.find(".app/Contents/MacOS/") + 4]
    info = QFileInfo(path)
    if not info.exists() and sys.platform == "darwin":
        p = Path(exe_path)
        if p.exists(): info = QFileInfo(str(p.resolve()))
    return _provider.icon(info)
