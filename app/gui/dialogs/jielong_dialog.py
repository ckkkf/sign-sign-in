from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
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
    build_submit_payload,
    load_form_bundle,
    parse_control_options,
    submit_record,
)
from app.config.common import CONFIG_FILE
from app.gui.components.toast import ToastManager
from app.utils.files import read_config, save_json_file


TITLE = "接龙"
FORM_TITLE = "接龙表单"
FORM_SUBTITLE = "填写 Token 和 threadId"
LOAD_BUTTON = "拉取表单"
LOADING_BUTTON = "拉取中..."
SUBMIT_BUTTON = "提交打卡"
SUBMITTING_BUTTON = "提交中..."
READY_TEXT = "准备就绪"
SUMMARY_TITLE = "表单概览"
FIELDS_TITLE = "接龙字段"
FIELDS_PLACEHOLDER = "点击“拉取表单”后在这里填写内容。"
EMPTY_FIELDS = "接口已返回，但没有可渲染字段。"
CHOOSE_TEXT = "请选择"
OTHER_PLACEHOLDER = "请补充说明"
LOCATION_PLACEHOLDER = "位置说明（坐标取自配置）"
LOCATION_HINT_TEMPLATE = "提交使用坐标：{longitude}, {latitude}"
LOCATION_HINT_EMPTY = "未检测到经纬度，请先到设置页补齐。"
MEDIA_UNSUPPORTED = "当前版本暂不支持图片上传；若该字段非必填，可留空继续提交。"
LOAD_SUCCESS = "接龙表单加载成功"
LOAD_FAILED = "接龙表单加载失败"
LOAD_WORKING = "正在拉取接龙表单..."
SUBMIT_SUCCESS = "接龙记录提交成功"
SUBMIT_FAILED = "接龙记录提交失败"
SUBMIT_WORKING = "正在提交接龙记录..."
TOKEN_REQUIRED = "请先填写 Bearer Token"
THREAD_REQUIRED = "请先填写 threadId"
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
BOTTOM_TITLE = "提交"


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


class JieLongDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(TITLE)
        self.resize(920, 700)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self._load_thread = None
        self._submit_thread = None
        self._current_bundle = None
        self._last_submit_token = ""
        self._last_submit_payload = None
        self._field_widgets = {}
        self._field_relations = {}
        self._conditional_targets = set()
        self._setup_style()
        self._setup_ui()
        self._load_saved_settings()
        self._sync_action_state()

    def _setup_style(self):
        self.setStyleSheet(
            """
            QDialog {
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
                border-radius: 18px;
            }
            #TopTitle {
                color: #F8FAFF;
                font-size: 17pt;
                font-weight: 800;
            }
            #TopSubTitle {
                color: #99A7D0;
                font-size: 9.5pt;
                font-weight: 600;
            }
            #SectionTitle {
                color: #EAF0FF;
                font-size: 10.8pt;
                font-weight: 700;
            }
            #SectionHint {
                color: #7C8BB8;
                font-size: 8.7pt;
                font-weight: 600;
            }
            #MetaLabel {
                color: #7F90BF;
                font-size: 8.4pt;
                font-weight: 600;
            }
            #MetaValue {
                color: #F3F6FF;
                font-size: 10pt;
                font-weight: 700;
            }
            #StatusLabel {
                color: #8FA2D8;
                font-size: 8.7pt;
                font-weight: 600;
            }
            QLabel#InputLabel {
                color: #B2C0E8;
                font-size: 8.5pt;
                font-weight: 700;
            }
            QLineEdit, QTextEdit, QComboBox {
                background: #162033;
                border: 1px solid #2A395B;
                color: #F6F8FF;
                border-radius: 12px;
                padding: 11px 13px;
                font-size: 9.2pt;
            }
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
                border-color: #5A84FF;
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
                border-radius: 12px;
                padding: 10px 18px;
                font-size: 9pt;
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
                padding: 12px 22px;
            }
            QPushButton#LoadBtn {
                min-width: 132px;
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
                font-size: 7.4pt;
                font-weight: 700;
            }
            #RequiredBadge {
                color: #FFD9D9;
                background: rgba(233, 87, 63, 0.14);
                border: 1px solid rgba(233, 87, 63, 0.28);
                border-radius: 9px;
                padding: 1px 8px;
                font-size: 7.2pt;
                font-weight: 700;
            }
            #FieldName {
                color: #F5F7FF;
                font-size: 10.3pt;
                font-weight: 800;
            }
            #FieldTip {
                color: #8994BB;
                font-size: 8.6pt;
                font-weight: 600;
            }
            #HintText {
                color: #91A2D0;
                font-size: 8.4pt;
                font-weight: 600;
            }
            #EmptyText {
                color: #8D98BF;
                font-size: 9.2pt;
                font-weight: 600;
            }
            #BottomAccent {
                color: #C9D4FF;
                font-size: 9pt;
                font-weight: 700;
            }
            """
        )

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        top_card = QFrame()
        top_card.setObjectName("TopCard")
        top_layout = QVBoxLayout(top_card)
        top_layout.setContentsMargins(16, 16, 16, 16)
        top_layout.setSpacing(10)

        heading_row = QHBoxLayout()
        heading_row.setSpacing(12)

        heading_box = QVBoxLayout()
        heading_box.setSpacing(3)
        title = QLabel(FORM_TITLE)
        title.setObjectName("TopTitle")
        heading_box.addWidget(title)

        subtitle = QLabel(FORM_SUBTITLE)
        subtitle.setObjectName("TopSubTitle")
        subtitle.setWordWrap(True)
        heading_box.addWidget(subtitle)
        heading_row.addLayout(heading_box, 1)
        top_layout.addLayout(heading_row)

        form_row = QHBoxLayout()
        form_row.setSpacing(12)
        form_row.setContentsMargins(0, 2, 0, 0)

        token_box = QVBoxLayout()
        token_box.setSpacing(8)
        token_label = QLabel("Bearer Token")
        token_label.setObjectName("InputLabel")
        token_box.addWidget(token_label)
        self.token_input = QLineEdit()
        self.token_input.setPlaceholderText(TOKEN_REQUIRED)
        self.token_input.setClearButtonEnabled(True)
        token_box.addWidget(self.token_input)
        form_row.addLayout(token_box, 4)

        thread_box = QVBoxLayout()
        thread_box.setSpacing(8)
        thread_label = QLabel("threadId")
        thread_label.setObjectName("InputLabel")
        thread_box.addWidget(thread_label)
        self.thread_input = QLineEdit()
        self.thread_input.setPlaceholderText(THREAD_REQUIRED)
        self.thread_input.setClearButtonEnabled(True)
        thread_box.addWidget(self.thread_input)
        form_row.addLayout(thread_box, 2)

        btn_box = QVBoxLayout()
        btn_box.setSpacing(8)
        btn_box.addStretch()
        self.btn_load = QPushButton(LOAD_BUTTON)
        self.btn_load.setObjectName("LoadBtn")
        self.btn_load.clicked.connect(self._start_load)
        btn_box.addWidget(self.btn_load)
        btn_box.addStretch()
        form_row.addLayout(btn_box, 0)

        top_layout.addLayout(form_row)

        self.status_label = QLabel(READY_TEXT)
        self.status_label.setObjectName("StatusLabel")
        top_layout.addWidget(self.status_label)

        layout.addWidget(top_card)

        self.summary_card = QFrame()
        self.summary_card.setObjectName("SummaryCard")
        summary_layout = QVBoxLayout(self.summary_card)
        summary_layout.setContentsMargins(16, 14, 16, 14)
        summary_layout.setSpacing(8)

        summary_title = QLabel(SUMMARY_TITLE)
        summary_title.setObjectName("SectionTitle")
        summary_layout.addWidget(summary_title)

        summary_grid = QHBoxLayout()
        summary_grid.setSpacing(18)
        self.summary_items = {}
        for key, label_text in (
            ("subject", SUMMARY_SUBJECT),
            ("date", SUMMARY_DATE),
            ("status", SUMMARY_STATUS),
            ("count", SUMMARY_COUNT),
        ):
            box = QVBoxLayout()
            box.setSpacing(4)
            label = QLabel(label_text)
            label.setObjectName("MetaLabel")
            value = QLabel("-")
            value.setObjectName("MetaValue")
            value.setWordWrap(True)
            box.addWidget(label)
            box.addWidget(value)
            summary_grid.addLayout(box, 1)
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
        self.form_layout.setSpacing(12)

        self.placeholder_card = QFrame()
        self.placeholder_card.setObjectName("PlaceholderCard")
        placeholder_layout = QVBoxLayout(self.placeholder_card)
        placeholder_layout.setContentsMargins(20, 18, 20, 18)
        placeholder_layout.setSpacing(8)
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
        bottom_layout.setContentsMargins(16, 12, 16, 12)
        bottom_layout.setSpacing(12)

        bottom_info = QVBoxLayout()
        bottom_info.setSpacing(2)
        bottom_title = QLabel(BOTTOM_TITLE)
        bottom_title.setObjectName("SectionTitle")
        bottom_info.addWidget(bottom_title)

        self.bottom_status_label = QLabel(READY_TEXT)
        self.bottom_status_label.setObjectName("BottomAccent")
        bottom_info.addWidget(self.bottom_status_label)
        bottom_layout.addLayout(bottom_info, 1)

        self.btn_submit = QPushButton(SUBMIT_BUTTON)
        self.btn_submit.setObjectName("PrimaryBtn")
        self.btn_submit.setMinimumWidth(170)
        self.btn_submit.clicked.connect(self._start_submit)
        bottom_layout.addWidget(self.btn_submit, 0, Qt.AlignRight | Qt.AlignVCenter)

        layout.addWidget(self.bottom_card)

    def _load_config(self) -> dict:
        try:
            return read_config(CONFIG_FILE)
        except Exception:
            return {}

    def _load_saved_settings(self):
        config = self._load_config()
        jielong = ((config.get("settings") or {}).get("jielong") or {})
        self.token_input.setText(str(jielong.get("authorization") or ""))
        self.thread_input.setText(str(jielong.get("thread_id") or ""))

    def _save_settings(self):
        config = self._load_config() or {}
        settings = config.setdefault("settings", {})
        jielong = settings.setdefault("jielong", {})
        jielong["authorization"] = self.token_input.text().strip()
        jielong["thread_id"] = self.thread_input.text().strip()
        save_json_file(CONFIG_FILE, config)

    def _load_location_config(self):
        config = self._load_config()
        return ((config.get("input") or {}).get("location") or {})

    def _format_location_hint(self) -> str:
        location = self._load_location_config()
        longitude = str(location.get("longitude") or "").strip()
        latitude = str(location.get("latitude") or "").strip()
        if longitude and latitude:
            return LOCATION_HINT_TEMPLATE.format(longitude=longitude, latitude=latitude)
        return LOCATION_HINT_EMPTY

    def _sync_action_state(self):
        busy = self._is_busy()
        has_bundle = bool(self._current_bundle)
        self.token_input.setEnabled(not busy)
        self.thread_input.setEnabled(not busy)
        self.btn_load.setEnabled(not busy)
        self.btn_submit.setEnabled(has_bundle and not busy)
        self.btn_load.setText(LOADING_BUTTON if self._is_loading() else LOAD_BUTTON)
        self.btn_submit.setText(SUBMITTING_BUTTON if self._is_submitting() else SUBMIT_BUTTON)

    def _set_status(self, text: str):
        self.status_label.setText(text)
        self.bottom_status_label.setText(text)

    def _is_loading(self) -> bool:
        return bool(self._load_thread and self._load_thread.isRunning())

    def _is_submitting(self) -> bool:
        return bool(self._submit_thread and self._submit_thread.isRunning())

    def _is_busy(self) -> bool:
        return self._is_loading() or self._is_submitting()

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
        self._set_status(LOAD_SUCCESS)
        self._render_summary(payload)
        self._render_fields(payload.get("fields") or [])
        self._sync_action_state()
        ToastManager.instance().show(LOAD_SUCCESS, "success")

    def _on_failed(self, message: str):
        self._current_bundle = None
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
        answers = {}
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
            kind = info["kind"]
            if kind == "select":
                option = info["widget"].currentData()
                if option:
                    answers[field_id] = {
                        "option_text": str(option.get("Text") or info["widget"].currentText()),
                        "option_value": str(option.get("Value") or info["widget"].currentText()),
                        "other_value": info["other_widget"].text().strip() if option.get("IsOtherOption") else "",
                    }
            elif kind == "textarea":
                answers[field_id] = {"value": info["widget"].toPlainText().strip()}
            elif kind in {"text", "location"}:
                answers[field_id] = {"value": info["widget"].text().strip()}
            elif kind == "media":
                answers[field_id] = {"files": info.get("files") or []}

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
            location=self._load_location_config(),
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
        date_range = f"{check_in.get('StartTime') or '-'} ~ {check_in.get('EndTime') or '-'}"
        count_value = COUNT_TEMPLATE.format(
            users=check_in.get("CheckInUserCount") or 0,
            count=check_in.get("CheckInCount") or 0,
        )

        self.summary_items["subject"].setText(str(thread.get("Subject") or "-"))
        self.summary_items["date"].setText(date_range)
        self.summary_items["status"].setText(str(status))
        self.summary_items["count"].setText(count_value)
        self.summary_card.show()

    def _render_fields(self, fields: list):
        self._clear_form()

        if not fields:
            self.placeholder_card = QFrame()
            self.placeholder_card.setObjectName("PlaceholderCard")
            placeholder_layout = QVBoxLayout(self.placeholder_card)
            placeholder_layout.setContentsMargins(20, 18, 20, 18)
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
            card_layout.setContentsMargins(14, 12, 14, 12)
            card_layout.setSpacing(10)

            head = QHBoxLayout()
            head.setSpacing(8)

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
            self.form_layout.addWidget(card)
            self._field_widgets[str(field.get("Id"))] = widget_info

            relation_id = str(field.get("RelationId") or "").strip()
            if relation_id:
                self._field_relations[relation_id] = widget_info

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
            layout.setSpacing(8)

            combo = QComboBox()
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
            layout.setSpacing(8)

            unsupported = QLabel(MEDIA_UNSUPPORTED)
            unsupported.setObjectName("HintText")
            unsupported.setWordWrap(True)
            layout.addWidget(unsupported)
            return {
                "kind": "media",
                "container": container,
                "widget": unsupported,
                "files": [],
            }

        if field.get("IsTextarea"):
            editor = QTextEdit()
            editor.setPlaceholderText(placeholder)
            editor.setPlainText(initial_value)
            editor.setFixedHeight(max(78, min(int(field.get("Rows") or 3) * 24 + 18, 160)))
            return {"kind": "textarea", "container": editor, "widget": editor}

        if field_type == 16:
            container = QWidget()
            layout = QVBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(8)
            line_edit = QLineEdit()
            line_edit.setPlaceholderText(placeholder or LOCATION_PLACEHOLDER)
            line_edit.setText(initial_value)
            layout.addWidget(line_edit)
            hint = QLabel(self._format_location_hint())
            hint.setObjectName("HintText")
            hint.setWordWrap(True)
            layout.addWidget(hint)
            return {"kind": "location", "container": container, "widget": line_edit, "hint": hint}

        line_edit = QLineEdit()
        line_edit.setPlaceholderText(placeholder)
        line_edit.setText(initial_value)
        return {"kind": "text", "container": line_edit, "widget": line_edit}

    def _on_select_changed(self, info: dict):
        option = info["widget"].currentData()
        is_other = bool(option and option.get("IsOtherOption"))
        info["other_widget"].setVisible(is_other)
        self._refresh_visibility()

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
        if self._load_thread and self._load_thread.isRunning():
            self._load_thread.requestInterruption()
            self._load_thread.wait(1000)
        if self._submit_thread and self._submit_thread.isRunning():
            self._submit_thread.requestInterruption()
            self._submit_thread.wait(1000)
        event.accept()
