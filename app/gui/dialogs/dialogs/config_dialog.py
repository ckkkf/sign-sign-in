import json
import os

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog, QVBoxLayout, QScrollArea, QWidget, QFormLayout, QHBoxLayout, QLabel, QPushButton, \
    QSpacerItem, QMessageBox, QLineEdit

from app.gui.components.toast import ToastManager
from app.utils.files import read_config, save_json_file
from app.utils.model_client import test_model_connection, ModelConfigurationError


class ConfigDialog(QDialog):
    def __init__(self, config_path, parent=None):
        super().__init__(parent)
        self.config_path = config_path
        self.setWindowTitle("修改配置")
        self.resize(600, 500)
        self.original_data = read_config(config_path)
        self.current_data = json.loads(json.dumps(self.original_data))
        self.current_data.setdefault('model', {"baseUrl": "", "apiKey": "", "model": ""})
        self.inputs = {}
        self.is_modified = False
        self.setup_style()
        self.setup_ui()

    def setup_style(self):
        self.setStyleSheet("""
            QDialog {
                background: #0F111A;
                color: #E6E9FF;
            }
            QLabel {
                color: #8E95B4;
                font-weight: 600;
            }
            QWidget#FormContainer {
                background: #151828;
                border: 1px solid #232841;
                border-radius: 16px;
                padding: 12px 18px;
            }
            QLineEdit {
                background: #1C2033;
                border: 1px solid #2F3654;
                color: #F5F6FF;
                padding: 10px;
                border-radius: 10px;
            }
            QLineEdit:focus {
                border-color: #6E7BFF;
                box-shadow: 0 0 12px rgba(110,123,255,0.24);
            }
            QPushButton {
                background: #1F2336;
                color: #D5D9FF;
                padding: 8px 16px;
                border: 1px solid #2F3452;
                border-radius: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                border-color: #7C89FF;
                color: white;
            }
            #LinkBtn {
                color: #58D68D;
                border: none;
                background: transparent;
                text-align: left;
                font-weight: bold;
            }
            #LinkBtn:hover { text-decoration: underline; }
            QPushButton#Primary {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4E8BFF, stop:1 #7A5BFF);
                color: white;
                border: none;
            }
        """)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content.setObjectName("FormContainer")
        form = QFormLayout()
        form.setSpacing(10)
        content.setLayout(form)

        input_conf = self.current_data.get('input', {})
        loc = input_conf.get('location', {})
        dev = input_conf.get('device', {})
        model_conf = self.current_data.get('model', {})

        # ===========================================================
        # 位置（标题 + 按钮 一行）
        # ===========================================================
        pos_row = QHBoxLayout()
        lbl_pos = QLabel("位置")
        lbl_pos.setStyleSheet("color: #007ACC; font-size: 11pt; margin-top: 10px; font-weight: bold;")

        btn_loc = QPushButton("📍 获取坐标")
        btn_loc.setObjectName("LinkBtn")
        btn_loc.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://lbs.amap.com/tools/picker")))

        pos_row.addWidget(lbl_pos)
        pos_row.addStretch()
        pos_row.addWidget(btn_loc)

        form.addRow(pos_row)

        # 经纬度
        self.add_row(form, "经度", "lng", loc.get('longitude', ''))
        self.add_row(form, "纬度", "lat", loc.get('latitude', ''))

        # 区块底部空白
        form.addItem(QSpacerItem(0, 15))

        # ===========================================================
        # 设备（标题 + 按钮 一行）
        # ===========================================================
        dev_row = QHBoxLayout()
        lbl_dev = QLabel("设备")
        lbl_dev.setStyleSheet("color: #007ACC; font-size: 11pt; margin-top: 10px; font-weight: bold;")

        btn_ai = QPushButton("🤖 询问 AI")
        btn_ai.setObjectName("LinkBtn")
        btn_ai.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://www.doubao.com/chat/")))

        dev_row.addWidget(lbl_dev)
        dev_row.addStretch()
        dev_row.addWidget(btn_ai)

        form.addRow(dev_row)

        # 设备参数
        self.add_row(form, "品牌", "brand", dev.get('brand', ''))
        self.add_row(form, "型号", "model", dev.get('model', ''))
        self.add_row(form, "系统", "system", dev.get('system', ''))
        self.add_row(form, "平台", "platform", dev.get('platform', ''))
        self.add_row(form, "User-Agent", "userAgent", input_conf.get('userAgent', ''))

        # 设备区块底部空白
        form.addItem(QSpacerItem(0, 15))

        # ===========================================================
        # 模型接入
        # ===========================================================
        model_row = QHBoxLayout()
        lbl_model = QLabel("模型接入")
        lbl_model.setStyleSheet("color: #007ACC; font-size: 11pt; margin-top: 10px; font-weight: bold;")
        btn_test = QPushButton("🧪 测试连通性")
        btn_test.setObjectName("LinkBtn")
        btn_test.clicked.connect(self.test_model)
        model_row.addWidget(lbl_model)
        model_row.addStretch()
        model_row.addWidget(btn_test)
        form.addRow(model_row)

        self.add_row(form, "Base URL", "model_baseUrl", model_conf.get('baseUrl', ''))
        self.add_row(form, "API Key", "model_apiKey", model_conf.get('apiKey', ''))
        self.add_row(form, "模型名称", "model_model", model_conf.get('model', ''))

        form.addItem(QSpacerItem(0, 15))

        # ===========================================================
        # Scroll + 底部按钮区
        # ===========================================================
        scroll.setWidget(content)
        layout.addWidget(scroll)

        bot_layout = QHBoxLayout()
        btn_open = QPushButton("📄 打开配置文件")
        btn_open.clicked.connect(lambda: os.startfile(os.path.abspath(self.config_path)))
        bot_layout.addWidget(btn_open)

        btn_save = QPushButton("💾 保存并应用")
        btn_save.setObjectName("Primary")
        btn_save.clicked.connect(self.save_config)
        bot_layout.addWidget(btn_save)

        layout.addLayout(bot_layout)

    def add_sec(self, layout, title):
        l = QLabel(title)
        l.setStyleSheet("color: #007ACC; font-size: 11pt; margin-top: 10px;")
        layout.addRow(l)

    def add_row(self, layout, label, key, value):
        le = QLineEdit(str(value))
        le.textChanged.connect(lambda: setattr(self, 'is_modified', True))
        layout.addRow(label, le)
        self.inputs[key] = le

    def save_config(self):
        try:
            inp = self.current_data['input']
            inp['userAgent'] = self.inputs['userAgent'].text()
            inp['location'] = {'longitude': self.inputs['lng'].text(), 'latitude': self.inputs['lat'].text()}
            inp['device'] = {'brand': self.inputs['brand'].text(), 'model': self.inputs['model'].text(),
                'system': self.inputs['system'].text(), 'platform': self.inputs['platform'].text()}
            model_conf = self.current_data.setdefault('model', {})
            model_conf['baseUrl'] = self.inputs['model_baseUrl'].text().strip()
            model_conf['apiKey'] = self.inputs['model_apiKey'].text().strip()
            model_conf['model'] = self.inputs['model_model'].text().strip()
            save_json_file(self.config_path, self.current_data)
            self.is_modified = False
            # QMessageBox.information(self, "成功", "配置已保存")
            ToastManager.instance().show("配置保存成功", "success")
            # self.accept()
        except Exception as e:
            QMessageBox.critical(self, "错误", str(e))

    def test_model(self):
        cfg = {
            "baseUrl": self.inputs.get('model_baseUrl').text().strip() if 'model_baseUrl' in self.inputs else "",
            "apiKey": self.inputs.get('model_apiKey').text().strip() if 'model_apiKey' in self.inputs else "",
            "model": self.inputs.get('model_model').text().strip() if 'model_model' in self.inputs else "",
        }
        try:
            reply = test_model_connection(cfg)
            QMessageBox.information(self, "测试成功", reply)
        except ModelConfigurationError as exc:
            QMessageBox.warning(self, "配置不完整", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "测试失败", str(exc))

    def closeEvent(self, e):
        if self.is_modified:
            reply = QMessageBox.question(
                self,
                "配置未保存",
                "是否保存配置的更改？如果不保存，你的更改将丢失",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.Cancel
            )

            if reply == QMessageBox.Yes:
                self.save_config()
                e.accept()
            elif reply == QMessageBox.No:
                e.accept()
            else:  # Cancel
                e.ignore()
                return
        else:
            e.accept()

