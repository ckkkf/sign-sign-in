class FeedbackDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("发送反馈")
        self.resize(400, 300)
        self.setStyleSheet("background: #252526; color: white;")
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        self.cb_type = QComboBox()
        self.cb_type.addItems(["功能建议", "Bug 反馈", "其他问题"])
        self.cb_type.setStyleSheet("background: #333; border: 1px solid #555; padding: 5px;")
        layout.addWidget(QLabel("反馈类型:"))
        layout.addWidget(self.cb_type)

        self.le_contact = QLineEdit()
        self.le_contact.setPlaceholderText("Email / QQ")
        self.le_contact.setStyleSheet("background: #333; border: 1px solid #555; padding: 5px;")
        layout.addWidget(QLabel("联系方式:"))
        layout.addWidget(self.le_contact)

        self.txt_content = QTextEdit()
        self.txt_content.setStyleSheet("background: #333; border: 1px solid #555;")
        layout.addWidget(QLabel("内容:"))
        layout.addWidget(self.txt_content)

        self.btn_submit = QPushButton("提交反馈")
        self.btn_submit.setStyleSheet("background: #007ACC; border: none; padding: 8px; font-weight: bold;")
        self.btn_submit.clicked.connect(self.submit)
        layout.addWidget(self.btn_submit)

    def submit(self):
        QMessageBox.information(self, "开发中", "该功能正在开发中！")
        return
        content = self.txt_content.toPlainText()
        if not content: return QMessageBox.warning(self, "提示", "请输入内容")

        self.btn_submit.setEnabled(False)
        self.btn_submit.setText("提交中...")

        self.worker = HttpWorker(API_URL, {"type": "feedback", "category": self.cb_type.currentText(),
            "contact": self.le_contact.text(), "content": content})
        self.worker.result_signal.connect(self.on_finished)
        self.worker.start()

    def on_finished(self, success, msg):
        self.btn_submit.setEnabled(True)
        self.btn_submit.setText("提交反馈")
        if success:
            QMessageBox.information(self, "成功", "反馈已提交！")
            self.close()
        else:
            QMessageBox.warning(self, "失败", msg)
