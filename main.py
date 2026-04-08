# -*- coding: utf-8 -*-
import logging
import os
import sys

from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (QApplication, QMessageBox)
from app.gui.windows.modern_window import ModernWindow
from app.mitm.embedded_runner import main as mitm_runner_main
import traceback

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

def exception_hook(exctype, value, tb):
    """全局异常捕获钩子"""
    error_msg = "".join(traceback.format_exception(exctype, value, tb))
    logging.critical(f"Uncaught exception:\n{error_msg}")
    
    # 在GUI线程中弹出错误框（尽量）
    # 注意：如果app尚未初始化或已崩溃，这可能无效，但对于逻辑错误非常有用
    msg_box = QMessageBox()
    msg_box.setIcon(QMessageBox.Critical)
    msg_box.setText("程序发生未捕获的异常")
    msg_box.setInformativeText(str(value))
    msg_box.setDetailedText(error_msg)
    msg_box.setWindowTitle("Error")
    msg_box.exec()
    
    # 调用默认的钩子（通常会打印到 stderr）
    sys.__excepthook__(exctype, value, tb)

sys.excepthook = exception_hook

if __name__ == '__main__':
    if '--mitm-runner' in sys.argv:
        runner_index = sys.argv.index('--mitm-runner')
        raise SystemExit(mitm_runner_main(sys.argv[runner_index + 1:]))

    if "QT_FONT_DPI" in os.environ: del os.environ["QT_FONT_DPI"]

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setStyle("Fusion")
    font = QFont("Microsoft YaHei UI", 9)
    font.setStyleStrategy(QFont.PreferAntialias)
    app.setFont(font)

    icon_path = os.path.join(os.path.dirname(__file__), "app", "assets", "app_icon.svg")
    app_icon = QIcon(icon_path)
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)

    win = ModernWindow()
    if not app_icon.isNull():
        win.setWindowIcon(app_icon)
    win.show()
    sys.exit(app.exec())
