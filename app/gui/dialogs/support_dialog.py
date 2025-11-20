
class SupportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("支持作者")
        self.resize(500, 350)
        self.setStyleSheet("background: #252526; color: white;")

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("如果本项目对您有帮助，请请我喝瓶冰露！", alignment=Qt.AlignCenter))

        qr_box = QHBoxLayout()
        for name, color, url in [("微信支付", "#09BB07", "wxp://f2f01EiRAzk-cwnkJtbu5GMpj0Juf_dTWQr1DiUn5r25wlM"),
                                 ("支付宝", "#00A0E9", "https://qr.alipay.com/fkx10780lnnieguozv3vhaa")]:
            vbox = QVBoxLayout()
            lbl_img = QLabel()
            lbl_img.setAlignment(Qt.AlignCenter)
            img = qrcode.make(url)
            img = img.resize((120, 120))
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            qimg = QImage.fromData(buf.getvalue())
            lbl_img.setPixmap(QPixmap.fromImage(qimg))
            vbox.addWidget(lbl_img)
            l = QLabel(name)
            l.setAlignment(Qt.AlignCenter)
            l.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 11pt; margin-top: 5px;")
            vbox.addWidget(l)
            qr_box.addLayout(vbox)

        layout.addLayout(qr_box)

        ver = QLabel(f"当前版本: {VERSION}")
        ver.setAlignment(Qt.AlignRight)
        ver.setStyleSheet("color: #666; font-size: 9pt;")
        layout.addWidget(ver)