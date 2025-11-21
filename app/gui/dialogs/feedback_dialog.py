from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QComboBox,
    QLabel,
    QLineEdit,
    QTextEdit,
    QPushButton,
    QHBoxLayout,
)

from app.config.common import API_URL
from app.gui.components.toast import ToastManager
from app.workers.http_worker import HttpWorker


class FeedbackDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("发送反馈")
        self.resize(420, 360)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.worker = None
        self._setup_style()
        self._setup_ui()

    def _setup_style(self):
        self.setStyleSheet("""
            QDialog {
                background: #10121B;
                color: #E8EBFF;
            }
            QLabel {
                color: #8F95B2;
                font-weight: 600;
            }
            QComboBox, QLineEdit, QTextEdit {
                background: #181B2A;
                border: 1px solid #2D3250;
                border-radius: 10px;
                padding: 8px 12px;
                color: #F5F6FF;
            }
            QComboBox:focus, QLineEdit:focus, QTextEdit:focus {
                border-color: #6E7BFF;
                box-shadow: 0 0 12px rgba(110,123,255,0.25);
            }
            QTextEdit {
                min-height: 140px;
            }
            QPushButton#SubmitBtn {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4E8BFF, stop:1 #A24DFF);
                color: white;
                border: none;
                border-radius: 22px;
                padding: 10px 18px;
                font-weight: bold;
                letter-spacing: 1px;
            }
            QPushButton#SubmitBtn:disabled {
                background: #2E3350;
                color: #888CAA;
            }
        """)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        subtitle = QLabel("感谢你的反馈，我们会尽快处理并与你联系。")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        self.cb_type = QComboBox()
        self.cb_type.addItems(["功能建议", "Bug 反馈", "使用咨询", "其他问题"])
        layout.addWidget(QLabel("反馈类型"))
        layout.addWidget(self.cb_type)

        contact_row = QHBoxLayout()
        self.le_contact = QLineEdit()
        self.le_contact.setPlaceholderText("Email / QQ / 微信（可选）")
        contact_row.addWidget(self.le_contact)
        layout.addWidget(QLabel("联系方式"))
        layout.addLayout(contact_row)

        self.txt_content = QTextEdit()
        self.txt_content.setPlaceholderText("请尽量描述清楚问题、重现步骤或你期待的功能...")
        layout.addWidget(QLabel("反馈内容"))
        layout.addWidget(self.txt_content)

        self.btn_submit = QPushButton("提交反馈")
        self.btn_submit.setObjectName("SubmitBtn")
        self.btn_submit.clicked.connect(self.submit)
        layout.addWidget(self.btn_submit)

    def submit(self):
        content = self.txt_content.toPlainText().strip()
        if not content:
            ToastManager.instance().show("请先填写反馈内容", "warning")
            return

        payload = {
            "type": "feedback",
            "category": self.cb_type.currentText(),
            "contact": self.le_contact.text().strip(),
            "content": content,
        }

        self.btn_submit.setEnabled(False)
        self.btn_submit.setText("提交中...")
        self.worker = HttpWorker(API_URL, payload)
        self.worker.result_signal.connect(self.on_finished)
        self.worker.start()

    def on_finished(self, success, msg):
        self.btn_submit.setEnabled(True)
        self.btn_submit.setText("提交反馈")
        if success:
            ToastManager.instance().show("反馈提交成功，感谢支持！", "success")
            self.close()
        else:
            ToastManager.instance().show(f"提交失败：{msg}", "error")
