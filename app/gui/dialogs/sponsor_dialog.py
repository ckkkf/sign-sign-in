import io

import qrcode
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QHBoxLayout,
    QFrame,
    QFormLayout,
    QLineEdit,
    QDoubleSpinBox,
    QPushButton,
    QTextEdit,
)

from app.config.common import API_URL, VERSION, CONFIG_FILE
from app.gui.components.toast import ToastManager
from app.workers.http_worker import HttpWorker
from app.utils.files import save_json_file, read_config


class SponsorSubmitDialog(QDialog):
    """赞助榜提交对话框 (含二维码)"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("加入赞助榜")
        self.resize(560, 480)  # 减少高度
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.worker = None
        self._setup_style()
        self._setup_ui()

    def _setup_style(self):
        self.setStyleSheet("""
            QDialog {
                background: #0F111C;
                color: #E8EBFF;
            }
            QLabel {
                color: #9BA3C6;
            }
            #DescLabel {
                color: #BAC3FF;
                font-size: 10.5pt;
                line-height: 1.6;
            }
            QFrame#Card {
                background: #16192A;
                border: 1px solid #2A2F45;
                border-radius: 14px;
                padding: 5px;
            }
            QLineEdit, QTextEdit, QDoubleSpinBox {
                background: #1E2238;
                border: 1px solid #2F3654;
                border-radius: 10px;
                padding: 10px 12px;
                color: #F5F6FF;
            }
            QLineEdit:focus, QTextEdit:focus, QDoubleSpinBox:focus {
                border-color: #7C89FF;
                box-shadow: 0 0 12px rgba(124,137,255,0.25);
            }
            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
                background: #3A4062;
                border: 1px solid #4A5072;
                border-radius: 4px;
                width: 20px;
                min-width: 20px;
            }
            QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {
                background: #4E5678;
                border-color: #7C89FF;
            }
            QDoubleSpinBox::up-button:pressed, QDoubleSpinBox::down-button:pressed {
                background: #5A6288;
            }
            QDoubleSpinBox::up-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-bottom: 6px solid #F5F6FF;
                width: 0;
                height: 0;
            }
            QDoubleSpinBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 6px solid #F5F6FF;
                width: 0;
                height: 0;
            }
            QDoubleSpinBox::up-button:hover QDoubleSpinBox::up-arrow {
                border-bottom-color: #FFFFFF;
            }
            QDoubleSpinBox::down-button:hover QDoubleSpinBox::down-arrow {
                border-top-color: #FFFFFF;
            }
            QTextEdit {
                min-height: 90px;
            }
            QPushButton#PrimaryBtn {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #FF8A5C, stop:1 #F24FB3);
                color: white;
                border: none;
                border-radius: 22px;
                padding: 10px 20px;
                font-weight: bold;
                letter-spacing: 1px;
            }
            QPushButton#OutlinedBtn {
                background: transparent;
                border: 1px solid #3A4062;
                color: #9BA3C6;
                border-radius: 22px;
                padding: 10px 16px;
                font-weight: bold;
            }
            QPushButton#PrimaryBtn:disabled {
                background: #353B5A;
                color: #7B80A3;
            }
        """)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        desc = QLabel("开发不易，若能对您有帮助，是我的荣幸。若您手头有余，在自己有可乐喝的前提下，可以考虑请我喝瓶冰露。可以留一下您的昵称，以便添加到赞助感谢榜~")
        desc.setObjectName("DescLabel")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        qr_card = QFrame()
        qr_card.setObjectName("Card")
        # qr_card.setMaximumHeight(180)  # 限制二维码卡片高度
        qr_layout = QHBoxLayout(qr_card)
        qr_layout.setSpacing(20)


        for name, color, url in [
            ("微信", "#61DB57", "wxp://f2f01EiRAzk-cwnkJtbu5GMpj0Juf_dTWQr1DiUn5r25wlM"),
            ("支付宝", "#3AA0FF", "https://qr.alipay.com/fkx10780lnnieguozv3vhaa"),
        ]:
            column = QVBoxLayout()
            column.setSpacing(5)
            lbl_img = QLabel(alignment=Qt.AlignCenter)
            qr = qrcode.make(url,box_size=5)
            buffer = io.BytesIO()
            qr.save(buffer, kind="png", scale=1)
            qimg = QImage.fromData(buffer.getvalue())
            lbl_img.setPixmap(QPixmap.fromImage(qimg))
            column.addWidget(lbl_img)

            caption = QLabel(name, alignment=Qt.AlignCenter)
            caption.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 11pt;")
            column.addWidget(caption)
            qr_layout.addLayout(column)

        layout.addWidget(qr_card)

        form_card = QFrame()
        form_card.setObjectName("Card")
        form_layout = QFormLayout(form_card)
        form_layout.setSpacing(14)

        self.le_name = QLineEdit()
        self.le_name.setPlaceholderText("显示在赞助墙的昵称")
        form_layout.addRow("赞助昵称", self.le_name)

        self.le_contact = QLineEdit()
        self.le_contact.setPlaceholderText("可选：QQ / 微信 / 邮箱")
        form_layout.addRow("联系方式", self.le_contact)

        self.sb_amount = QDoubleSpinBox()
        self.sb_amount.setRange(1.00, 10000.00)
        self.sb_amount.setPrefix("￥")
        self.sb_amount.setDecimals(2)
        self.sb_amount.setValue(1.00)  # 默认设置为1元
        form_layout.addRow("赞助金额", self.sb_amount)

        self.txt_message = QTextEdit()
        self.txt_message.setPlaceholderText("想对作者说的话、署名或展示链接，可选")
        form_layout.addRow("留言", self.txt_message)

        # layout.addWidget(form_card)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        # self.btn_submit = QPushButton("提交赞助信息")
        # self.btn_submit.setObjectName("PrimaryBtn")
        # self.btn_submit.clicked.connect(self.submit)
        # btn_row.addWidget(self.btn_submit)

        # 不再显示按钮
        btn_dont_show = QPushButton("不再显示")
        btn_dont_show.setObjectName("OutlinedBtn")
        btn_dont_show.setStyleSheet("""
            QPushButton#OutlinedBtn {
                background: transparent;
                border: 1px solid #3A4062;
                color: #9BA3C6;
                border-radius: 22px;
                padding: 10px 16px;
                font-weight: bold;
                font-size: 9pt;
            }
            QPushButton#OutlinedBtn:hover {
                border-color: #7C89FF;
                color: #F5F6FF;
            }
        """)
        btn_dont_show.clicked.connect(self.dont_show_again)
        btn_row.addWidget(btn_dont_show)

        btn_close = QPushButton("关闭")
        btn_close.setObjectName("OutlinedBtn")
        btn_close.clicked.connect(self.close)
        btn_row.addWidget(btn_close)

        layout.addLayout(btn_row)

        version = QLabel(f"当前版本：{VERSION}", alignment=Qt.AlignRight)
        version.setStyleSheet("color:#5C6287; font-size:9pt;")
        layout.addWidget(version)

    def submit(self):
        ToastManager.instance().show("该功能开发中", "error")
        return
        name = self.le_name.text().strip()
        amount = float(self.sb_amount.value())
        if not name:
            ToastManager.instance().show("请填写赞助昵称", "warning")
            return
        if amount <= 0:
            ToastManager.instance().show("赞助金额需大于 0", "warning")
            return

        payload = {
            "type": "sponsor",
            "name": name,
            "contact": self.le_contact.text().strip(),
            "amount": amount,
            "message": self.txt_message.toPlainText().strip(),
        }

        self.btn_submit.setEnabled(False)
        self.btn_submit.setText("提交中...")
        self.worker = HttpWorker(API_URL, payload)
        self.worker.result_signal.connect(self.on_finished)
        self.worker.start()

    def on_finished(self, success: bool, msg: str):
        self.btn_submit.setEnabled(True)
        self.btn_submit.setText("提交赞助信息")
        if success:
            ToastManager.instance().show("信息提交成功，感谢支持！", "success")
            self.close()
        else:
            ToastManager.instance().show(f"提交失败：{msg}", "error")

    def dont_show_again(self):
        """保存不再显示设置"""
        try:
            config = read_config(CONFIG_FILE)
            if "settings" not in config:
                config["settings"] = {}
            config["settings"]["dont_show_sponsor"] = True
            save_json_file(CONFIG_FILE, config)
            ToastManager.instance().show("已设置不再显示赞助页面", "success")
            self.close()
        except Exception as e:
            ToastManager.instance().show(f"保存设置失败：{e}", "error")
