from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QTextEdit, QHBoxLayout, QFrame, )


class UserMessageBubble(QFrame):
    def __init__(self, parent_dialog, text):
        super().__init__()
        self.parent_dialog = parent_dialog
        self.text = text
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch()
        layout.setAlignment(Qt.AlignTop)

        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setFrameShape(QFrame.NoFrame)
        self.text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.text_edit.setObjectName("UserMessageText")
        self.text_edit.document().setDocumentMargin(0)  # 去除默认边距
        self.text_edit.setPlainText(self.text)
        self.text_edit.setMaximumWidth(550)
        self.text_edit.setMinimumWidth(20)

        self.text_edit.setStyleSheet("""
            QTextEdit {
                background-color: #2563EB;
                color: #FFFFFF;
                font-size: 14px;
                padding: 10px 14px; /* 垂直10，水平14 */
                border-radius: 16px;
                border-bottom-right-radius: 2px;
                border: none;
            }
        """)

        layout.addWidget(self.text_edit)
        self._adjust_height()

    def _adjust_height(self):
        doc = self.text_edit.document()

        # 1. 计算理想宽度
        doc.setTextWidth(-1)  # 不换行
        ideal_width = doc.idealWidth()

        # 2. 确定气泡宽度 (Horizontal Padding 28 + 额外 2)
        bubble_width = ideal_width + 30
        bubble_width = max(40, min(bubble_width, 550))  # 最小宽度减小到40

        self.text_edit.setFixedWidth(int(bubble_width))

        # 3. 根据实际宽度计算高度 (减去 Horizontal Padding)
        doc.setTextWidth(bubble_width - 28)
        h = doc.size().height()
        self.text_edit.setFixedHeight(int(h + 20))  # Vertical Padding 20

    def resizeEvent(self, event):
        self._adjust_height()
        super().resizeEvent(event)

    def enterEvent(self, event):
        if hasattr(self.parent_dialog, 'floating_bar'):
            self.parent_dialog.floating_bar.show_for(self.text_edit, self.text, show_submit=False)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if hasattr(self.parent_dialog, 'floating_bar'):
            self.parent_dialog.floating_bar.schedule_hide()
        super().leaveEvent(event)

    def wheelEvent(self, event):
        event.ignore()

    def wheelEvent(self, event):
        event.ignore()
