from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QComboBox


class NoWheelComboBox(QComboBox):
    """Ignore mouse-wheel changes to prevent accidental selection edits while scrolling."""

    def wheelEvent(self, event: QWheelEvent):
        event.ignore()
