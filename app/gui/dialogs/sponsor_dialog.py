import io

import qrcode
from PySide6.QtGui import QImage, QPixmap, Qt
from PySide6.QtWidgets import QMessageBox, QDialog, QVBoxLayout, QLabel, QHBoxLayout, QFrame, QFormLayout, QLineEdit, \
    QDoubleSpinBox, QPushButton, QSizePolicy


class SponsorSubmitDialog(QDialog):
    """赞助榜提交对话框 (含二维码)"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("加入赞助榜")
        self.resize(500, 450)
        self.setStyleSheet("background: #252526; color: white;")
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        lbl_desc = QLabel(
            "开发不易，若能您对您有帮助，是我们的荣幸，若您手头有余，在自己有可乐喝的前提下，可以考虑请我喝瓶冰露，可以留一下您的昵称，以便添加到赞助感谢榜。")
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet("color: #70a1ff; margin-bottom: 5px;")
        layout.addWidget(lbl_desc)

        import segno
        import io

        qr_box = QHBoxLayout()
        for name, color, url in [
            ("微信", "#09BB07", "wxp://f2f01EiRAzk-cwnkJtbu5GMpj0Juf_dTWQr1DiUn5r25wlM"),
            ("支付宝", "#00A0E9", "https://qr.alipay.com/fkx10780lnnieguozv3vhaa")
        ]:
            vbox = QVBoxLayout()
            lbl_img = QLabel()
            lbl_img.setAlignment(Qt.AlignCenter)

            # 生成二维码（不依赖 qrcode 库）
            qr = segno.make(url)
            buf = io.BytesIO()
            qr.save(buf, kind='png', scale=6)

            qimg = QImage.fromData(buf.getvalue())
            lbl_img.setPixmap(QPixmap.fromImage(qimg))

            vbox.addWidget(lbl_img)

            l = QLabel(name)
            l.setAlignment(Qt.AlignCenter)
            l.setStyleSheet(f"color: {color}; font-weight: bold;")
            vbox.addWidget(l)

            qr_box.addLayout(vbox)

        layout.addLayout(qr_box)

        # 表单区域
        form = QFrame()
        fl = QFormLayout(form)
        self.le_name = QLineEdit()
        self.le_name.setStyleSheet("background: #333; border: 1px solid #555; padding: 6px;")
        fl.addRow("昵称:", self.le_name)

        self.sb_amount = QDoubleSpinBox()
        self.sb_amount.setRange(0.00, 10000)
        self.sb_amount.setPrefix("￥")
        self.sb_amount.setValue(0.00)
        self.sb_amount.setStyleSheet("background: #333; border: 1px solid #555; padding: 6px;")
        fl.addRow("金额:", self.sb_amount)
        layout.addWidget(form)

        # 按钮区域（占满一行）
        btn_row = QHBoxLayout()
        btn_row.setSpacing(15)  # 两个按钮之间的间距

        # 提交按钮
        self.btn_submit = QPushButton("提交")
        self.btn_submit.setStyleSheet("""
            QPushButton {
                background: #E64A19;
                color: white;
                border: none;
                padding: 8px 0;
                font-weight: bold;
                border-radius: 6px;
                font-size: 15px;
            }
        """)
        self.btn_submit.clicked.connect(self.submit)
        self.btn_submit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)  # ⭐ 自动拉伸
        btn_row.addWidget(self.btn_submit)

        # 关闭按钮
        self.btn_close = QPushButton("关闭")
        self.btn_close.setStyleSheet("""
            QPushButton {
                background: #9E9E9E;
                color: white;
                border: none;
                padding: 8px 0;
                font-weight: bold;
                border-radius: 6px;
                font-size: 15px;
            }
        """)
        self.btn_close.clicked.connect(self.close)
        self.btn_close.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)  # ⭐ 自动拉伸
        btn_row.addWidget(self.btn_close)

        layout.addLayout(btn_row)

    def submit(self):
        QMessageBox.information(self, "开发中", "该功能正在开发中！")
        return

        if not self.le_name.text(): return QMessageBox.warning(self, "提示", "请输入昵称")

        self.btn_submit.setEnabled(False)
        self.btn_submit.setText("正在请求服务器...")

        self.worker = HttpWorker(API_URL,
                                 {"type": "sponsor", "name": self.le_name.text(), "amount": self.sb_amount.value()})
        self.worker.result_signal.connect(self.on_finished)
        self.worker.start()

    def on_finished(self, success, msg):
        self.btn_submit.setEnabled(True)
        self.btn_submit.setText("提交并上榜")
        if success:
            QMessageBox.information(self, "成功", f"提交成功！\n{msg}")
            self.close()
        else:
            QMessageBox.warning(self, "失败", f"请求失败: {msg}")


if __name__ == '__main__':
    from PySide6.QtWidgets import QApplication

    app = QApplication()
    dlg = SponsorSubmitDialog()
    dlg.show()
    app.exec()
