from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtWidgets import (QPushButton, QHBoxLayout, QFrame, )


class FloatingActionBar(QFrame):
    def __init__(self, parent=None, callback_copy=None, callback_submit=None):
        super().__init__(parent)
        self.callback_copy = callback_copy
        self.callback_submit = callback_submit
        self.current_text = ""
        self.hide_timer = QTimer(self)
        self.hide_timer.setInterval(100)
        self.hide_timer.timeout.connect(self.hide)
        self.hide()  # 确保初始隐藏
        self._init_ui()

    def _init_ui(self):
        self.setObjectName("FloatingActionBar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)
        self.setStyleSheet("""
            QFrame#FloatingActionBar {
                background-color: rgba(40, 44, 52, 0.95);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
            }
        """)

        self.btn_copy = QPushButton("复制")
        self._style_btn(self.btn_copy)
        self.btn_copy.clicked.connect(lambda: self.callback_copy(self.current_text))
        layout.addWidget(self.btn_copy)

        # 分割线
        self.divider = QFrame()
        self.divider.setFixedSize(1, 14)
        self.divider.setStyleSheet("background-color: rgba(255, 255, 255, 0.2);")
        layout.addWidget(self.divider)

        self.btn_submit = QPushButton("📝 提交为周记")
        self._style_btn(self.btn_submit)
        self.btn_submit.clicked.connect(lambda: self.callback_submit(self.current_text))
        layout.addWidget(self.btn_submit)

    def _style_btn(self, btn):
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedHeight(24)
        btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #BDC1C6;
                border: none;
                padding: 0 8px;
                font-size: 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
                color: #FFFFFF;
            }
        """)

    def show_for(self, target_widget, text, show_submit=False):
        self.hide_timer.stop()
        self.current_text = text
        self.btn_submit.setVisible(show_submit)
        self.divider.setVisible(show_submit)
        self.adjustSize()

        # Calculate position: Bottom Left of target widget, mapped to parent dialog
        target_pos = target_widget.mapTo(self.parent(), QPoint(0, 0))
        x = target_pos.x()
        y = target_pos.y() + target_widget.height() + 4

        self.move(x, y)
        self.show()
        self.raise_()

    def enterEvent(self, event):
        self.hide_timer.stop()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hide_timer.start()
        super().leaveEvent(event)

    def schedule_hide(self):
        self.hide_timer.start()
