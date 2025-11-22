from PySide6.QtCore import Qt, QThread, Signal, QTimer
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
    QComboBox,
    QGroupBox,
)
from PySide6.QtWidgets import QApplication

from app.config.common import API_URL, SYSTEM_PROMPT, CONFIG_FILE
from app.gui.components.toast import ToastManager
from app.gui.dialogs.journal_auth_dialog import JournalAuthDialog
from app.utils.files import load_journal_history, append_journal_entry, read_config, clear_session_cache
import logging
from app.utils.model_client import call_chat_model, ModelConfigurationError
from app.utils.journal_client import fetch_journals, JournalServerError
from app.apis.xybsyw import login, get_plan, load_blog_year, load_blog_date, submit_blog, handle_invalid_session

class AIGenerationThread(QThread):
    """AI生成周记的异步线程"""
    delta_signal = Signal(str)
    finished_signal = Signal(str)
    error_signal = Signal(str, str)  # error_type, message

    def __init__(self, model_config, prompt, system_prompt):
        super().__init__()
        self.model_config = model_config
        self.prompt = prompt
        self.system_prompt = system_prompt

    def run(self):
        try:
            def on_delta(delta: str):
                self.delta_signal.emit(delta)

            content = call_chat_model(
                self.model_config,
                self.prompt,
                self.system_prompt,
                on_delta=on_delta
            )
            self.finished_signal.emit(content)
        except ModelConfigurationError as e:
            self.error_signal.emit("config", str(e))
        except Exception as e:
            self.error_signal.emit("error", f"调用模型失败：{e}")


class LoadYearDataThread(QThread):
    """加载年份数据的异步线程"""
    finished_signal = Signal(dict, str, list)  # login_args, trainee_id, year_data
    error_signal = Signal(str)

    def __init__(self, config):
        super().__init__()
        self.config = config

    def run(self):
        try:
            from app.apis.xybsyw import login, get_plan, load_blog_year
            
            # 尝试使用缓存的登录信息
            try:
                login_args = login(self.config['input'], use_cache=True)
            except Exception as login_err:
                self.error_signal.emit(f"使用缓存登录失败: {login_err}")
                return
            
            # 获取traineeId
            plan_data = get_plan(userAgent=self.config['input']['userAgent'], args=login_args)
            trainee_id = None
            if plan_data and len(plan_data) > 0 and 'dateList' in plan_data[0] and len(plan_data[0]['dateList']) > 0:
                trainee_id = plan_data[0]['dateList'][0]['traineeId']
                login_args['traineeId'] = trainee_id
            
            # 加载年份数据
            year_data = load_blog_year(login_args, self.config['input'])
            
            self.finished_signal.emit(login_args, trainee_id, year_data)
        except Exception as e:
            self.error_signal.emit(str(e))


