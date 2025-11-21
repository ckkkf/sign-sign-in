from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QTabWidget,
    QWidget,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QLabel,
)

from app.gui.components.toast import ToastManager
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
        intro = QLabel("登录后即可同步周记草稿与提交记录，注册仅需设置用户名与密码。")
        intro.setWordWrap(True)
        intro.setObjectName("IntroLabel")
        layout.addWidget(intro)
        layout.addWidget(self.tabs)

        self.login_widget = self._build_login_tab()
        self.register_widget = self._build_register_tab()

        self.tabs.addTab(self.login_widget, "登录")
        self.tabs.addTab(self.register_widget, "注册")

    def _setup_style(self):
        self.setStyleSheet("""
            QDialog {
                background: #0F111A;
                color: #E2E6FF;
            }
            #IntroLabel {
                color: #8F95B2;
                padding: 6px 4px 10px;
            }
            QTabWidget::pane {
                border: 1px solid #1F2336;
                border-radius: 12px;
                padding: 8px;
                background: #151927;
            }
            QTabBar::tab {
                background: transparent;
                padding: 6px 16px;
                margin-right: 6px;
                border-radius: 12px;
                color: #848AAE;
                font-weight: 600;
            }
            QTabBar::tab:selected {
                background: #262B44;
                color: #F5F6FF;
            }
            QLineEdit {
                background: #1A1E2F;
                border: 1px solid #2F3550;
                border-radius: 10px;
                padding: 10px 12px;
                color: #F7F9FF;
            }
            QLineEdit:focus {
                border-color: #6E7BFF;
                box-shadow: 0 0 10px rgba(110,123,255,0.25);
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
        """)

    def _build_login_tab(self):
        widget = QWidget()
        form = QFormLayout(widget)
        form.setSpacing(14)
        self.login_user = QLineEdit()
        self.login_user.setPlaceholderText("请输入账号")
        self.login_pass = QLineEdit()
        self.login_pass.setEchoMode(QLineEdit.Password)
        self.login_pass.setPlaceholderText("请输入密码")
        btn_login = QPushButton("立即登录")
        btn_login.clicked.connect(self._handle_login)
        form.addRow("用户名", self.login_user)
        form.addRow("密码", self.login_pass)
        form.addRow(btn_login)
        return widget

    def _build_register_tab(self):
        widget = QWidget()
        form = QFormLayout(widget)
        form.setSpacing(12)
        self.reg_user = QLineEdit()
        self.reg_user.setPlaceholderText("设置用户名")
        self.reg_pass = QLineEdit()
        self.reg_pass.setEchoMode(QLineEdit.Password)
        self.reg_pass.setPlaceholderText("设置登录密码")
        self.reg_pass_confirm = QLineEdit()
        self.reg_pass_confirm.setEchoMode(QLineEdit.Password)
        self.reg_pass_confirm.setPlaceholderText("再次输入密码")
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
            ToastManager.instance().show(str(exc), "warning")
            return
        except Exception as exc:
            ToastManager.instance().show(str(exc), "error")
            return
        self.auth_result = result
        ToastManager.instance().show("登录成功", "success")
        self.accept()

    def _handle_register(self):
        username = self.reg_user.text().strip()
        password = self.reg_pass.text().strip()
        confirm = self.reg_pass_confirm.text().strip()
        if password != confirm:
            ToastManager.instance().show("两次输入的密码不一致", "warning")
            return
        try:
            register(self.base_url, username, password)
            ToastManager.instance().show("注册成功，请使用该账号登录", "success")
            self.tabs.setCurrentIndex(0)
            self.login_user.setText(username)
            self.login_pass.setText("")
        except JournalServerError as exc:
            ToastManager.instance().show(str(exc), "warning")
        except Exception as exc:
            ToastManager.instance().show(str(exc), "error")

