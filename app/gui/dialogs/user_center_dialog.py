from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QHBoxLayout,
)

from app.gui.components.toast import ToastManager
from app.utils.journal_client import JournalServerError


class UserCenterDialog(QDialog):
    def __init__(self, auth_info: dict, base_url: str, parent=None):
        super().__init__(parent)
        self.auth_info = auth_info
        self.base_url = base_url
        self.logged_out = False
        self.setWindowTitle("用户中心")
        self.resize(400, 250)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self._setup_style()
        self._setup_ui()

    def _setup_style(self):
        self.setStyleSheet("""
            QDialog {
                background: #0F111A;
                color: #E2E6FF;
            }
            QLabel {
                color: #8F95B2;
            }
            QLabel#UserInfo {
                color: #F5F6FF;
                font-size: 12pt;
                font-weight: bold;
                padding: 20px;
            }
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4E8BFF, stop:1 #7A5BFF);
                border: none;
                border-radius: 22px;
                padding: 10px 18px;
                font-weight: bold;
                color: white;
                letter-spacing: 1px;
            }
            QPushButton:hover {
                opacity: 0.92;
            }
            QPushButton#LogoutBtn {
                background: #E74C3C;
            }
            QPushButton#LogoutBtn:hover {
                background: #C0392B;
            }
        """)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        user = self.auth_info.get("user", {})
        username = user.get("username") or user.get("name") or "用户"
        
        user_label = QLabel(f"当前登录用户：{username}")
        user_label.setObjectName("UserInfo")
        layout.addWidget(user_label)

        layout.addStretch()

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        
        btn_logout = QPushButton("登出")
        btn_logout.setObjectName("LogoutBtn")
        btn_logout.clicked.connect(self._handle_logout)
        btn_row.addWidget(btn_logout)

        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(self.close)
        btn_row.addWidget(btn_close)

        layout.addLayout(btn_row)

    def _handle_logout(self):
        self.logged_out = True
        ToastManager.instance().show("已登出", "success")
        self.accept()

