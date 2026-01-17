from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QPushButton, QHBoxLayout, QLabel, )


class CustomConfirmDialog(QDialog):
    """自定义样式的确认对话框"""

    def __init__(self, parent, title, text, confirm_text="确认", is_danger=False):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedWidth(380)
        # 移除问号图标，使用纯净样式
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self._setup_ui(text, confirm_text, is_danger)

    def _setup_ui(self, text, confirm_text, is_danger):
        self.setStyleSheet("""
            QDialog { background-color: #1E1E1E; }
            QLabel { color: #E8EAED; font-size: 14px; line-height: 1.5; }
            QPushButton { 
                padding: 8px 16px; border-radius: 6px; font-size: 13px; font-weight: 500;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setSpacing(24)
        layout.setContentsMargins(24, 24, 24, 24)

        msg_label = QLabel(text)
        msg_label.setWordWrap(True)
        # 稍微增加字间距
        msg_layout = QHBoxLayout()
        msg_layout.addWidget(msg_label)
        layout.addLayout(msg_layout)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        btn_layout.addStretch()

        btn_cancel = QPushButton("取消")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setStyleSheet("""
            background-color: transparent; border: 1px solid #3E3E3E; color: #CCCCCC;
        """)
        btn_cancel.clicked.connect(self.reject)

        btn_confirm = QPushButton(confirm_text)
        btn_confirm.setCursor(Qt.PointingHandCursor)
        if is_danger:
            btn_confirm.setStyleSheet(
                "QPushButton { background-color: #EF4444; color: white; border: none; } QPushButton:hover { background-color: #DC2626; }")
        else:
            btn_confirm.setStyleSheet(
                "QPushButton { background-color: #2563EB; color: white; border: none; } QPushButton:hover { background-color: #1D4ED8; }")

        btn_confirm.clicked.connect(self.accept)
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_confirm)

        layout.addLayout(btn_layout)