class WeeklyJournalDialog(QDialog):
    def __init__(self, model_config: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("提交周记")
        self.resize(900, 650)
        self.model_config = model_config or {}
        self.server_base = API_URL
        self.auth_info = None
        self.history = {"generated": [], "submitted": []}
        self._ai_busy = False
        self._ai_thread = None
        self._load_data_thread = None
        self.login_args = None
        self.config = None
        self.trainee_id = None
        self.year_data = None
        self.week_data = None
        self._refresh_timer = QTimer()
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self._enable_refresh_buttons)
        self._refresh_cooldown = 2000  # 2秒冷却时间
        self._refresh_buttons_enabled = True
        self._setup_styles()
        self._setup_ui()
        self._load_history()
        # 不再自动加载年月数据，提示用户手动点击按钮加载

    def closeEvent(self, event):
        """窗口关闭时清理资源"""
        if self._ai_thread and self._ai_thread.isRunning():
            self._ai_thread.requestInterruption()
            self._ai_thread.wait(1000)  # 等待最多1秒
        if self._load_data_thread and self._load_data_thread.isRunning():
            self._load_data_thread.requestInterruption()
            self._load_data_thread.wait(1000)  # 等待最多1秒
        event.accept()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        # 周记配置区域
        config_frame = QFrame()
        config_frame.setObjectName("ConfigCard")
        config_layout = QVBoxLayout(config_frame)
        config_layout.setContentsMargins(12, 8, 12, 8)
        config_layout.setSpacing(8)

        config_row1 = QHBoxLayout()
        config_row1.setSpacing(8)
        
        # 添加加载年月按钮
        btn_load_data = QPushButton("加载年月")
        btn_load_data.setObjectName("LoadDataBtn")
        btn_load_data.setToolTip("点击加载可用的年份和月份")
        btn_load_data.clicked.connect(self._load_year_month_data)
        config_row1.addWidget(btn_load_data)
        self.btn_load_data = btn_load_data
        
        config_row1.addWidget(QLabel("绑定年份:"))
        self.year_combo = QComboBox()
        self.year_combo.setObjectName("ConfigCombo")
        self.year_combo.currentIndexChanged.connect(self._on_year_changed)
        config_row1.addWidget(self.year_combo)
        
        config_row1.addSpacing(3)
        config_row1.addWidget(QLabel("月份:"))
        self.month_combo = QComboBox()
        self.month_combo.setObjectName("ConfigCombo")
        self.month_combo.currentIndexChanged.connect(self._on_month_changed)
        config_row1.addWidget(self.month_combo)
        
        config_row1.addSpacing(3)
        config_row1.addWidget(QLabel("周:"))
        self.week_combo = QComboBox()
        self.week_combo.setObjectName("WeekCombo")
        config_row1.addWidget(self.week_combo)
        
        config_row1.setSpacing(3)
        config_row1.addWidget(QLabel("查看权限:"))
        self.permission_combo = QComboBox()
        self.permission_combo.setObjectName("ConfigCombo")
        self.permission_combo.addItem("仅老师和同学可见", 0)
        self.permission_combo.addItem("全网可见", 1)
        self.permission_combo.addItem("仅老师可见", 2)
        self.permission_combo.setCurrentIndex(2)  # 默认仅老师可见
        config_row1.addWidget(self.permission_combo)

        config_row1.addStretch()
        config_layout.addLayout(config_row1)


        layout.addWidget(config_frame)

        splitter = QSplitter(Qt.Vertical)

        editor_container = QWidget()
        editor_layout = QVBoxLayout(editor_container)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(6)

        # 周记标题
        title_label = QLabel("周记标题:")
        title_label.setStyleSheet("color: #AAA; font-weight: bold;")
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("请输入周记标题（必填）")
        self.title_input.setObjectName("TitleInput")
        editor_layout.addWidget(title_label)
        editor_layout.addWidget(self.title_input)

        # 周记内容
        self.editor = QTextEdit()
        self.editor.setPlaceholderText("在此输入或生成本周周记内容...")
        editor_layout.addWidget(self.editor)

        # 职业提示（移到编辑区域下面）
        role_frame = QFrame()
        role_frame.setObjectName("RoleCard")
        role_layout = QHBoxLayout(role_frame)
        role_layout.setContentsMargins(8, 6, 8, 6)
        role_layout.setSpacing(8)
        role_layout.addWidget(QLabel("AI提示词:"))
        self.role_input = QLineEdit()
        self.role_input.setPlaceholderText("请描述你的实习职业/岗位（例：前端实习生）")
        self.role_input.setObjectName("PromptInput")
        role_layout.addWidget(self.role_input)
        editor_layout.addWidget(role_frame)

        # 按钮行：包含登录状态、从服务器获取、AI生成、提交、清空
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        
        self.server_status = QLabel("未登录周记服务器")
        self.server_status.setObjectName("ServerStatus")
        self.server_status.setStyleSheet("color: #AAA; font-size: 9pt; padding: 0 8px; cursor: pointer;")
        self.server_status.mousePressEvent = self._on_server_status_clicked
        
        btn_fetch = QPushButton("从服务器获取")
        btn_fetch.setObjectName("FetchBtn")
        btn_fetch.clicked.connect(self._fetch_from_server)
        
        # AI按钮移到最左侧
        self.btn_ai = QPushButton("AI 自动生成")
        self.btn_ai.clicked.connect(self._generate_with_ai)
        self.btn_ai.setObjectName("PrimaryBtn")

        btn_submit = QPushButton("提交周记")
        btn_submit.setObjectName("SuccessBtn")
        btn_submit.clicked.connect(self._submit_journal)

        btn_clear = QPushButton("清空")
        btn_clear.setObjectName("GhostBtn")
        btn_clear.clicked.connect(self._clear_all)

        btn_row.addWidget(self.btn_ai)
        btn_row.addStretch()
        btn_row.addWidget(self.server_status)
        btn_row.addWidget(btn_fetch)
        btn_row.addWidget(btn_submit)
        btn_row.addWidget(btn_clear)
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
        splitter.setStretchFactor(0, 5)  # 增大编辑区域比例
        splitter.setStretchFactor(1, 2)

        layout.addWidget(splitter)

    def _clear_all(self):
        """清空标题和内容"""
        self.title_input.clear()
        self.editor.clear()

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
        if self._ai_busy:
            return

        prompt_context = self.editor.toPlainText().strip()
        role = self.role_input.text().strip()

        if not self._confirm_generation(role):
            return

        base_prompt = (
            "请扮演实习生，根据以下笔记生成不少于300字的中文周记，包含本周工作、收获与下周计划。"
            if prompt_context else
            "请随机生成一份通用的实习周记，包含工作内容、问题反思与下周目标。"
        )
        prompt = f"{base_prompt}\n\n笔记：{prompt_context}" if prompt_context else base_prompt

        if role:
            prompt = f"{prompt}\n\n职业/岗位：{role}"

        self._set_ai_busy(True)
        self.editor.clear()

        # 创建并启动异步线程
        self._ai_thread = AIGenerationThread(self.model_config, prompt, SYSTEM_PROMPT)
        self._ai_thread.delta_signal.connect(self._on_ai_delta)
        self._ai_thread.finished_signal.connect(self._on_ai_finished)
        self._ai_thread.error_signal.connect(self._on_ai_error)
        self._ai_thread.start()

    def _on_ai_delta(self, delta: str):
        """处理AI生成的增量内容"""
        cursor = self.editor.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(delta)
        self.editor.setTextCursor(cursor)

    def _on_ai_finished(self, content: str):
        """AI生成完成"""
        self._set_ai_busy(False)
        if not content.strip():
            return
        append_journal_entry("generated", content)
        ToastManager.instance().show("AI 周记已生成", "success")
        self._load_history()
        self._ai_thread = None

    def _on_ai_error(self, error_type: str, message: str):
        """AI生成出错"""
        self._set_ai_busy(False)
        toast_type = "warning" if error_type == "config" else "error"
        ToastManager.instance().show(message, toast_type)
        self._ai_thread = None

    def _load_year_month_data(self):
        """加载年月数据（用户手动触发）"""
        try:
            if not self.config:
                self.config = read_config(CONFIG_FILE)
            # 在子线程中加载数据，避免阻塞UI
            self._load_data_thread = LoadYearDataThread(self.config)
            self._load_data_thread.finished_signal.connect(self._on_year_data_loaded)
            self._load_data_thread.error_signal.connect(self._on_year_data_error)
            self._load_data_thread.start()
            self.btn_load_data.setEnabled(False)
            self.btn_load_data.setText("加载中...")
        except Exception as e:
            logging.error(f"加载年月数据失败: {e}")
            ToastManager.instance().show(f"加载失败: {str(e)}", "warning")

    def _on_year_data_loaded(self, login_args, trainee_id, year_data):
        """年份数据加载完成"""
        self.login_args = login_args
        self.trainee_id = trainee_id
        self.year_data = year_data
        # 更新UI
        self.year_combo.clear()
        for year_item in self.year_data:
            year_name = year_item.get('name', '')
            self.year_combo.addItem(year_name, year_item)
        if self.year_combo.count() > 0:
            self.year_combo.setCurrentIndex(0)
            self._on_year_changed()
        self.btn_load_data.setEnabled(True)
        self.btn_load_data.setText("加载年月")
        ToastManager.instance().show("年月数据加载成功", "success")

    def _on_year_data_error(self, error_msg):
        """年份数据加载失败"""
        logging.error(f"加载年份数据失败: {error_msg}")
        self.btn_load_data.setEnabled(True)
        self.btn_load_data.setText("加载年月")
        if "缓存登录失败" in error_msg or "过期" in error_msg or "失效" in error_msg:
            ToastManager.instance().show("登录信息已过期，请先执行签到操作以获取新的登录信息", "warning")
        else:
            ToastManager.instance().show(f"加载失败: {error_msg}", "warning")

    def _load_year_data(self):
        """加载年份和月份数据"""
        try:
            if not self.login_args or not self.trainee_id:
                return
            self.year_data = load_blog_year(self.login_args, self.config['input'])
            self.year_combo.clear()
            for year_item in self.year_data:
                year_name = year_item.get('name', '')
                self.year_combo.addItem(year_name, year_item)
            if self.year_combo.count() > 0:
                self.year_combo.setCurrentIndex(0)
                self._on_year_changed()
        except Exception as e:
            logging.error(f"加载年份数据失败: {e}")
            ToastManager.instance().show(f"加载年份失败: {str(e)}", "warning")

    def _enable_refresh_buttons(self):
        """启用刷新按钮"""
        self._refresh_buttons_enabled = True
        if hasattr(self, 'btn_refresh_year'):
            self.btn_refresh_year.setEnabled(True)
        if hasattr(self, 'btn_refresh_week'):
            self.btn_refresh_week.setEnabled(True)

    def _refresh_year_data(self):
        """刷新年份数据（带频率限制）"""
        if not self._refresh_buttons_enabled:
            return
        self._refresh_buttons_enabled = False
        if hasattr(self, 'btn_refresh_year'):
            self.btn_refresh_year.setEnabled(False)
        self._load_year_data()
        self._refresh_timer.start(self._refresh_cooldown)

    def _refresh_week_data(self):
        """刷新周数据（带频率限制）"""
        if not self._refresh_buttons_enabled:
            return
        self._refresh_buttons_enabled = False
        if hasattr(self, 'btn_refresh_week'):
            self.btn_refresh_week.setEnabled(False)
        self._on_month_changed()
        self._refresh_timer.start(self._refresh_cooldown)

    def _on_year_changed(self):
        """年份改变时更新月份"""
        try:
            year_item = self.year_combo.currentData()
            if not year_item:
                return
            months = year_item.get('months', [])
            self.month_combo.clear()
            for month_item in months:
                month_name = month_item.get('name', '')
                self.month_combo.addItem(month_name, month_item)
            if self.month_combo.count() > 0:
                self.month_combo.setCurrentIndex(0)
                self._on_month_changed()
        except Exception as e:
            logging.error(f"更新月份失败: {e}")

    def _on_month_changed(self):
        """月份改变时更新周信息"""
        try:
            year_item = self.year_combo.currentData()
            month_item = self.month_combo.currentData()
            if not year_item or not month_item:
                return
            year_id = year_item.get('id')
            month_id = month_item.get('id')
            if not year_id or not month_id:
                return
            self.week_data = load_blog_date(self.login_args, self.config['input'], year_id, month_id)
            self.week_combo.clear()
            for week_item in self.week_data:
                week_num = week_item.get('week', 0)
                start_date = week_item.get('startDate', '')
                end_date = week_item.get('endDate', '')
                blog_count = week_item.get('blogCount', 0)
                status = week_item.get('status', 2)
                # status: 1-已提交，2-未提交
                status_text = "已提交" if status == 1 else "未提交"
                week_text = f"第{week_num}周 ({start_date} ~ {end_date}) - {status_text} ({blog_count}篇)"
                self.week_combo.addItem(week_text, week_item)
        except Exception as e:
            logging.error(f"更新周信息失败: {e}")
            ToastManager.instance().show(f"加载周信息失败: {str(e)}", "warning")

    def _check_jsessionid_validity(self):
        """检查jsessionid是否有效"""
        try:
            if not self.config:
                self.config = read_config(CONFIG_FILE)
            # 尝试使用缓存的登录信息
            try:
                login_args = login(self.config['input'], use_cache=True)
            except Exception:
                return False
            # 尝试获取计划来验证session
            get_plan(userAgent=self.config['input']['userAgent'], args=login_args)
            return True
        except Exception as e:
            logging.error(f"检查jsessionid有效性失败: {e}")
            return False

    def _submit_journal(self):
        """提交周记到xybsyw"""
        # 先检查jsessionid是否有效
        if not self._check_jsessionid_validity():
            handle_invalid_session()
            ToastManager.instance().show("JSESSIONID已失效，请先执行签到操作以获取新的登录信息", "warning")
            return
        
        # 检查标题
        title = self.title_input.text().strip()
        if not title:
            ToastManager.instance().show("请输入周记标题", "warning")
            self.title_input.setFocus()
            return
        
        content = self.editor.toPlainText().strip()
        if not content:
            ToastManager.instance().show("请先输入或生成周记内容", "info")
            return

        # 检查是否选择了周
        week_item = self.week_combo.currentData()
        if not week_item:
            ToastManager.instance().show("请选择要绑定的周", "warning")
            return

        # 检查登录信息
        if not self.login_args or not self.trainee_id:
            ToastManager.instance().show("登录信息无效，请先执行签到操作以获取登录信息", "warning")
            return

        try:
            # 获取选中的周信息
            start_date = week_item.get('startDate', '')
            end_date = week_item.get('endDate', '')
            blog_open_type = self.permission_combo.currentData()
            
            # 提交周记
            try:
                blog_id = submit_blog(
                    args=self.login_args,
                    config=self.config['input'],
                    blog_title=title,
                    blog_body=content,
                    start_date=start_date,
                    end_date=end_date,
                    blog_open_type=blog_open_type,
                    trainee_id=self.trainee_id
                )
                
                append_journal_entry("submitted", content)
                ToastManager.instance().show(f"周记提交成功！ID: {blog_id}", "success")
                self._load_history()
                # 刷新周信息
                self._on_month_changed()
            except RuntimeError as submit_err:
                error_msg = str(submit_err)
                # 如果是因为session过期，提示用户重新获取code
                if "403" in error_msg or "登录" in error_msg or "session" in error_msg.lower():
                    ToastManager.instance().show("登录信息已过期，请先执行签到操作以获取新的登录信息", "warning")
                    # 清除缓存
                    from app.utils.files import clear_session_cache
                    clear_session_cache()
                    self.login_args = None
                    self.trainee_id = None
                else:
                    raise
        except Exception as e:
            logging.error(f"提交周记失败: {e}")
            ToastManager.instance().show(f"提交周记失败: {str(e)}", "error")

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
            #ConfigCard {
                background: rgba(24,27,42,0.95);
                border: 1px solid #2E3147;
                border-radius: 12px;
            }
            QComboBox#ConfigCombo {
                background: #1A1C24;
                border: 1px solid #2F3145;
                border-radius: 5px;
                padding: 3px 0;
                color: #F5F6FF;
                font-size: 10pt;
                min-width: 10px;
            }
            QComboBox#ConfigCombo:hover {
                border-color: #5865F2;
            }
            QComboBox#ConfigCombo::drop-down {
                border: none;
                width: 20px;
            }
            
            QComboBox#WeekCombo {
                background: #1A1C24;
                border: 1px solid #2F3145;
                border-radius: 5px;
                padding: 3px;
                color: #F5F6FF;
                font-size: 10pt;
                min-width: 300px;
            }
            QComboBox#WeekCombo:hover {
                border-color: #5865F2;
            }
            QComboBox#WeekCombo::drop-down {
                border: none;
                width: 20px;
            }
            
            QComboBox#ConfigCombo QAbstractItemView {
                background: #1A1C24;
                border: 1px solid #2F3145;
                selection-background-color: #5865F2;
                color: #F5F6FF;
                padding: 2px;
            }
            QComboBox#ConfigCombo QAbstractItemView::item {
                padding: 8px 12px;
                border-radius: 4px;
                min-height: 24px;
            }
            QComboBox#ConfigCombo QAbstractItemView::item:selected {
                background-color: #5865F2;
                color: #FFFFFF;
            }
            QComboBox#ConfigCombo QAbstractItemView::item:hover:!selected {
                background-color: #3A3F5F;
                color: #F5F6FF;
            }
            QPushButton#LoginBtn {
                background: #4CAF50;
                color: white;
                border: none;
                border-radius: 18px;
                padding: 8px 18px;
                font-weight: bold;
            }
            QPushButton#LoginBtn:hover {
                background: #45a049;
            }
            QPushButton#FetchBtn {
                background: #2196F3;
                color: white;
                border: none;
                border-radius: 18px;
                padding: 8px 18px;
                font-weight: bold;
            }
            QPushButton#FetchBtn:hover {
                background: #0b7dda;
            }
            QPushButton#SmallBtn {
                background: #2A2D3A;
                border: 1px solid #3A3F5F;
                border-radius: 6px;
                padding: 4px 8px;
                color: #C2C2C8;
                font-size: 10pt;
                min-width: 28px;
                max-width: 28px;
            }
            QPushButton#SmallBtn:hover {
                background: #3A3F5F;
                border-color: #5865F2;
                color: #FFFFFF;
            }
            QPushButton#LoadDataBtn {
                background: #4E8BFF;
                color: white;
                border: none;
                border-radius: 18px;
                padding: 8px 18px;
                font-weight: bold;
            }
            QPushButton#LoadDataBtn:hover {
                background: #5C96FF;
            }
            QPushButton#LoadDataBtn:disabled {
                background: #353B5A;
                color: #7B80A3;
            }
            #RoleCard {
                background: rgba(24,27,42,0.95);
                border: 1px solid #2E3147;
                border-radius: 12px;
            }
            QLineEdit#TitleInput {
                background: #1C1C1C;
                border: 1px solid #2F2F2F;
                border-radius: 8px;
                padding: 10px;
                color: #EAEAEA;
                font-size: 11pt;
            }
            QLineEdit#TitleInput:focus {
                border-color: #5865F2;
                box-shadow: 0 0 8px rgba(88,101,242,0.3);
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
            self.server_status.setStyleSheet("color:#58D68D; font-size: 9pt; padding: 0 8px; cursor: pointer; text-decoration: underline;")
        else:
            self.server_status.setText("未登录周记服务器")
            self.server_status.setStyleSheet("color:#AAA; font-size: 9pt; padding: 0 8px; cursor: pointer;")
    
    def _on_server_status_clicked(self, event):
        """点击服务器状态标签时的处理"""
        if self.auth_info:
            self._open_user_center()
        else:
            self._prompt_login()
    
    def _open_user_center(self):
        """打开用户中心页面"""
        if not self.auth_info:
            return
        from app.gui.dialogs.user_center_dialog import UserCenterDialog
        dialog = UserCenterDialog(self.auth_info, self.server_base, self)
        if dialog.exec() == QDialog.Accepted:
            # 如果用户登出了，更新状态
            if dialog.logged_out:
                self.auth_info = None
                self._update_server_status()

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
        # 检查是否登录，如果没有登录则弹出登录/注册页面
        if not self.auth_info:
            self._prompt_login()
            if not self.auth_info:
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

    def _confirm_generation(self, role: str) -> bool:
        summary = (
            f"职业/岗位：{role or '未填写'}\n\n"
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

