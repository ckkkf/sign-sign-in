# -*- coding: utf-8 -*-
import logging
import os
import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QApplication)

from app.gui.windows.modern_window import ModernWindow

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

if __name__ == '__main__':
    if "QT_FONT_DPI" in os.environ: del os.environ["QT_FONT_DPI"]

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    font = QFont("Microsoft YaHei UI", 9)
    font.setStyleStrategy(QFont.PreferAntialias)
    app.setFont(font)

    win = ModernWindow()
    win.show()
    sys.exit(app.exec())
