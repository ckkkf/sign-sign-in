from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QColor


class LoadingSpinner(QWidget):
    def __init__(self, size=16, line_width=2, color="#58D68D", parent=None):
        super().__init__(parent)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.rotate)
        self._timer.start(60)  # 16 FPS

        self.size = size
        self.line_width = line_width
        self.color = QColor(color)
        self.setFixedSize(size, size)

    def rotate(self):
        self._angle = (self._angle + 30) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.translate(self.width() / 2, self.height() / 2)
        painter.rotate(self._angle)

        pen = painter.pen()
        pen.setWidth(self.line_width)
        pen.setColor(self.color)
        painter.setPen(pen)

        radius = (self.size - self.line_width) / 2
        painter.drawArc(
            -radius,
            -radius,
            radius * 2,
            radius * 2,
            0 * 16,
            100 * 16,  # 弧度
        )
