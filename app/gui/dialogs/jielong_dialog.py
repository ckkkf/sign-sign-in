import os
from copy import deepcopy
import time

from PySide6.QtGui import QPixmap
from PySide6.QtCore import QThread, Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.apis.jielong import (
    build_local_media_files,
    build_submit_payload,
    create_qr_login,
    download_qrcode_image,
    exchange_qr_login_token,
    get_thread_id_by_url,
    load_form_bundle,
    parse_control_options,
    poll_qr_login,
    submit_record,
)
from app.config.common import CONFIG_FILE
from app.gui.components.no_wheel_combo import NoWheelComboBox
from app.gui.components.toast import ToastManager
from app.gui.dialogs.image_manager_dialog import ImageManagerDialog
from app.gui.dialogs.photo_sign_dialog import PhotoSignDialog
from app.utils.files import read_config, save_json_file


TITLE = "接龙"
FORM_TITLE = "接龙管家"
LOAD_BUTTON = "拉取表单"
LOADING_BUTTON = "拉取中..."
SUBMIT_BUTTON = "提交打卡"
SUBMITTING_BUTTON = "提交中..."
IDLE_TEXT = "待拉取"
FIELDS_TITLE = "接龙字段"
FIELDS_PLACEHOLDER = "点击“拉取表单”后在这里填写内容。"
EMPTY_FIELDS = "接口已返回，但没有可渲染字段。"
CHOOSE_TEXT = "请选择"
OTHER_PLACEHOLDER = "请补充说明"
LOCATION_AREA_PLACEHOLDER = "填写市区"
LOCATION_PLACE_PLACEHOLDER = "填写地点"
LOCATION_HINT_TEXT = "请分别填写市区和地点，系统会自动用“•”拼接；下方经纬度需填写有效数字。"
LOCATION_VALIDATION_ERROR = "请分别填写有效的市区、地点和经纬度。"
MEDIA_UNSUPPORTED = "图片将复用首页图片库，并在提交时自动上传。"
MEDIA_PICK = "选择图片"
MEDIA_MANAGE = "图片管理"
MEDIA_CLEAR = "清空"
MEDIA_EMPTY = "未选择图片"
MEDIA_SELECTED = "已选择：{name}"
LOAD_DONE_TEXT = "拉取完毕"
LOAD_FAILED = "拉取失败"
LOAD_WORKING = "正在拉取"
SUBMIT_SUCCESS = "提交成功"
SUBMIT_FAILED = "提交失败"
SUBMIT_WORKING = "正在提交"
SUBMIT_CONFIRM_TITLE = "确认提交"
SUBMIT_CONFIRM_TEXT = "确认按当前内容提交打卡吗？"
TOKEN_REQUIRED = "请先扫码登录获取 Token Token"
THREAD_REQUIRED = "请先解析接龙分享链接或填写 threadId"
SHARE_URL_REQUIRED = "请先粘贴接龙分享链接"
SHARE_URL_PLACEHOLDER = "粘贴接龙分享链接，例如 https://jielong.com/s/..."
PASTE_BUTTON = "解析"
LOGIN_IDLE_TEXT = "未获取 Token"
LOGIN_READY_TEXT = ""
LOGIN_TOKEN_EXCHANGE = "换取 Token 中"
LOGIN_QR_BUTTON = "扫码登录"
LOGIN_QR_BUTTON_LOADING = "扫码中..."
LOGIN_QR_PREPARING = "生成二维码中"
LOGIN_QR_READY_TEMPLATE = "等待扫码（{seconds:g}s）"
LOGIN_QR_HINT = "点击“扫码登录”后会弹出完整二维码；扫码成功后会按默认 1 秒轮询并换取 Token。"
LOGIN_QR_PLACEHOLDER = "二维码将在这里显示"
LOGIN_QR_SCANNED = "扫码成功"
LOGIN_QR_RETRYING = "微信轮询超时，正在重试..."
LOGIN_QR_DIALOG_TITLE = "接龙扫码登录"
LOGIN_QR_POLL_INTERVAL_SECONDS = 1.0
LOGIN_QR_MAX_TIMEOUT_RETRIES = 5
LOGIN_SUCCESS = "登录成功"
LOGIN_FAILED = "登录失败"
LOGIN_STOPPED = "已停止登录"
LOGIN_CERT_REQUIRED = "未检测到 mitm 证书，请先通过首页抓包功能安装证书后再试"
LOGIN_PROXY_ERROR = "代理服务未就绪，请稍后重试"
LOGIN_TIMEOUT = "等待登录回调超时"
LOAD_FIRST = "请先拉取接龙表单"
REQUIRED_BADGE = "必填"
TYPE_LOCATION = "位置"
TYPE_IMAGE = "图片"
TYPE_TEXTAREA = "多行"
TYPE_OPTIONS = "选项"
TYPE_TEXT = "文本"
SUBMIT_OK = "提交成功"
UNKNOWN_FIELD = "未命名字段"
SUMMARY_SUBJECT = "主题"
SUMMARY_DATE = "时间"
SUMMARY_STATUS = "状态"
SUMMARY_COUNT = "已接龙"
COUNT_TEMPLATE = "{users} 人 / {count} 次"


class JieLongLoadThread(QThread):
    success_signal = Signal(dict)
    error_signal = Signal(str)

    def __init__(self, token: str, thread_id: str):
        super().__init__()
        self.token = token
        self.thread_id = thread_id

    def run(self):
        try:
            result = load_form_bundle(self.token, self.thread_id)
            self.success_signal.emit(result)
        except Exception as exc:
            self.error_signal.emit(str(exc))


class JieLongSubmitThread(QThread):
    success_signal = Signal(dict)
    error_signal = Signal(str)

    def __init__(self, token: str, payload: dict):
        super().__init__()
        self.token = token
        self.payload = payload

    def run(self):
        try:
            result = submit_record(self.token, self.payload)
            self.success_signal.emit(result)
        except Exception as exc:
            self.error_signal.emit(str(exc))


class JieLongQrLoginThread(QThread):
    success_signal = Signal(dict)
    error_signal = Signal(str)
    status_signal = Signal(str)
    qr_ready_signal = Signal(dict)

    def __init__(self, authorization: str = "", poll_interval_seconds: float = LOGIN_QR_POLL_INTERVAL_SECONDS):
        super().__init__()
        self.authorization = str(authorization or "").strip()
        self.poll_interval_seconds = max(LOGIN_QR_POLL_INTERVAL_SECONDS, float(poll_interval_seconds or LOGIN_QR_POLL_INTERVAL_SECONDS))

    def check_stop(self):
        if self.isInterruptionRequested():
            raise RuntimeError(LOGIN_STOPPED)

    def _emit_status(self, text: str, last_text: str) -> str:
        if text != last_text:
            self.status_signal.emit(text)
        return text

    def run(self):
        try:
            self.check_stop()
            last_status = ""
            timeout_retries = 0
            last_status = self._emit_status(LOGIN_QR_PREPARING, last_status)
            qr_payload = create_qr_login()
            image_bytes = download_qrcode_image(qr_payload["qrcode_url"])
            self.qr_ready_signal.emit(
                {
                    "uuid": qr_payload["uuid"],
                    "qrcode_url": qr_payload["qrcode_url"],
                    "image_bytes": image_bytes,
                }
            )
            last_status = self._emit_status(
                LOGIN_QR_READY_TEMPLATE.format(seconds=self.poll_interval_seconds),
                last_status,
            )

            deadline = time.time() + 180
            while time.time() < deadline:
                self.check_stop()
                result = poll_qr_login(qr_payload["uuid"])
                status = result.get("status")
                message = str(result.get("message") or LOGIN_TIMEOUT)

                if status == "timeout":
                    timeout_retries += 1
                    if timeout_retries >= LOGIN_QR_MAX_TIMEOUT_RETRIES:
                        raise RuntimeError("微信轮询多次超时，请检查网络后重试")
                    last_status = self._emit_status(LOGIN_QR_RETRYING, last_status)
                    self.msleep(int(self.poll_interval_seconds * 1000))
                    continue

                timeout_retries = 0

                if status == "confirmed":
                    last_status = self._emit_status(LOGIN_TOKEN_EXCHANGE, last_status)
                    login_result = exchange_qr_login_token(
                        code=str(result.get("code") or ""),
                    )
                    self.success_signal.emit(login_result)
                    return

                if status == "scanned":
                    last_status = self._emit_status(LOGIN_QR_SCANNED, last_status)
                elif status == "waiting":
                    last_status = self._emit_status(
                        LOGIN_QR_READY_TEMPLATE.format(seconds=self.poll_interval_seconds),
                        last_status,
                    )
                elif status in {"expired", "error"}:
                    raise RuntimeError(message)

                self.msleep(int(self.poll_interval_seconds * 1000))

            raise RuntimeError(LOGIN_TIMEOUT)
        except Exception as exc:
            self.error_signal.emit(str(exc))


class JieLongQrPopupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(LOGIN_QR_DIALOG_TITLE)
        self.setModal(False)
        self.resize(392, 468)
        self.setMinimumSize(372, 448)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        self.hint_label = QLabel(LOGIN_QR_HINT)
        self.hint_label.setObjectName("SectionHint")
        self.hint_label.setWordWrap(True)
        layout.addWidget(self.hint_label)

        self.preview_label = QLabel(LOGIN_QR_PLACEHOLDER)
        self.preview_label.setObjectName("MediaPreview")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setWordWrap(True)
        self.preview_label.setMinimumSize(320, 320)
        layout.addWidget(self.preview_label, 1)

    def reset_preview(self, text: str = LOGIN_QR_PLACEHOLDER):
        self.preview_label.setPixmap(QPixmap())
        self.preview_label.setText(text)
        self.preview_label.setAlignment(Qt.AlignCenter)

    def set_preview_pixmap(self, pixmap: QPixmap):
        self.preview_label.setPixmap(
            pixmap.scaled(240, 240, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )
        self.preview_label.setText("")
        self.preview_label.setAlignment(Qt.AlignCenter)


class JieLongDialog(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("JieLongPage")
        self.setWindowTitle(TITLE)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self._login_thread = None
        self._login_mode = ""
        self._load_thread = None
        self._submit_thread = None
        self._current_bundle = None
        self._last_submit_token = ""
        self._last_submit_payload = None
        self._field_widgets = {}
        self._field_relations = {}
        self._conditional_targets = set()
        self._restoring_form_draft = False
        self._setup_style()
        self._setup_ui()
        self._load_saved_settings()
        self._sync_action_state()
        self._set_status(IDLE_TEXT)
        self._set_login_status(LOGIN_READY_TEXT)

    def _setup_style(self):
        self.setStyleSheet(
            """
            QWidget#JieLongPage {
                background: #0B1020;
                color: #ECF1FF;
            }
            QScrollArea {
                border: none;
                background: transparent;
            }
            QWidget#ScrollContent, QWidget#ScrollViewport {
                background: transparent;
            }
            #TopCard, #SummaryCard, #FieldCard, #PlaceholderCard, #BottomCard {
                background: #111827;
                border: 1px solid #1E2A46;
                border-radius: 16px;
            }
            #TopTitle {
                color: #F8FAFF;
                font-size: 12.8pt;
                font-weight: 800;
            }
            #SectionTitle {
                color: #EAF0FF;
                font-size: 8.2pt;
                font-weight: 700;
            }
            #SectionHint {
                color: #7C8BB8;
                font-size: 8.1pt;
                font-weight: 600;
            }
            #MetaLabel {
                color: #7F90BF;
                font-size: 7.9pt;
                font-weight: 600;
            }
            #MetaValue {
                color: #F3F6FF;
                font-size: 9.1pt;
                font-weight: 700;
            }
            #SummaryMetaLabel {
                color: #7F90BF;
                font-size: 6.3pt;
                font-weight: 600;
            }
            #SummaryMetaValue {
                color: #E9EEFF;
                font-size: 6.9pt;
                font-weight: 700;
            }
            #StatusChip {
                color: #D7DCEA;
                background: rgba(103, 112, 136, 0.16);
                border: 1px solid rgba(126, 136, 162, 0.24);
                border-radius: 10px;
                padding: 3px 10px;
                font-size: 7.4pt;
                font-weight: 700;
            }
            QLabel#StatusChip[tone="ready"] {
                color: #D7DCEA;
                background: rgba(103, 112, 136, 0.16);
                border-color: rgba(126, 136, 162, 0.24);
            }
            QLabel#StatusChip[tone="working"] {
                color: #DDF2FF;
                background: rgba(62, 146, 255, 0.18);
                border-color: rgba(89, 168, 255, 0.34);
            }
            QLabel#StatusChip[tone="success"] {
                color: #DFF8E8;
                background: rgba(40, 167, 99, 0.18);
                border-color: rgba(72, 194, 124, 0.34);
            }
            QLabel#StatusChip[tone="error"] {
                color: #FFE0E0;
                background: rgba(224, 72, 72, 0.18);
                border-color: rgba(244, 104, 104, 0.34);
            }
            QLabel#InputLabel {
                color: #B2C0E8;
                font-size: 6.9pt;
                font-weight: 700;
            }
            QLineEdit, QTextEdit, QComboBox {
                background: #162033;
                border: 1px solid #2A395B;
                color: #F6F8FF;
                border-radius: 10px;
                padding: 3px 8px;
                font-size: 7pt;
            }
            QLineEdit, QComboBox {
                min-height: 24px;
                max-height: 24px;
            }
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
                border-color: #5A84FF;
            }
            QLineEdit[invalid="true"], QLineEdit[invalid="true"]:focus {
                border-color: #F87171;
                background: rgba(127, 29, 29, 0.22);
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
                background: transparent;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid #AAB3E8;
                width: 0px;
                height: 0px;
                margin-right: 8px;
            }
            QPushButton {
                background: #18233A;
                color: #E0E7FF;
                border: 1px solid #304467;
                border-radius: 10px;
                padding: 5px 8px;
                font-size: 7.2pt;
                font-weight: 700;
            }
            QPushButton:hover {
                border-color: #7A93FF;
                color: #FFFFFF;
            }
            QPushButton:disabled {
                color: #7883A6;
                border-color: #2A314A;
                background: #141927;
            }
            QPushButton#PrimaryBtn {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4D86FF, stop:1 #7557FF);
                border: none;
                padding: 6px 12px;
            }
            QPushButton#QrLoginBtn {
                background: rgba(88, 109, 255, 0.18);
                color: #EEF2FF;
                border: 1px solid rgba(112, 132, 255, 0.42);
                min-width: 84px;
                min-height: 28px;
                max-height: 28px;
                padding: 0 10px;
            }
            QPushButton#QrLoginBtn:hover {
                background: rgba(88, 109, 255, 0.28);
                border-color: rgba(133, 151, 255, 0.58);
            }
            QPushButton#LoadBtn {
                background: rgba(88, 109, 255, 0.18);
                color: #EEF2FF;
                border: 1px solid rgba(112, 132, 255, 0.42);
                min-width: 72px;
                min-height: 24px;
                max-height: 24px;
                padding: 0 8px;
            }
            QPushButton#LoadBtn:hover {
                background: rgba(88, 109, 255, 0.28);
                border-color: rgba(133, 151, 255, 0.58);
            }
            QPushButton#LoadBtn:disabled {
                background: rgba(54, 61, 88, 0.24);
                color: #8D96B8;
                border-color: rgba(84, 92, 126, 0.28);
            }
            QPushButton#PasteBtn {
                background: rgba(88, 109, 255, 0.14);
                color: #EEF2FF;
                border: 1px solid rgba(112, 132, 255, 0.34);
                min-width: 40px;
                max-width: 40px;
                min-height: 24px;
                max-height: 24px;
                padding: 0 4px;
            }
            QPushButton#PasteBtn:hover {
                background: rgba(88, 109, 255, 0.24);
                border-color: rgba(133, 151, 255, 0.50);
            }
            QPushButton#PrimaryBtn:disabled {
                background: #26314F;
                color: #98A5CC;
            }
            #TypeBadge {
                color: #DCE5FF;
                background: rgba(88, 109, 255, 0.14);
                border: 1px solid rgba(106, 126, 255, 0.30);
                border-radius: 9px;
                padding: 1px 8px;
                font-size: 6.6pt;
                font-weight: 700;
            }
            #RequiredBadge {
                color: #FFD9D9;
                background: rgba(233, 87, 63, 0.14);
                border: 1px solid rgba(233, 87, 63, 0.28);
                border-radius: 9px;
                padding: 1px 8px;
                font-size: 6.5pt;
                font-weight: 700;
            }
            #FieldName {
                color: #F5F7FF;
                font-size: 8.5pt;
                font-weight: 800;
            }
            #FieldTip {
                color: #8994BB;
                font-size: 7.3pt;
                font-weight: 600;
            }
            #HintText {
                color: #91A2D0;
                font-size: 7.2pt;
                font-weight: 600;
            }
            #MediaPreview {
                color: #97A5CC;
                background: rgba(19, 28, 46, 0.72);
                border: 1px dashed #31425F;
                border-radius: 10px;
                min-height: 88px;
            }
            #EmptyText {
                color: #8D98BF;
                font-size: 7.7pt;
                font-weight: 600;
            }
            #BottomAccent {
                color: #C9D4FF;
                font-size: 7.5pt;
                font-weight: 700;
            }
            """
        )

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        top_card = QFrame()
        top_card.setObjectName("TopCard")
        top_layout = QVBoxLayout(top_card)
        top_layout.setContentsMargins(8, 6, 8, 6)
        top_layout.setSpacing(4)

        heading_row = QHBoxLayout()
        heading_row.setSpacing(8)

        heading_box = QVBoxLayout()
        heading_box.setSpacing(0)
        title = QLabel(FORM_TITLE)
        title.setObjectName("TopTitle")
        heading_box.addWidget(title)
        heading_row.addLayout(heading_box, 1)
        top_layout.addLayout(heading_row)

        login_heading = QHBoxLayout()
        login_heading.setSpacing(6)
        self.login_status_chip = QLabel("")
        self.login_status_chip.setObjectName("StatusChip")
        self.login_status_chip.hide()
        login_heading.addWidget(self.login_status_chip, 0, Qt.AlignLeft | Qt.AlignVCenter)
        login_heading.addStretch()
        top_layout.addLayout(login_heading)

        self.token_input = QLineEdit()
        self.token_input.setPlaceholderText(TOKEN_REQUIRED)
        self.token_input.setClearButtonEnabled(True)
        self.token_input.setFixedHeight(24)
        self.token_input.hide()

        share_label = QLabel("分享链接")
        share_label.setObjectName("InputLabel")
        top_layout.addWidget(share_label)

        share_input_row = QHBoxLayout()
        share_input_row.setContentsMargins(0, 0, 0, 0)
        share_input_row.setSpacing(4)

        self.share_url_input = QLineEdit()
        self.share_url_input.setPlaceholderText(SHARE_URL_PLACEHOLDER)
        self.share_url_input.setClearButtonEnabled(True)
        self.share_url_input.setFixedHeight(24)
        share_input_row.addWidget(self.share_url_input, 1)

        self.btn_paste_share = QPushButton(PASTE_BUTTON)
        self.btn_paste_share.setObjectName("PasteBtn")
        self.btn_paste_share.setFixedSize(40, 24)
        self.btn_paste_share.clicked.connect(lambda _checked=False: self._parse_share_url())
        share_input_row.addWidget(self.btn_paste_share)
        top_layout.addLayout(share_input_row)

        thread_label = QLabel("threadId")
        thread_label.setObjectName("InputLabel")
        top_layout.addWidget(thread_label)

        thread_row = QHBoxLayout()
        thread_row.setContentsMargins(0, 0, 0, 0)
        thread_row.setSpacing(6)

        self.thread_input = QLineEdit()
        self.thread_input.setPlaceholderText(THREAD_REQUIRED)
        self.thread_input.setClearButtonEnabled(True)
        self.thread_input.setFixedHeight(24)
        thread_row.addWidget(self.thread_input, 1)

        self.btn_load = QPushButton(LOAD_BUTTON)
        self.btn_load.setObjectName("LoadBtn")
        self.btn_load.setFixedSize(72, 24)
        self.btn_load.clicked.connect(self._start_load)
        thread_row.addWidget(self.btn_load)
        top_layout.addLayout(thread_row)

        layout.addWidget(top_card)

        self.summary_card = QFrame()
        self.summary_card.setObjectName("SummaryCard")
        summary_layout = QVBoxLayout(self.summary_card)
        summary_layout.setContentsMargins(6, 4, 6, 4)
        summary_layout.setSpacing(2)

        summary_grid = QHBoxLayout()
        summary_grid.setSpacing(6)
        self.summary_items = {}
        for key, label_text, stretch in (
            ("subject", SUMMARY_SUBJECT, 2),
            ("date", SUMMARY_DATE, 3),
            ("status", SUMMARY_STATUS, 1),
            ("count", SUMMARY_COUNT, 1),
        ):
            box = QVBoxLayout()
            box.setSpacing(2)
            label = QLabel(label_text)
            label.setObjectName("SummaryMetaLabel")
            value = QLabel("-")
            value.setObjectName("SummaryMetaValue")
            value.setWordWrap(key == "subject")
            box.addWidget(label)
            box.addWidget(value)
            summary_grid.addLayout(box, stretch)
            self.summary_items[key] = value
        summary_layout.addLayout(summary_grid)
        self.summary_card.hide()
        layout.addWidget(self.summary_card)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.viewport().setObjectName("ScrollViewport")

        content = QWidget()
        content.setObjectName("ScrollContent")
        self.form_layout = QVBoxLayout(content)
        self.form_layout.setContentsMargins(0, 0, 0, 0)
        self.form_layout.setSpacing(4)

        self.placeholder_card = QFrame()
        self.placeholder_card.setObjectName("PlaceholderCard")
        placeholder_layout = QVBoxLayout(self.placeholder_card)
        placeholder_layout.setContentsMargins(12, 10, 12, 10)
        placeholder_layout.setSpacing(4)
        placeholder_title = QLabel(FIELDS_TITLE)
        placeholder_title.setObjectName("SectionTitle")
        placeholder_layout.addWidget(placeholder_title)
        placeholder_text = QLabel(FIELDS_PLACEHOLDER)
        placeholder_text.setObjectName("EmptyText")
        placeholder_text.setWordWrap(True)
        placeholder_layout.addWidget(placeholder_text)
        self.form_layout.addWidget(self.placeholder_card)
        self.form_layout.addStretch()

        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        self.bottom_card = QFrame()
        self.bottom_card.setObjectName("BottomCard")
        bottom_layout = QHBoxLayout(self.bottom_card)
        bottom_layout.setContentsMargins(10, 8, 10, 8)
        bottom_layout.setSpacing(6)

        bottom_info = QVBoxLayout()
        bottom_info.setSpacing(0)
        self.status_chip = QLabel(IDLE_TEXT)
        self.status_chip.setObjectName("StatusChip")
        bottom_info.addWidget(self.status_chip, 0, Qt.AlignLeft | Qt.AlignVCenter)
        bottom_layout.addLayout(bottom_info, 1)

        self.btn_qr_login = QPushButton(LOGIN_QR_BUTTON)
        self.btn_qr_login.setObjectName("QrLoginBtn")
        self.btn_qr_login.setFixedHeight(28)
        self.btn_qr_login.setMinimumWidth(84)
        self.btn_qr_login.clicked.connect(self._start_qr_login)
        bottom_layout.addWidget(self.btn_qr_login, 0, Qt.AlignVCenter)

        self.btn_submit = QPushButton(SUBMIT_BUTTON)
        self.btn_submit.setObjectName("PrimaryBtn")
        self.btn_submit.setMinimumWidth(112)
        self.btn_submit.clicked.connect(self._start_submit)
        bottom_layout.addWidget(self.btn_submit, 0, Qt.AlignRight | Qt.AlignVCenter)

        layout.addWidget(self.bottom_card)
        self.qr_popup = JieLongQrPopupDialog(self)

    def _load_config(self) -> dict:

        try:
            return read_config(CONFIG_FILE)
        except Exception:
            return {}

    def _load_config_for_update(self) -> dict | None:
        if not os.path.exists(CONFIG_FILE):
            return {}
        try:
            return read_config(CONFIG_FILE)
        except Exception:
            ToastManager.instance().show("配置文件读取失败，已停止自动写入，避免覆盖原配置", "error")
            return None

    def _update_config_file(self, updater) -> bool:
        config = self._load_config_for_update()
        if config is None:
            return False
        updater(config)
        save_json_file(CONFIG_FILE, config)
        return True

    def _load_saved_settings(self):
        config = self._load_config()
        jielong = ((config.get("settings") or {}).get("jielong") or {})
        self.token_input.setText(str(jielong.get("authorization") or ""))
        self.thread_input.setText(str(jielong.get("thread_id") or ""))
        self.share_url_input.setText(str(jielong.get("share_url") or ""))

    def _save_settings(self, login_meta: dict | None = None):
        def updater(config: dict):
            settings = config.setdefault("settings", {})
            jielong = settings.setdefault("jielong", {})
            jielong["authorization"] = self.token_input.text().strip()
            jielong["thread_id"] = self.thread_input.text().strip()
            jielong["share_url"] = self.share_url_input.text().strip()
            if login_meta:
                for key in ("OpenId", "SId", "Expire", "TermsAgreed", "IsNew"):
                    if key in login_meta:
                        jielong[key[0].lower() + key[1:]] = login_meta.get(key)
        self._update_config_file(updater)

    def _current_form_draft_key(self) -> str:
        thread_id = ""
        if isinstance(self._current_bundle, dict):
            thread = self._current_bundle.get("thread") or {}
            edit_detail = self._current_bundle.get("edit_detail") or {}
            thread_id = str(thread.get("ThreadId") or edit_detail.get("ThreadId") or "").strip()
        if not thread_id:
            thread_id = self.thread_input.text().strip()
        return thread_id

    def _load_form_draft_answers(self) -> dict:
        config = self._load_config() or {}
        jielong = ((config.get("settings") or {}).get("jielong") or {})
        drafts = jielong.get("form_drafts") or {}
        thread_key = self._current_form_draft_key()
        draft = drafts.get(thread_key) or {}
        answers = draft.get("answers") or {}
        return deepcopy(answers) if isinstance(answers, dict) else {}

    def _collect_field_answers(self, *, visible_only: bool) -> dict:
        answers = {}
        fields = (self._current_bundle or {}).get("fields") or []
        for field in fields:
            field_id = str(field.get("Id"))
            info = self._field_widgets.get(field_id)
            if not info:
                continue
            if visible_only and int(field.get("Id") or 0) != 0 and info["card"].isHidden():
                continue

            kind = info["kind"]
            if kind == "select":
                option = info["widget"].currentData()
                answers[field_id] = {
                    "option_text": str((option or {}).get("Text") or info["widget"].currentText() or "").strip(),
                    "option_value": str((option or {}).get("Value") or "").strip(),
                    "other_value": info["other_widget"].text().strip(),
                }
            elif kind == "textarea":
                answers[field_id] = {"value": info["widget"].toPlainText().strip()}
            elif kind == "location":
                area = info["area_widget"].text().strip()
                place = info["place_widget"].text().strip()
                answers[field_id] = {
                    "value": self._compose_location_text(area, place),
                    "area": area,
                    "place": place,
                    "longitude": info["longitude_widget"].text().strip(),
                    "latitude": info["latitude_widget"].text().strip(),
                }
            elif kind == "text":
                answers[field_id] = {"value": info["widget"].text().strip()}
            elif kind == "media":
                answers[field_id] = {"files": deepcopy(info.get("files") or [])}
        return answers

    @staticmethod
    def _compose_location_text(area: str, place: str) -> str:
        left = str(area or "").strip()
        right = str(place or "").strip()
        if left and right:
            return f"{left}•{right}"
        return left or right

    @staticmethod
    def _split_location_text(value: str) -> tuple[str, str]:
        text = str(value or "").strip()
        if not text:
            return "", ""
        separator = "•" if "•" in text else "·" if "·" in text else ""
        if not separator:
            return text, ""
        area, place = [part.strip() for part in text.split(separator, 1)]
        return area, place

    @staticmethod
    def _is_valid_location_area(value: str) -> bool:
        text = str(value or "").strip()
        if not text or len(text) < 4:
            return False
        return any(marker in text for marker in ("市", "区", "县", "旗", "镇", "乡", "街道", "新区", "开发区"))

    @staticmethod
    def _is_valid_location_place(value: str) -> bool:
        text = str(value or "").strip()
        return len(text) >= 2

    @staticmethod
    def _is_valid_coordinate_value(value: str, *, axis: str) -> bool:
        text = str(value or "").strip()
        if not text:
            return False
        try:
            number = float(text)
        except (TypeError, ValueError):
            return False
        minimum, maximum = (-180.0, 180.0) if axis == "longitude" else (-90.0, 90.0)
        return minimum <= number <= maximum

    @staticmethod
    def _set_line_edit_invalid(widget: QLineEdit, invalid: bool):
        widget.setProperty("invalid", invalid)
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()

    def _validate_location_widgets(self, info: dict, *, strict: bool) -> bool:
        area = info["area_widget"].text().strip()
        place = info["place_widget"].text().strip()
        longitude = info["longitude_widget"].text().strip()
        latitude = info["latitude_widget"].text().strip()
        has_any_value = bool(area or place or longitude or latitude)

        area_invalid = False
        place_invalid = False
        longitude_invalid = False
        latitude_invalid = False

        if strict or has_any_value:
            area_invalid = not self._is_valid_location_area(area)
            place_invalid = not self._is_valid_location_place(place)

        if strict or longitude or latitude:
            longitude_invalid = not self._is_valid_coordinate_value(longitude, axis="longitude")
            latitude_invalid = not self._is_valid_coordinate_value(latitude, axis="latitude")

        self._set_line_edit_invalid(info["area_widget"], area_invalid)
        self._set_line_edit_invalid(info["place_widget"], place_invalid)
        self._set_line_edit_invalid(info["longitude_widget"], longitude_invalid)
        self._set_line_edit_invalid(info["latitude_widget"], latitude_invalid)
        return not (area_invalid or place_invalid or longitude_invalid or latitude_invalid)

    def _validate_visible_location_fields(self):
        for info in self._field_widgets.values():
            if info.get("kind") != "location":
                continue
            field = info.get("field") or {}
            if int(field.get("Id") or 0) != 0 and info["card"].isHidden():
                continue
            has_any_value = any(
                widget.text().strip()
                for widget in (
                    info["area_widget"],
                    info["place_widget"],
                    info["longitude_widget"],
                    info["latitude_widget"],
                )
            )
            if not field.get("IsRequired") and not has_any_value:
                self._validate_location_widgets(info, strict=False)
                continue
            if not self._validate_location_widgets(info, strict=True):
                raise RuntimeError(LOCATION_VALIDATION_ERROR)

    def _on_location_changed(self, info: dict):
        self._validate_location_widgets(info, strict=False)
        self._save_form_draft()

    def _save_form_draft(self):
        if self._restoring_form_draft or not self._current_bundle:
            return
        thread_key = self._current_form_draft_key()
        if not thread_key:
            return
        answers = self._collect_field_answers(visible_only=False)
        def updater(config: dict):
            settings = config.setdefault("settings", {})
            jielong = settings.setdefault("jielong", {})
            drafts = jielong.setdefault("form_drafts", {})
            drafts[thread_key] = {"answers": answers}
        self._update_config_file(updater)

    def _bind_form_draft_persistence(self, info: dict):
        kind = info.get("kind")
        if kind == "select":
            info["widget"].currentIndexChanged.connect(lambda *_: self._save_form_draft())
            info["other_widget"].textChanged.connect(lambda *_: self._save_form_draft())
            return
        if kind == "textarea":
            info["widget"].textChanged.connect(self._save_form_draft)
            return
        if kind == "location":
            info["widget"].textChanged.connect(lambda *_: self._on_location_changed(info))
            info["place_widget"].textChanged.connect(lambda *_: self._on_location_changed(info))
            info["longitude_widget"].textChanged.connect(lambda *_: self._on_location_changed(info))
            info["latitude_widget"].textChanged.connect(lambda *_: self._on_location_changed(info))
            return
        if kind == "text":
            info["widget"].textChanged.connect(lambda *_: self._save_form_draft())

    def _apply_form_draft_answers(self):
        answers = self._load_form_draft_answers()
        if not answers:
            return
        self._restoring_form_draft = True
        try:
            for field_id, info in self._field_widgets.items():
                answer = answers.get(field_id) or {}
                kind = info.get("kind")
                if kind == "select":
                    target_value = str(answer.get("option_value") or "").strip()
                    target_text = str(answer.get("option_text") or "").strip()
                    matched_index = 0
                    for index in range(1, info["widget"].count()):
                        option = info["widget"].itemData(index) or {}
                        option_value = str(option.get("Value") or "").strip()
                        option_text = str(option.get("Text") or info["widget"].itemText(index) or "").strip()
                        if (target_value and option_value == target_value) or (target_text and option_text == target_text):
                            matched_index = index
                            break
                    info["widget"].setCurrentIndex(matched_index)
                    info["other_widget"].setText(str(answer.get("other_value") or ""))
                elif kind == "textarea":
                    info["widget"].setPlainText(str(answer.get("value") or ""))
                elif kind == "location":
                    area = str(answer.get("area") or "").strip()
                    place = str(answer.get("place") or "").strip()
                    if not area and not place:
                        area, place = self._split_location_text(str(answer.get("value") or ""))
                    info["widget"].setText(area)
                    info["place_widget"].setText(place)
                    info["longitude_widget"].setText(str(answer.get("longitude") or ""))
                    info["latitude_widget"].setText(str(answer.get("latitude") or ""))
                    self._validate_location_widgets(info, strict=False)
                elif kind == "text":
                    info["widget"].setText(str(answer.get("value") or ""))
                elif kind == "media":
                    info["files"] = deepcopy(answer.get("files") or [])
                    self._refresh_media_widget(info)
        finally:
            self._restoring_form_draft = False
        self._refresh_visibility()

    def _format_location_hint(self) -> str:
        return LOCATION_HINT_TEXT

    def _sync_action_state(self):
        busy = self._is_busy()
        has_bundle = bool(self._current_bundle)
        logging_in = self._is_logging_in()
        login_blocked = self._is_loading() or self._is_submitting()
        self.share_url_input.setEnabled(not busy)
        self.btn_paste_share.setEnabled(not busy)
        self.thread_input.setEnabled(not busy)
        self.btn_load.setEnabled(not busy)
        self.btn_submit.setEnabled(has_bundle and not busy)
        self.btn_qr_login.setEnabled(not login_blocked)
        self.btn_load.setText(LOADING_BUTTON if self._is_loading() else LOAD_BUTTON)
        self.btn_submit.setText(SUBMITTING_BUTTON if self._is_submitting() else SUBMIT_BUTTON)
        self.btn_qr_login.setText(
            LOGIN_QR_BUTTON_LOADING if logging_in and self._login_mode == "qr" else LOGIN_QR_BUTTON
        )

    def _set_status(self, text: str):
        self._set_chip_text(self.status_chip, text)

    def _set_login_status(self, text: str):
        self._set_chip_text(self.login_status_chip, text)
        self.login_status_chip.setVisible(bool(str(text or "").strip()))
        self.login_status_chip.setVisible(bool(str(text or "").strip()))

    def _set_chip_text(self, chip: QLabel, text: str):
        chip.setText(text)
        chip.setProperty("tone", self._status_tone_for_text(text))
        self.style().unpolish(chip)
        self.style().polish(chip)
        chip.update()

    @staticmethod
    def _status_tone_for_text(text: str) -> str:
        if text in {LOAD_FAILED, SUBMIT_FAILED, LOGIN_FAILED}:
            return "error"
        if text in {LOAD_DONE_TEXT, SUBMIT_SUCCESS, LOGIN_SUCCESS}:
            return "success"
        if text in {
            LOAD_WORKING,
            SUBMIT_WORKING,
            LOGIN_TOKEN_EXCHANGE,
            LOGIN_QR_PREPARING,
            LOGIN_QR_SCANNED,
        } or text.startswith("二维码已就绪"):
            return "working"
        return "ready"

    @staticmethod
    def _looks_like_invalid_token_error(message: str) -> bool:
        text = str(message or "").strip()
        lower = text.lower()
        return (
            "token" in lower
            or "authorization" in lower
            or "bearer" in lower
            or "\u6388\u6743\u9a8c\u8bc1\u5931\u8d25" in text
            or "\u8bf7\u5148\u767b\u5f55" in text
            or "\u672a\u767b\u5f55" in text
            or "\u767b\u5f55" in text
        )

    def _clear_token_if_invalid(self, message: str) -> None:
        if not self._looks_like_invalid_token_error(message):
            return
        if not self.token_input.text().strip():
            return
        self.token_input.clear()
        self._save_settings()
        ToastManager.instance().show("\u68c0\u6d4b\u5230 Token \u5df2\u5931\u6548\uff0c\u5df2\u81ea\u52a8\u6e05\u7a7a\uff0c\u8bf7\u91cd\u65b0\u83b7\u53d6", "warning")

    def _is_loading(self) -> bool:
        return bool(self._load_thread and self._load_thread.isRunning())

    def _is_submitting(self) -> bool:
        return bool(self._submit_thread and self._submit_thread.isRunning())

    def _is_logging_in(self) -> bool:
        return bool(self._login_thread and self._login_thread.isRunning())

    def _is_busy(self) -> bool:
        return self._is_loading() or self._is_submitting() or self._is_logging_in()

    def _parse_share_url(self, show_toast: bool = True):
        share_url = self.share_url_input.text().strip()
        if not share_url:
            if show_toast:
                ToastManager.instance().show(SHARE_URL_REQUIRED, "warning")
            return
        try:
            thread_id = get_thread_id_by_url(share_url)
        except Exception as exc:
            if show_toast:
                ToastManager.instance().show(str(exc), "error")
            return
        self.thread_input.setText(thread_id)
        self._save_settings()
        if show_toast:
            ToastManager.instance().show(f"已解析 threadId：{thread_id}", "success")

    def _start_qr_login(self):
        if self._is_loading() or self._is_submitting():
            return
        if self._is_logging_in() and self._login_mode == "qr":
            self._present_qr_popup()
            return
        self._login_mode = "qr"
        self._save_settings()
        self._show_qr_popup(LOGIN_QR_PREPARING)
        self._set_login_status(LOGIN_QR_PREPARING)
        self._start_login_thread(
            JieLongQrLoginThread(
                authorization=self.token_input.text().strip(),
                poll_interval_seconds=LOGIN_QR_POLL_INTERVAL_SECONDS,
            )
        )

    def _start_login_thread(self, thread: QThread):
        if self._login_thread and self._login_thread.isRunning():
            self._login_thread.requestInterruption()
            self._login_thread.wait(500)
        self._login_thread = thread
        self._login_thread.success_signal.connect(
            lambda payload, source=thread: self._on_login_success(source, payload)
        )
        self._login_thread.error_signal.connect(
            lambda message, source=thread: self._on_login_failed(source, message)
        )
        self._login_thread.status_signal.connect(
            lambda text, source=thread: self._on_login_status(source, text)
        )
        if hasattr(self._login_thread, "qr_ready_signal"):
            self._login_thread.qr_ready_signal.connect(
                lambda payload, source=thread: self._on_qr_ready(source, payload)
            )
        self._login_thread.finished.connect(
            lambda source=thread: self._on_login_thread_finished(source)
        )
        self._sync_action_state()
        self._login_thread.start()

    def _present_qr_popup(self):
        self.qr_popup.show()
        if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
            return
        self.qr_popup.raise_()
        self.qr_popup.activateWindow()

    def _show_qr_popup(self, text: str = LOGIN_QR_PLACEHOLDER):
        self.qr_popup.reset_preview(text)
        self._present_qr_popup()

    def _hide_qr_popup(self):
        self.qr_popup.reset_preview()
        self.qr_popup.hide()

    def _stop_login(self, update_status: bool = True):
        if not self._is_logging_in():
            return False
        self._login_thread.requestInterruption()
        self._hide_qr_popup()
        if update_status:
            self._set_login_status(LOGIN_STOPPED)
        self._sync_action_state()
        return True

    def _on_login_status(self, source_thread: QThread, text: str):
        if source_thread is not self._login_thread:
            return
        self._set_login_status(text)

    def _on_qr_ready(self, source_thread: QThread, payload: dict):
        if source_thread is not self._login_thread or self._login_mode != "qr":
            return
        image_bytes = (payload or {}).get("image_bytes") or b""
        pixmap = QPixmap()
        if image_bytes and pixmap.loadFromData(image_bytes):
            self.qr_popup.set_preview_pixmap(pixmap)
            self._present_qr_popup()

    @staticmethod
    def _extract_login_token(payload: dict) -> str:
        data = (payload or {}).get("Data") or {}
        for candidate in (
            data.get("Token"),
            data.get("token"),
            data.get("Authorization"),
            data.get("authorization"),
            (payload or {}).get("Token"),
            (payload or {}).get("token"),
        ):
            token = str(candidate or "").strip()
            if token:
                return token
        return ""

    def _on_login_success(self, source_thread: QThread, payload: dict):
        if source_thread is not self._login_thread:
            return
        data = (payload or {}).get("Data") or {}
        token = self._extract_login_token(payload)
        if token:
            self.token_input.setText(token)
        self._hide_qr_popup()
        self._login_mode = ""
        self._save_settings(login_meta=data)
        self._set_login_status(LOGIN_SUCCESS)
        self._sync_action_state()
        ToastManager.instance().show("接龙登录成功，Token 已更新", "success")

    def _on_login_failed(self, source_thread: QThread, message: str):
        if source_thread is not self._login_thread:
            return
        text = str(message or LOGIN_FAILED).strip()
        self._login_mode = ""
        if text in {LOGIN_STOPPED, "已停止登录"}:
            self._hide_qr_popup()
            self._set_login_status(LOGIN_STOPPED)
            self._sync_action_state()
            ToastManager.instance().show("已停止接龙登录", "info")
            return
        self._set_login_status(LOGIN_FAILED)
        self._sync_action_state()
        ToastManager.instance().show(text, "error")

    def _on_login_thread_finished(self, source_thread: QThread):
        if source_thread is self._login_thread:
            self._login_thread = None
        self._sync_action_state()

    def _start_load(self):
        token = self.token_input.text().strip()
        thread_id = self.thread_input.text().strip()
        if not token:
            ToastManager.instance().show(TOKEN_REQUIRED, "warning")
            return
        if not thread_id:
            ToastManager.instance().show(THREAD_REQUIRED, "warning")
            return

        self._save_settings()
        self._set_status(LOAD_WORKING)

        if self._load_thread and self._load_thread.isRunning():
            self._load_thread.requestInterruption()
            self._load_thread.wait(500)

        self._load_thread = JieLongLoadThread(token, thread_id)
        self._load_thread.success_signal.connect(self._on_loaded)
        self._load_thread.error_signal.connect(self._on_failed)
        self._sync_action_state()
        self._load_thread.start()

    def _on_loaded(self, payload: dict):
        self._current_bundle = payload
        self._set_status(LOAD_DONE_TEXT)
        self._render_summary(payload)
        self._render_fields(payload.get("fields") or [])
        self._sync_action_state()
        ToastManager.instance().show("接龙表单加载成功", "success")

    def _on_failed(self, message: str):
        self._current_bundle = None
        self._clear_token_if_invalid(message)
        self._sync_action_state()
        self._set_status(LOAD_FAILED)
        ToastManager.instance().show(message, "error")

    def _start_submit(self):
        if not self._current_bundle:
            ToastManager.instance().show(LOAD_FIRST, "warning")
            return

        try:
            payload = self._build_submit_payload()
        except Exception as exc:
            ToastManager.instance().show(str(exc), "warning")
            return

        token = self.token_input.text().strip()
        confirm = QMessageBox.question(
            self,
            SUBMIT_CONFIRM_TITLE,
            SUBMIT_CONFIRM_TEXT,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            self._set_status(LOAD_DONE_TEXT)
            return
        self._submit_payload(token, payload)

    def _submit_payload(self, token: str, payload: dict):
        self._last_submit_token = token
        self._last_submit_payload = dict(payload)
        self._set_status(SUBMIT_WORKING)
        if self._submit_thread and self._submit_thread.isRunning():
            self._submit_thread.requestInterruption()
            self._submit_thread.wait(500)

        self._submit_thread = JieLongSubmitThread(token, payload)
        self._submit_thread.success_signal.connect(self._on_submitted)
        self._submit_thread.error_signal.connect(self._on_submit_failed)
        self._sync_action_state()
        self._submit_thread.start()

    def _on_submitted(self, payload: dict):
        self._set_status(SUBMIT_SUCCESS)
        self._sync_action_state()
        description = str(payload.get("Description") or SUBMIT_OK)
        ToastManager.instance().show(description, "success")

    def _on_submit_failed(self, message: str):
        self._clear_token_if_invalid(message)
        self._set_status(SUBMIT_FAILED)
        self._sync_action_state()
        if self._should_confirm_signature_mismatch(message):
            self._confirm_signature_and_resubmit()
            return
        ToastManager.instance().show(message, "error")

    def _should_confirm_signature_mismatch(self, message: str) -> bool:
        payload = self._last_submit_payload or {}
        return (
            "当前署名与您上一次提交的不符" in str(message)
            and not bool(payload.get("IsNameNumberComfirm"))
        )

    def _confirm_signature_and_resubmit(self):
        payload = dict(self._last_submit_payload or {})
        if not payload:
            return
        result = QMessageBox.question(
            self,
            "确认提交",
            "当前署名与您上一次提交的不符，是否继续提交？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if result != QMessageBox.Yes:
            ToastManager.instance().show("已取消提交", "info")
            return

        payload["IsNameNumberComfirm"] = True
        self._submit_payload(self._last_submit_token, payload)

    def _build_submit_payload(self) -> dict:
        self._validate_visible_location_fields()
        answers = self._collect_field_answers(visible_only=True)
        visible_fields = []
        fields = self._current_bundle.get("fields") or []
        for field in fields:
            field_id = str(field.get("Id"))
            info = self._field_widgets.get(field_id)
            if not info:
                continue
            if int(field.get("Id") or 0) != 0 and info["card"].isHidden():
                continue
            visible_fields.append(field)

        edit_detail = self._current_bundle.get("edit_detail") or {}
        signature = (answers.get("0") or {}).get("value") or str(
            edit_detail.get("LastSignature") or edit_detail.get("Signature") or ""
        )
        submit_bundle = dict(self._current_bundle)
        submit_bundle["fields"] = visible_fields
        return build_submit_payload(
            submit_bundle,
            answers,
            signature=signature,
            number=str(edit_detail.get("Number") or ""),
        )

    def _clear_form(self):
        while self.form_layout.count():
            item = self.form_layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget is not None:
                widget.deleteLater()
            elif child_layout is not None:
                while child_layout.count():
                    sub_item = child_layout.takeAt(0)
                    sub_widget = sub_item.widget()
                    if sub_widget is not None:
                        sub_widget.deleteLater()
        self._field_widgets.clear()
        self._field_relations.clear()
        self._conditional_targets.clear()

    def _render_summary(self, payload: dict):
        thread = payload.get("thread") or {}
        check_in = payload.get("check_in") or {}
        status = (check_in.get("CheckInStatus") or {}).get("CheckInMsg") or thread.get("AttendButtonText") or "-"
        date_range = self._format_summary_date_range(
            check_in.get("StartTime"),
            check_in.get("EndTime"),
        )
        count_value = COUNT_TEMPLATE.format(
            users=check_in.get("CheckInUserCount") or 0,
            count=check_in.get("CheckInCount") or 0,
        )

        self.summary_items["subject"].setText(str(thread.get("Subject") or "-"))
        self.summary_items["date"].setText(date_range)
        self.summary_items["status"].setText(str(status))
        self.summary_items["count"].setText(count_value)
        self.summary_card.show()

    @staticmethod
    def _format_summary_date_range(start_time, end_time) -> str:
        def _compact(value) -> str:
            text = str(value or "").strip()
            if not text or text == "-":
                return "-"
            parts = text.split()
            if len(parts) >= 2 and len(parts[0]) == 10:
                return f"{parts[0][5:]} {parts[1][:5]}"
            return text

        start = _compact(start_time)
        end = _compact(end_time)
        if start == "-" and end == "-":
            return "-"
        return f"{start} → {end}"

    def _media_caption(self, info: dict) -> str:
        files = info.get("files") or []
        if not files:
            return MEDIA_EMPTY
        first = files[0]
        name = str(first.get("Name") or first.get("FileName") or os.path.basename(str(first.get("LocalPath") or "")) or "图片")
        return MEDIA_SELECTED.format(name=name)

    def _refresh_media_widget(self, info: dict):
        preview = info["preview"]
        files = info.get("files") or []
        local_path = ""
        if files:
            local_path = str(files[0].get("LocalPath") or "").strip()
        preview.setText(self._media_caption(info))
        preview.setPixmap(QPixmap())
        if local_path and os.path.exists(local_path):
            pixmap = QPixmap(local_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(220, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                preview.setPixmap(scaled)
                return
        preview.setAlignment(Qt.AlignCenter)

    def _select_media_image(self, info: dict):
        dialog = PhotoSignDialog(self)
        dialog.setWindowTitle("选择接龙图片")
        if dialog.exec() != QDialog.Accepted or not dialog.selected_image:
            return
        info["files"] = build_local_media_files([dialog.selected_image])
        self._refresh_media_widget(info)
        self._save_form_draft()

    def _open_media_manager(self, info: dict):
        dialog = ImageManagerDialog(self)
        dialog.exec()
        self._refresh_media_widget(info)
        self._save_form_draft()

    def _clear_media_selection(self, info: dict):
        info["files"] = []
        self._refresh_media_widget(info)
        self._save_form_draft()

    def _render_fields(self, fields: list):
        self._clear_form()

        if not fields:
            self.placeholder_card = QFrame()
            self.placeholder_card.setObjectName("PlaceholderCard")
            placeholder_layout = QVBoxLayout(self.placeholder_card)
            placeholder_layout.setContentsMargins(10, 8, 10, 8)
            empty_text = QLabel(EMPTY_FIELDS)
            empty_text.setObjectName("EmptyText")
            empty_text.setWordWrap(True)
            placeholder_layout.addWidget(empty_text)
            self.form_layout.addWidget(self.placeholder_card)
            self.form_layout.addStretch()
            return

        for field in fields:
            for condition in field.get("VisibilityCondition") or []:
                for relation_id in condition.get("RelationIdList") or []:
                    relation_id = str(relation_id or "").strip()
                    if relation_id:
                        self._conditional_targets.add(relation_id)

        for field in fields:
            card = QFrame()
            card.setObjectName("FieldCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(8, 6, 8, 6)
            card_layout.setSpacing(4)

            head = QHBoxLayout()
            head.setSpacing(6)

            name = QLabel(str(field.get("Name") or UNKNOWN_FIELD))
            name.setObjectName("FieldName")
            head.addWidget(name)

            type_badge = QLabel(self._field_type_text(field))
            type_badge.setObjectName("TypeBadge")
            head.addWidget(type_badge, 0, Qt.AlignVCenter)

            if field.get("IsRequired"):
                required_badge = QLabel(REQUIRED_BADGE)
                required_badge.setObjectName("RequiredBadge")
                head.addWidget(required_badge, 0, Qt.AlignVCenter)

            head.addStretch()
            card_layout.addLayout(head)

            tip = str(field.get("Tip") or "").strip()
            if tip:
                tip_label = QLabel(tip)
                tip_label.setObjectName("FieldTip")
                tip_label.setWordWrap(True)
                card_layout.addWidget(tip_label)

            widget_info = self._create_field_widget(field)
            card_layout.addWidget(widget_info["container"])
            widget_info["card"] = card
            widget_info["field"] = field
            self._bind_form_draft_persistence(widget_info)
            self.form_layout.addWidget(card)
            self._field_widgets[str(field.get("Id"))] = widget_info

            relation_id = str(field.get("RelationId") or "").strip()
            if relation_id:
                self._field_relations[relation_id] = widget_info

        self._apply_form_draft_answers()
        self.form_layout.addStretch()
        self._refresh_visibility()

    def _field_type_text(self, field: dict) -> str:
        field_type = int(field.get("FieldType") or 0)
        if field_type == 16:
            return TYPE_LOCATION
        if field_type == 25:
            return TYPE_IMAGE
        if field.get("IsTextarea"):
            return TYPE_TEXTAREA
        if parse_control_options(field.get("ControlOptions")):
            return TYPE_OPTIONS
        return TYPE_TEXT

    def _create_field_widget(self, field: dict):
        initial_value = str(field.get("InitialValue") or "")
        placeholder = str(field.get("Tip") or field.get("Name") or "")
        field_type = int(field.get("FieldType") or 0)

        options = parse_control_options(field.get("ControlOptions"))
        if options:
            container = QWidget()
            layout = QVBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(3)

            combo = NoWheelComboBox()
            combo.addItem(CHOOSE_TEXT, None)
            for option in options:
                combo.addItem(str(option.get("Text") or ""), option)
            layout.addWidget(combo)

            other_input = QLineEdit()
            other_input.setPlaceholderText(OTHER_PLACEHOLDER)
            other_input.hide()
            layout.addWidget(other_input)

            selected_index = 0
            matched_other_text = ""
            for index, option in enumerate(options, start=1):
                text = str(option.get("Text") or "")
                value = str(option.get("Value") or "")
                if initial_value and initial_value in {text, value}:
                    selected_index = index
                    break
                if initial_value and option.get("IsOtherOption"):
                    matched_other_text = initial_value
                    selected_index = index
            combo.setCurrentIndex(selected_index)
            if matched_other_text:
                other_input.setText(matched_other_text)

            info = {
                "kind": "select",
                "container": container,
                "widget": combo,
                "other_widget": other_input,
            }
            combo.currentIndexChanged.connect(lambda *_: self._on_select_changed(info))
            self._on_select_changed(info)
            return info

        if field_type == 25:
            container = QWidget()
            layout = QVBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(3)

            preview = QLabel(MEDIA_EMPTY)
            preview.setObjectName("MediaPreview")
            preview.setAlignment(Qt.AlignCenter)
            preview.setWordWrap(True)
            layout.addWidget(preview)

            actions = QHBoxLayout()
            actions.setContentsMargins(0, 0, 0, 0)
            actions.setSpacing(4)
            pick_btn = QPushButton(MEDIA_PICK)
            manage_btn = QPushButton(MEDIA_MANAGE)
            clear_btn = QPushButton(MEDIA_CLEAR)
            actions.addWidget(pick_btn)
            actions.addWidget(manage_btn)
            actions.addWidget(clear_btn)
            actions.addStretch()
            layout.addLayout(actions)

            hint = QLabel(MEDIA_UNSUPPORTED)
            hint.setObjectName("HintText")
            hint.setWordWrap(True)
            layout.addWidget(hint)

            info = {
                "kind": "media",
                "container": container,
                "widget": preview,
                "preview": preview,
                "files": list(field.get("InitialFiles") or []),
            }
            pick_btn.clicked.connect(lambda: self._select_media_image(info))
            manage_btn.clicked.connect(lambda: self._open_media_manager(info))
            clear_btn.clicked.connect(lambda: self._clear_media_selection(info))
            self._refresh_media_widget(info)
            return info

        if field.get("IsTextarea"):
            editor = QTextEdit()
            editor.setPlaceholderText(placeholder)
            editor.setPlainText(initial_value)
            editor.setFixedHeight(max(48, min(int(field.get("Rows") or 3) * 16 + 8, 92)))
            return {"kind": "textarea", "container": editor, "widget": editor}

        if field_type == 16:
            container = QWidget()
            layout = QVBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(3)

            edit_label = QLabel("位置说明")
            edit_label.setObjectName("InputLabel")
            layout.addWidget(edit_label)

            text_row = QHBoxLayout()
            text_row.setContentsMargins(0, 0, 0, 0)
            text_row.setSpacing(6)

            area_value, place_value = self._split_location_text(initial_value)

            area_input = QLineEdit()
            area_input.setPlaceholderText(LOCATION_AREA_PLACEHOLDER)
            area_input.setClearButtonEnabled(True)
            area_input.setToolTip("填写市区部分，提交时会自动拼接“•”。")
            area_input.setText(area_value)
            text_row.addWidget(area_input)

            dot_label = QLabel("•")
            dot_label.setObjectName("InputLabel")
            text_row.addWidget(dot_label, 0, Qt.AlignCenter)

            place_input = QLineEdit()
            place_input.setPlaceholderText(LOCATION_PLACE_PLACEHOLDER)
            place_input.setClearButtonEnabled(True)
            place_input.setToolTip("填写地点部分，提交时会自动拼接“•”。")
            place_input.setText(place_value)
            text_row.addWidget(place_input)

            layout.addLayout(text_row)

            coord_row = QHBoxLayout()
            coord_row.setContentsMargins(0, 0, 0, 0)
            coord_row.setSpacing(6)

            longitude_input = QLineEdit()
            longitude_input.setPlaceholderText("经度，例如 119.20336")
            longitude_input.setClearButtonEnabled(True)
            coord_row.addWidget(longitude_input)

            latitude_input = QLineEdit()
            latitude_input.setPlaceholderText("纬度，例如 36.73202")
            latitude_input.setClearButtonEnabled(True)
            coord_row.addWidget(latitude_input)

            layout.addLayout(coord_row)

            hint = QLabel(self._format_location_hint())
            hint.setObjectName("HintText")
            hint.setWordWrap(True)
            layout.addWidget(hint)
            info = {
                "kind": "location",
                "container": container,
                "widget": area_input,
                "area_widget": area_input,
                "place_widget": place_input,
                "hint": hint,
                "edit_label": edit_label,
                "separator_label": dot_label,
                "longitude_widget": longitude_input,
                "latitude_widget": latitude_input,
            }
            self._validate_location_widgets(info, strict=False)
            return info

        line_edit = QLineEdit()
        line_edit.setPlaceholderText(placeholder)
        line_edit.setText(initial_value)
        return {"kind": "text", "container": line_edit, "widget": line_edit}

    def _on_select_changed(self, info: dict):
        option = info["widget"].currentData()
        is_other = bool(option and option.get("IsOtherOption"))
        info["other_widget"].setVisible(is_other)
        self._refresh_visibility()
        self._save_form_draft()

    def _refresh_visibility(self):
        active_relations = set()
        for info in self._field_widgets.values():
            field = info.get("field") or {}
            conditions = field.get("VisibilityCondition") or []
            if not conditions or info.get("kind") != "select":
                continue
            selected = info["widget"].currentData()
            selected_value = str((selected or {}).get("Value") or "").strip()
            for condition in conditions:
                option_value = str(condition.get("OptionValue") or "").strip()
                if option_value and option_value == selected_value:
                    for relation_id in condition.get("RelationIdList") or []:
                        relation_id = str(relation_id or "").strip()
                        if relation_id:
                            active_relations.add(relation_id)

        for relation_id, info in self._field_relations.items():
            should_show = relation_id not in self._conditional_targets or relation_id in active_relations
            info["card"].setVisible(should_show)

    def closeEvent(self, event):
        if self._login_thread and self._login_thread.isRunning():
            self._login_thread.requestInterruption()
            self._login_thread.wait(1000)
        if self._load_thread and self._load_thread.isRunning():
            self._load_thread.requestInterruption()
            self._load_thread.wait(1000)
        if self._submit_thread and self._submit_thread.isRunning():
            self._submit_thread.requestInterruption()
            self._submit_thread.wait(1000)
        self._hide_qr_popup()
        self.qr_popup.close()
        event.accept()
