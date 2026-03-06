import json
import os
import re

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog, QVBoxLayout, QScrollArea, QWidget, QFormLayout, QHBoxLayout, QLabel, QPushButton, \
    QSpacerItem, QMessageBox, QLineEdit, QComboBox

from app.gui.components.toast import ToastManager
from app.utils.files import (
    build_user_agent,
    read_config,
    save_json_file,
    validate_config,
    validate_user_agent_matches_device,
)
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
            QComboBox {
                background: #1C2033;
                border: 1px solid #2F3654;
                color: #F5F6FF;
                padding: 8px 10px;
                border-radius: 10px;
                min-height: 22px;
            }
            QComboBox:hover {
                border-color: #7C89FF;
            }
            QComboBox:focus {
                border-color: #6E7BFF;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 28px;
                border: none;
                background: transparent;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 7px solid #AAB3E8;
                width: 0px;
                height: 0px;
                margin-right: 10px;
            }
            QComboBox QAbstractItemView {
                background: #1C2033;
                color: #F5F6FF;
                border: 1px solid #2F3654;
                selection-background-color: #2D365A;
                selection-color: #FFFFFF;
                outline: 0;
                padding: 4px;
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
            QLabel#Tip {
                color: #9AA4CF;
                font-size: 12px;
                font-weight: 500;
                padding: 2px 0 6px 0;
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
        system_ver = self.extract_android_version(dev.get('system', ''))
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
        self.add_tip(form, "提示：经纬度可用高德拾取器获取，建议保留 6 位小数。")

        # 区块底部空白
        form.addItem(QSpacerItem(0, 15))

        # ===========================================================
        # 设备（标题 + 按钮 一行）
        # ===========================================================
        dev_row = QHBoxLayout()
        lbl_dev = QLabel("设备")
        lbl_dev.setStyleSheet("color: #007ACC; font-size: 11pt; margin-top: 10px; font-weight: bold;")

        btn_ai = QPushButton("✨ 询问 AI")
        btn_ai.setObjectName("LinkBtn")
        btn_ai.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://www.doubao.com/chat/")))

        dev_row.addWidget(lbl_dev)
        dev_row.addStretch()
        dev_row.addWidget(btn_ai)

        form.addRow(dev_row)

        # 设备参数
        self.add_row(form, "品牌", "brand", dev.get('brand', ''))
        self.add_row(form, "型号", "model", dev.get('model', ''))
        self.add_row(form, "系统版本", "system_version", system_ver)
        self.add_tip(form, "提示：系统版本只填数字，例如 15（程序会自动拼成 Android 15）。")

        platform_combo = QComboBox()
        platform_combo.addItems(["android", "ios"])
        platform = str(dev.get('platform', 'android')).strip().lower()
        idx = platform_combo.findText(platform)
        platform_combo.setCurrentIndex(idx if idx >= 0 else 0)
        platform_combo.currentIndexChanged.connect(lambda: setattr(self, 'is_modified', True))
        form.addRow("平台", platform_combo)
        self.inputs['platform'] = platform_combo
        self.add_tip(form, "提示：安卓选 android，iPhone 选 ios。")

        ua_row = QHBoxLayout()
        ua_row.addWidget(QLabel("User-Agent"))
        btn_ua = QPushButton("↻ 生成UA")
        btn_ua.setObjectName("LinkBtn")
        btn_ua.clicked.connect(self.refresh_user_agent)
        ua_row.addStretch()
        ua_row.addWidget(btn_ua)
        form.addRow(ua_row)
        self.add_row(form, "", "userAgent", input_conf.get('userAgent', ''))
        self.inputs['userAgent'].setReadOnly(True)
        self.inputs['userAgent'].setPlaceholderText("根据设备参数自动生成")
        self.add_tip(form, "提示：UA 会随设备参数自动生成，无需手动修改。")

        for key in ('brand', 'model', 'system_version'):
            self.inputs[key].textChanged.connect(self.refresh_user_agent)
        self.inputs['platform'].currentIndexChanged.connect(self.refresh_user_agent)
        self.refresh_user_agent()

        # 设备区块底部空白
        form.addItem(QSpacerItem(0, 15))

        # ===========================================================
        # 模型接入
        # ===========================================================
        # model_row = QHBoxLayout()
        # lbl_model = QLabel("模型接入")
        # lbl_model.setStyleSheet("color: #007ACC; font-size: 11pt; margin-top: 10px; font-weight: bold;")
        # btn_test = QPushButton("🧪 测试连通性")
        # btn_test.setObjectName("LinkBtn")
        # btn_test.clicked.connect(self.test_model)
        # model_row.addWidget(lbl_model)
        # model_row.addStretch()
        # model_row.addWidget(btn_test)
        # form.addRow(model_row)
        #
        # self.add_row(form, "Base URL", "model_baseUrl", model_conf.get('baseUrl', ''))
        # self.add_row(form, "API Key", "model_apiKey", model_conf.get('apiKey', ''))
        # self.add_row(form, "模型名称", "model_model", model_conf.get('model', ''))
        #
        # form.addItem(QSpacerItem(0, 15))

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

    def add_tip(self, layout, text):
        tip = QLabel(text)
        tip.setObjectName("Tip")
        tip.setWordWrap(True)
        layout.addRow("", tip)

    def save_config(self):
        try:
            inp = self.current_data['input']
            system_version = self.get_input_value('system_version')
            system = f"Android {system_version}" if system_version else ""
            device = {
                'brand': self.get_input_value('brand'),
                'model': self.get_input_value('model'),
                'system': system,
                'platform': self.get_input_value('platform').lower()
            }
            inp['userAgent'] = build_user_agent(device)
            inp['location'] = {'longitude': self.inputs['lng'].text(), 'latitude': self.inputs['lat'].text()}
            inp['device'] = device

            ua_err = validate_user_agent_matches_device(device, inp['userAgent'])
            if ua_err:
                self.focus_error_field(ua_err)
                raise RuntimeError(ua_err)

            cfg_err = validate_config(self.current_data)
            if cfg_err:
                self.focus_error_field(cfg_err)
                raise RuntimeError(cfg_err)

            model_conf = self.current_data.setdefault('model', {})
            # model_conf['baseUrl'] = self.inputs['model_baseUrl'].text().strip()
            # model_conf['apiKey'] = self.inputs['model_apiKey'].text().strip()
            # model_conf['model'] = self.inputs['model_model'].text().strip()
            save_json_file(self.config_path, self.current_data)
            self.is_modified = False
            # QMessageBox.information(self, "成功", "配置已保存")
            ToastManager.instance().show("配置保存成功", "success")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "配置校验未通过", str(e))

    def refresh_user_agent(self):
        system_version = self.get_input_value('system_version')
        system = f"Android {system_version}" if system_version else ""
        device = {
            'brand': self.get_input_value('brand'),
            'model': self.get_input_value('model'),
            'system': system,
            'platform': self.get_input_value('platform').lower()
        }
        ua = build_user_agent(device)
        if 'userAgent' in self.inputs and self.inputs['userAgent'].text() != ua:
            self.inputs['userAgent'].setText(ua)

    def focus_error_field(self, err_msg: str):
        msg = str(err_msg)
        key = None
        if "经度" in msg or "longitude" in msg:
            key = "lng"
        elif "纬度" in msg or "latitude" in msg:
            key = "lat"
        elif "品牌" in msg or "brand" in msg:
            key = "brand"
        elif "型号" in msg or "model" in msg:
            key = "model"
        elif "系统" in msg or "system" in msg:
            key = "system_version"
        elif "平台" in msg or "platform" in msg:
            key = "platform"
        elif "UA" in msg or "User-Agent" in msg or "userAgent" in msg:
            key = "userAgent"

        if not key or key not in self.inputs:
            return

        target = self.inputs[key]
        target.setFocus()
        try:
            target.selectAll()
        except Exception:
            pass

        target.setStyleSheet("border: 2px solid #FF6B6B; background: #2A1E24;")
        QTimer.singleShot(1800, lambda: target.setStyleSheet(""))

    def get_input_value(self, key: str) -> str:
        widget = self.inputs.get(key)
        if widget is None:
            return ""
        if hasattr(widget, "text"):
            return widget.text().strip()
        if hasattr(widget, "currentText"):
            return widget.currentText().strip()
        return ""

    @staticmethod
    def extract_android_version(system_text: str) -> str:
        txt = str(system_text or "").strip()
        if not txt:
            return ""
        m = re.match(r"(?i)^android\s+(.+)$", txt)
        if m:
            return m.group(1).strip()
        return txt

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
