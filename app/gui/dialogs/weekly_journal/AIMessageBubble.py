from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QTextEdit, QHBoxLayout, QLabel, QFrame, )


class AIMessageBubble(QFrame):
    def __init__(self, parent_dialog, initial_text=""):
        super().__init__()
        self.parent_dialog = parent_dialog
        self.text = initial_text
        self.setObjectName("AIMessage")
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignTop)  # 顶部对齐

        ai_icon = QLabel("✨")
        ai_icon.setObjectName("AIIcon")
        ai_icon.setAlignment(Qt.AlignTop)
        ai_icon.setContentsMargins(0, 4, 0, 0)  # 微调图标位置
        layout.addWidget(ai_icon)

        # 使用 TextEdit 代替 Label 以支持 Markdown 和 完美自动换行
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setFrameShape(QFrame.NoFrame)
        self.text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.text_edit.setObjectName("AIMessageText")
        self.text_edit.document().setDocumentMargin(0)  # 去除默认边距

        self.text_edit.setMarkdown(self.text)
        self.text_edit.setMaximumWidth(550)
        self.text_edit.setMinimumWidth(50)

        # 样式 - 确保背景透明，使用 label 样式
        self.text_edit.setStyleSheet("""
            QTextEdit {
                background-color: #2A2D3E;
                color: #E8EAED;
                font-size: 14px;
                line-height: 1.5;
                padding: 10px 14px; /* 垂直10，水平14 */
                border: 1px solid #363B4C;
                border-radius: 16px;
                border-bottom-left-radius: 2px;
            }
        """)

        layout.addWidget(self.text_edit)
        self._adjust_height()

    def setText(self, text):
        self.text = text
        self.text_edit.setMarkdown(text)
        self._adjust_height()

    def _adjust_height(self):
        # 自动调整高度
        current_width = self.text_edit.width()
        if current_width <= 0: current_width = 550  # 默认宽度

        # 减去 Horizontal Padding (14px * 2 = 28) 和 边框 余量
        # 保持一点额外空间防止换行抖动
        text_width = current_width - 30
        if text_width < 10: text_width = 10

        doc = self.text_edit.document()
        doc.setTextWidth(text_width)
        h = doc.size().height()
        self.text_edit.setFixedHeight(int(h + 20))  # Vertical Padding (10*2=20)

    def resizeEvent(self, event):
        self._adjust_height()
        super().resizeEvent(event)

    def enterEvent(self, event):
        if hasattr(self.parent_dialog, 'floating_bar'):
            self.parent_dialog.floating_bar.show_for(self.text_edit, self.text, show_submit=True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if hasattr(self.parent_dialog, 'floating_bar'):
            self.parent_dialog.floating_bar.schedule_hide()
        super().leaveEvent(event)

    def wheelEvent(self, event):
        # 禁用气泡内的滚轮滚动，并将事件忽略以便传递给父级（ScrollArea）
        event.ignore()
