from PySide6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint
)
from PySide6.QtGui import QColor, QPainter, QBrush
from PySide6.QtWidgets import QWidget, QLabel, QHBoxLayout, QApplication


class Toast(QWidget):
    def __init__(self, text, parent=None, duration=2000, bg="#333", color="#fff"):
        super().__init__(parent)

        self.setWindowFlags(
            Qt.ToolTip |
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)

        label = QLabel(text)
        label.setStyleSheet(f"color: {color}; font-size: 10pt;")
        layout.addWidget(label)

        self.bg = QColor(bg)
        self.duration = duration

        # 淡入透明度
        self.fade_in_anim = QPropertyAnimation(self, b"windowOpacity")
        self.fade_in_anim.setDuration(250)
        self.fade_in_anim.setStartValue(0)
        self.fade_in_anim.setEndValue(1)
        self.fade_in_anim.setEasingCurve(QEasingCurve.OutCubic)

        # 淡出透明度
        self.fade_out_anim = QPropertyAnimation(self, b"windowOpacity")
        self.fade_out_anim.setDuration(300)
        self.fade_out_anim.setStartValue(1)
        self.fade_out_anim.setEndValue(0)
        self.fade_out_anim.setEasingCurve(QEasingCurve.InCubic)
        self.fade_out_anim.finished.connect(self.close)

        # 下滑进入动画
        self.pos_anim = QPropertyAnimation(self, b"pos")
        self.pos_anim.setDuration(250)
        self.pos_anim.setEasingCurve(QEasingCurve.OutCubic)

        # 上滑退出动画
        self.exit_anim = QPropertyAnimation(self, b"pos")
        self.exit_anim.setDuration(250)
        self.exit_anim.setEasingCurve(QEasingCurve.InCubic)

        # 停留计时器
        self.timer = QTimer(self)
        self.timer.setInterval(duration)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.start_exit_anim)

    def start_exit_anim(self):
        current_pos = self.pos()
        end_pos = QPoint(current_pos.x(), current_pos.y() - 20)

        self.exit_anim.setStartValue(current_pos)
        self.exit_anim.setEndValue(end_pos)

        self.fade_out_anim.start()
        self.exit_anim.start()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QBrush(self.bg))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(self.rect(), 8, 8)

    def showEvent(self, e):
        super().showEvent(e)

        if self.parent():
            parent_pos = self.parent().mapToGlobal(self.parent().rect().topLeft())
            parent_size = self.parent().size()

            final_x = parent_pos.x() + parent_size.width() - self.width() - 20
            final_y = parent_pos.y() + 20

            start_y = final_y - 20  # 初始位置在 20 像素上方

            self.move(final_x, start_y)

            self.pos_anim.setStartValue(QPoint(final_x, start_y))
            self.pos_anim.setEndValue(QPoint(final_x, final_y))

            self.fade_in_anim.start()
            self.pos_anim.start()
            self.timer.start()




class ToastManager:
    _instance = None

    @staticmethod
    def instance():
        if ToastManager._instance is None:
            ToastManager._instance = ToastManager()
        return ToastManager._instance

    def show(self, text, type="info"):
        parent = QApplication.activeWindow()

        colors = {
            "info": ("#E8F4FD", "#2C7BE5", "ℹ️"),  # 浅蓝背景 + 深蓝文字
            "success": ("#f2f9ec", "#7ec050", "✅"),  # 浅绿背景 + 深绿文字
            "warning": ("#fcf6ed", "#dca550", "⚠️"),  # 浅橙背景 + 深橙文字
            "error": ("#fcf0f0", "#e47470", "❌"),  # 浅红背景 + 深红文字
        }

        bg, color, icon = colors[type]
        t = Toast(f"{icon}  {text}", parent, bg=bg, color=color)
        t.adjustSize()
        t.show()

