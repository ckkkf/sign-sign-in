from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QTabWidget,
    QWidget,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QMessageBox,
)

from app.utils.journal_client import login, register, JournalServerError


class JournalAuthDialog(QDialog):
    def __init__(self, base_url: str, parent=None):
        super().__init__(parent)
        self.base_url = base_url
        self.setWindowTitle("周记账号")
        self.resize(360, 260)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.auth_result = None
        self._setup_style()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self.login_widget = self._build_login_tab()
        self.register_widget = self._build_register_tab()

        self.tabs.addTab(self.login_widget, "登录")
        self.tabs.addTab(self.register_widget, "注册")

    def _setup_style(self):
        self.setStyleSheet("""
            QDialog {
                background: #121214;
                color: #DDD;
            }
            QLineEdit {
                background: #1D1D21;
                border: 1px solid #2F2F33;
                border-radius: 6px;
                padding: 6px 10px;
                color: #FFF;
            }
            QLineEdit:focus {
                border-color: #5865F2;
            }
            QPushButton {
                background: #3C3C4A;
                border: none;
                border-radius: 18px;
                padding: 8px 16px;
                font-weight: bold;
                color: white;
            }
            QPushButton:hover {
                background: #4F4F60;
            }
        """)

    def _build_login_tab(self):
        widget = QWidget()
        form = QFormLayout(widget)
        self.login_user = QLineEdit()
        self.login_pass = QLineEdit()
        self.login_pass.setEchoMode(QLineEdit.Password)
        btn_login = QPushButton("立即登录")
        btn_login.clicked.connect(self._handle_login)
        form.addRow("用户名", self.login_user)
        form.addRow("密码", self.login_pass)
        form.addRow(btn_login)
        return widget

    def _build_register_tab(self):
        widget = QWidget()
        form = QFormLayout(widget)
        self.reg_user = QLineEdit()
        self.reg_pass = QLineEdit()
        self.reg_pass.setEchoMode(QLineEdit.Password)
        self.reg_pass_confirm = QLineEdit()
        self.reg_pass_confirm.setEchoMode(QLineEdit.Password)
        btn_register = QPushButton("提交注册")
        btn_register.clicked.connect(self._handle_register)
        form.addRow("用户名", self.reg_user)
        form.addRow("密码", self.reg_pass)
        form.addRow("确认密码", self.reg_pass_confirm)
        form.addRow(btn_register)
        return widget

    def _handle_login(self):
        try:
            result = login(self.base_url, self.login_user.text().strip(), self.login_pass.text().strip())
        except JournalServerError as exc:
            QMessageBox.warning(self, "登录失败", str(exc))
            return
        except Exception as exc:
            QMessageBox.critical(self, "登录失败", str(exc))
            return
        self.auth_result = result
        self.accept()

    def _handle_register(self):
        username = self.reg_user.text().strip()
        password = self.reg_pass.text().strip()
        confirm = self.reg_pass_confirm.text().strip()
        if password != confirm:
            QMessageBox.warning(self, "提示", "两次输入的密码不一致")
            return
        try:
            register(self.base_url, username, password)
            QMessageBox.information(self, "注册成功", "账号注册成功，请切换到登录标签登录。")
            self.tabs.setCurrentIndex(0)
            self.login_user.setText(username)
            self.login_pass.setText("")
        except JournalServerError as exc:
            QMessageBox.warning(self, "注册失败", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "注册失败", str(exc))

