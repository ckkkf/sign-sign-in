from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QTextEdit,
    QPushButton,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QSplitter,
    QWidget,
    QFrame,
    QLineEdit,
    QMessageBox,
)
from PySide6.QtWidgets import QApplication

from app.config.common import JOURNAL_SERVER_BASE, SYSTEM_PROMPT
from app.gui.components.toast import ToastManager
from app.gui.dialogs.journal_auth_dialog import JournalAuthDialog
from app.utils.files import load_journal_history, append_journal_entry
from app.utils.model_client import call_chat_model, ModelConfigurationError
from app.utils.journal_client import fetch_journals, JournalServerError


class WeeklyJournalDialog(QDialog):
    def __init__(self, model_config: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("提交周记")
        self.resize(820, 520)
        self.model_config = model_config or {}
        self.server_base = JOURNAL_SERVER_BASE
        self.auth_info = None
        self.history = {"generated": [], "submitted": []}
        self._ai_busy = False
        self._setup_styles()
        self._setup_ui()
        self._load_history()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        server_frame = QFrame()
        server_frame.setObjectName("ServerCard")
        server_layout = QHBoxLayout(server_frame)
        server_layout.setContentsMargins(18, 12, 18, 12)
        server_layout.setSpacing(12)

        self.server_status = QLabel("未登录周记服务器")
        self.server_status.setObjectName("ServerStatus")

        btn_login = QPushButton("登录 / 注册")
        btn_login.setObjectName("PrimaryBtn")
        btn_login.clicked.connect(self._prompt_login)
        btn_fetch = QPushButton("从服务器获取")
        btn_fetch.setObjectName("GhostBtn")
        btn_fetch.clicked.connect(self._fetch_from_server)

        server_layout.addWidget(self.server_status)
        server_layout.addStretch()
        server_layout.addWidget(btn_login)
        server_layout.addWidget(btn_fetch)
        layout.addWidget(server_frame)

        prompt_frame = QFrame()
        prompt_frame.setObjectName("PromptCard")
        prompt_layout = QHBoxLayout(prompt_frame)
        prompt_layout.setContentsMargins(18, 10, 18, 10)
        prompt_layout.setSpacing(12)

        self.role_input = QLineEdit()
        self.role_input.setPlaceholderText("请输入你的职业/岗位（例：前端实习生）")
        self.role_input.setObjectName("PromptInput")

        self.journal_type_input = QLineEdit()
        self.journal_type_input.setPlaceholderText("请输入周记类型或主题（例：产品研发周记）")
        self.journal_type_input.setObjectName("PromptInput")

        prompt_layout.addWidget(QLabel("职业提示"))
        prompt_layout.addWidget(self.role_input)
        prompt_layout.addSpacing(6)
        prompt_layout.addWidget(QLabel("周记类型"))
        prompt_layout.addWidget(self.journal_type_input)
        layout.addWidget(prompt_frame)

        splitter = QSplitter(Qt.Vertical)

        editor_container = QWidget()
        editor_layout = QVBoxLayout(editor_container)
        editor_layout.setContentsMargins(0, 0, 0, 0)

        self.editor = QTextEdit()
        self.editor.setPlaceholderText("在此输入或生成本周周记内容...")
        editor_layout.addWidget(self.editor)

        btn_row = QHBoxLayout()
        self.btn_ai = QPushButton("AI 自动生成")
        self.btn_ai.clicked.connect(self._generate_with_ai)
        self.btn_ai.setObjectName("PrimaryBtn")

        btn_submit = QPushButton("提交周记")
        btn_submit.setObjectName("SuccessBtn")
        btn_submit.clicked.connect(self._submit_journal)

        btn_clear = QPushButton("清空内容")
        btn_clear.setObjectName("GhostBtn")
        btn_clear.clicked.connect(self.editor.clear)

        btn_row.addWidget(self.btn_ai)
        btn_row.addWidget(btn_submit)
        btn_row.addWidget(btn_clear)
        btn_row.addStretch()
        editor_layout.addLayout(btn_row)

        splitter.addWidget(editor_container)

        history_container = QWidget()
        history_layout = QHBoxLayout(history_container)
        history_layout.setContentsMargins(0, 0, 0, 0)

        self.generated_container, self.generated_widget = self._create_history_list("历史生成（双击填充）")
        self.submitted_container, self.submitted_widget = self._create_history_list("历史提交（双击填充）")

        history_layout.addWidget(self.generated_container)
        history_layout.addWidget(self.submitted_container)

        splitter.addWidget(history_container)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        layout.addWidget(splitter)

    def _create_history_list(self, title: str):
        container = QWidget()
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(0, 0, 0, 0)
        label = QLabel(title)
        label.setStyleSheet("color:#AAA;font-weight:bold;")
        list_widget = QListWidget()
        list_widget.itemDoubleClicked.connect(self._fill_from_history)
        vbox.addWidget(label)
        vbox.addWidget(list_widget)
        return container, list_widget

    def _load_history(self):
        data = load_journal_history()
        self.history = data
        self._populate_list(self.generated_widget, data.get("generated", []))
        self._populate_list(self.submitted_widget, data.get("submitted", []))

    def _populate_list(self, widget: QListWidget, entries):
        if widget is None:
            return
        widget.clear()
        for entry in entries:
            summary = entry["content"].strip().splitlines()[0][:40] if entry["content"].strip() else "(空内容)"
            item = QListWidgetItem(f"[{entry['timestamp']}] {summary}")
            item.setData(Qt.UserRole, entry["content"])
            widget.addItem(item)

    def _generate_with_ai(self):
        prompt_context = self.editor.toPlainText().strip()
        role = self.role_input.text().strip()
        journal_type = self.journal_type_input.text().strip()

        if not self._confirm_generation(role, journal_type):
            return

        base_prompt = (
            "请扮演实习生，根据以下笔记生成不少于300字的中文周记，包含本周工作、收获与下周计划。"
            if prompt_context else
            "请随机生成一份通用的实习周记，包含工作内容、问题反思与下周目标。"
        )
        prompt = f"{base_prompt}\n\n笔记：{prompt_context}" if prompt_context else base_prompt

        extra_hints = []
        if role:
            extra_hints.append(f"职业/岗位：{role}")
        if journal_type:
            extra_hints.append(f"周记类型：{journal_type}")
        if extra_hints:
            prompt = f"{prompt}\n\n{'; '.join(extra_hints)}"

        self._set_ai_busy(True)
        self.editor.clear()

        def handle_delta(delta: str):
            cursor = self.editor.textCursor()
            cursor.movePosition(QTextCursor.End)
            cursor.insertText(delta)
            self.editor.setTextCursor(cursor)
            QApplication.processEvents()

        try:
            content = call_chat_model(self.model_config, prompt, SYSTEM_PROMPT, on_delta=handle_delta)
        except ModelConfigurationError as cfg_err:
            ToastManager.instance().show(str(cfg_err), "warning")
            self._set_ai_busy(False)
            return
        except Exception as exc:
            ToastManager.instance().show(f"调用模型失败：{exc}", "error")
            self._set_ai_busy(False)
            return

        self._set_ai_busy(False)
        if not content.strip():
            return
        append_journal_entry("generated", content)
        ToastManager.instance().show("AI 周记已生成", "success")
        self._load_history()

    def _submit_journal(self):
        content = self.editor.toPlainText().strip()
        if not content:
            ToastManager.instance().show("请先输入或生成周记内容", "info")
            return
        append_journal_entry("submitted", content)
        ToastManager.instance().show("周记已提交并记录", "success")
        self._load_history()

    def _fill_from_history(self, item: QListWidgetItem):
        content = item.data(Qt.UserRole)
        if content:
            self.editor.setPlainText(content)

    # ---------------------- Server Helpers ----------------------
    def _setup_styles(self):
        self.setStyleSheet("""
            QDialog {
                background: #111;
                color: #E6E6E6;
            }
            QLabel {
                color: #AAA;
            }
            QTextEdit {
                background: #1C1C1C;
                border: 1px solid #2F2F2F;
                border-radius: 8px;
                padding: 12px;
                font-size: 12pt;
                color: #EAEAEA;
            }
            QLineEdit#PromptInput {
                background: #1A1C24;
                border: 1px solid #2F3145;
                border-radius: 8px;
                padding: 10px;
                color: #F5F6FF;
                font-size: 10pt;
            }
            QLineEdit#PromptInput:focus {
                border-color: #5865F2;
                box-shadow: 0 0 12px rgba(88,101,242,0.35);
            }
            QListWidget {
                background: #151515;
                border: 1px solid #222;
                border-radius: 8px;
            }
            QListWidget::item {
                padding: 8px;
            }
            QListWidget::item:selected {
                background: #2E74FF;
                color: white;
            }
            #ServerCard {
                background: #1B1B1F;
                border: 1px solid #2D2D32;
                border-radius: 10px;
            }
            #PromptCard {
                background: rgba(24,27,42,0.95);
                border: 1px solid #2E3147;
                border-radius: 12px;
            }
            #ServerStatus {
                font-weight: bold;
                color: #A0A0A8;
            }
            QPushButton {
                padding: 8px 18px;
                border-radius: 18px;
                border: 1px solid transparent;
                font-weight: bold;
            }
            QPushButton#PrimaryBtn {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4E8BFF, stop:1 #7C5BFF);
                color: white;
            }
            QPushButton#PrimaryBtn:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #5C96FF, stop:1 #8A68FF);
            }
            QPushButton#GhostBtn {
                background: transparent;
                border-color: #3A3A40;
                color: #C2C2C8;
            }
            QPushButton#GhostBtn:hover {
                border-color: #777;
                color: white;
            }
            QPushButton#SuccessBtn {
                background: #2CB67D;
                color: white;
            }
            QPushButton#SuccessBtn:hover {
                background: #34C889;
            }
        """)

    def _server_base(self):
        return self.server_base

    def _prompt_login(self):
        base = self._server_base()
        if not base:
            ToastManager.instance().show("未配置周记服务器地址", "warning")
            return
        dialog = JournalAuthDialog(base, self)
        if dialog.exec() == QDialog.Accepted and dialog.auth_result:
            self.auth_info = dialog.auth_result
            self._update_server_status()

    def _update_server_status(self):
        if self.auth_info:
            user = self.auth_info.get("user", {})
            name = user.get("username") or user.get("name") or "已登录"
            self.server_status.setText(f"已登录：{name}")
            self.server_status.setStyleSheet("color:#58D68D;")
        else:
            self.server_status.setText("未登录周记服务器")
            self.server_status.setStyleSheet("color:#BBB;")

    def _ensure_login(self):
        if self.auth_info:
            return True
        self._prompt_login()
        return self.auth_info is not None

    def _fetch_from_server(self):
        base = self._server_base()
        if not base:
            ToastManager.instance().show("未配置周记服务器地址", "warning")
            return
        if not self._ensure_login():
            return
        try:
            entries = fetch_journals(base, self.auth_info['token'])
        except JournalServerError as exc:
            ToastManager.instance().show(str(exc), "warning")
            return
        except Exception as exc:
            ToastManager.instance().show(str(exc), "error")
            return
        if not entries:
            ToastManager.instance().show("服务器没有可用的周记内容", "info")
            return
        content = self._select_entry(entries)
        if not content:
            return
        self.editor.setPlainText(content)
        append_journal_entry("generated", content)
        ToastManager.instance().show("已从服务器加载周记", "success")
        self._load_history()

    def _select_entry(self, entries):
        normalized = []
        for entry in entries:
            if isinstance(entry, dict):
                content = entry.get("content") or entry.get("text") or ""
                title = entry.get("title") or entry.get("date") or entry.get("id") or "周记"
            else:
                content = str(entry)
                title = content[:20]
            if content:
                normalized.append((title, content))
        if not normalized:
            return None
        if len(normalized) == 1:
            return normalized[0][1]

        dialog = QDialog(self)
        dialog.setWindowTitle("选择周记")
        dialog.resize(420, 320)
        layout = QVBoxLayout(dialog)
        list_widget = QListWidget()
        for title, content in normalized:
            item = QListWidgetItem(title)
            item.setData(Qt.UserRole, content)
            list_widget.addItem(item)
        layout.addWidget(QLabel("请选择一条周记："))
        layout.addWidget(list_widget)
        btns = QHBoxLayout()
        btn_ok = QPushButton("确定")
        btn_cancel = QPushButton("取消")
        btn_ok.clicked.connect(dialog.accept)
        btn_cancel.clicked.connect(dialog.reject)
        btns.addStretch()
        btns.addWidget(btn_ok)
        btns.addWidget(btn_cancel)
        layout.addLayout(btns)

        list_widget.itemDoubleClicked.connect(lambda _: dialog.accept())

        if dialog.exec() == QDialog.Accepted:
            item = list_widget.currentItem()
            if item:
                return item.data(Qt.UserRole)
        return None

    def _set_ai_busy(self, busy: bool):
        if busy:
            self.btn_ai.setEnabled(False)
            self.btn_ai.setText("AI 正在生成...")
            if not self._ai_busy:
                QApplication.setOverrideCursor(Qt.WaitCursor)
            self._ai_busy = True
        else:
            self.btn_ai.setEnabled(True)
            self.btn_ai.setText("AI 自动生成")
            if self._ai_busy:
                QApplication.restoreOverrideCursor()
                self._ai_busy = False

    def _confirm_generation(self, role: str, journal_type: str) -> bool:
        summary = (
            f"职业/岗位：{role or '未填写'}\n"
            f"周记类型：{journal_type or '未填写'}\n\n"
            "请确认这些提示词信息无误，是否继续生成？"
        )
        reply = QMessageBox.question(
            self,
            "确认提示词",
            summary,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        return reply == QMessageBox.Yes

