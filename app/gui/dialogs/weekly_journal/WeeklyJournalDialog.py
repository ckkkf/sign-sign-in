import logging
import traceback

from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QTextEdit, QPushButton, QHBoxLayout, QLabel, QFrame, QScrollArea,
                               QWidget, QMessageBox, QApplication, QListWidgetItem, QLineEdit, QListWidget, QSplitter,
                               QSizePolicy, QComboBox, QTextBrowser, )

from app.apis.xybsyw import handle_invalid_session, get_plan, login, load_blog_date, load_blog_year, submit_blog
from app.config.common import CONFIG_FILE, PROJECT_NAME, SYSTEM_PROMPT
from app.gui.components.no_wheel_combo import NoWheelComboBox
from app.gui.components.toast import ToastManager
from app.gui.dialogs.journal_auth_dialog import JournalAuthDialog
from app.gui.dialogs.weekly_journal.AIGenerationThread import AIGenerationThread
from app.gui.dialogs.weekly_journal.AIMessageBubble import AIMessageBubble
from app.gui.dialogs.weekly_journal.CustomConfirmDialog import CustomConfirmDialog
from app.gui.dialogs.weekly_journal.FloatingActionBar import FloatingActionBar
from app.gui.dialogs.weekly_journal.LoadYearDataThread import LoadYearDataThread
from app.gui.dialogs.weekly_journal.SubmitJournalThread import SubmitJournalThread
from app.gui.dialogs.weekly_journal.UserMessageBubble import UserMessageBubble
from app.gui.dialogs.weekly_journal.LoadBlogListThread import LoadBlogListThread
from app.gui.dialogs.weekly_journal.LoadWeekDataThread import LoadWeekDataThread
from app.utils.files import read_config, append_journal_entry, load_journal_history, clear_journal_history


class WeeklyJournalDialog(QDialog):
    def __init__(self, model_config: dict, args, parent=None):
        try:
            with open("debug_crash.txt", "a", encoding="utf-8") as f: f.write("STEP 1: Entering WeeklyJournalDialog.__init__\n")
            
            # 设置 parent 为 None 以确保在任务栏显示独立图标
            super().__init__(None)
            with open("debug_crash.txt", "a", encoding="utf-8") as f: f.write("STEP 2: super().__init__ done\n")
            
            self.setWindowTitle("周记提交")
            # 添加最小化和最大化按钮，以及 Window 标志确保任务栏显示
            self.setWindowFlags(
                self.windowFlags() | Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
            
            with open("debug_crash.txt", "a", encoding="utf-8") as f: f.write("STEP 3: Window flags set\n")

            # 自适应屏幕大小
            self._setup_window_geometry()
            with open("debug_crash.txt", "a", encoding="utf-8") as f: f.write("STEP 4: Geometry set\n")

            self.model_config = model_config or {}
            self.history = {"generated": [], "submitted": []}
            self._ai_busy = False
            self._ai_thread = None
            self._load_data_thread = None
            self.args = args
            self.config = None
            self.trainee_id = None
            self.year_data = None
            self.week_data = None
            self.current_months = [] # 存储当前选中的月份列表
            self._refresh_timer = QTimer()
            self._refresh_timer.setSingleShot(True)
            self._refresh_timer.timeout.connect(self._enable_refresh_buttons)
            self._refresh_cooldown = 2000  # 2秒冷却时间
            self._refresh_buttons_enabled = True
            self.current_page = 1
            self.total_pages = 1
            self.current_page = 1
            self.total_pages = 1
            self._load_blog_list_thread = None
            self._load_week_data_thread = None
            self._is_loading_week_data = False
            self._is_loading_year_data = False
            self._is_loading_blog_list = False
            self._blog_list_request_id = 0
            self._current_year_month_key = None
            self._last_loaded_year_month_key = None
            
            self._setup_styles()
            self._setup_ui()
            with open("debug_crash.txt", "a", encoding="utf-8") as f: f.write("STEP 7: UI setup done\n")
            
            self._load_history()
            with open("debug_crash.txt", "a", encoding="utf-8") as f: f.write("STEP 8: History loaded\n")
            
            # 初始化编辑器高度
            QTimer.singleShot(0, self._adjust_editor_height)
            # 自动加载年月数据
            QTimer.singleShot(100, self._load_year_month_data)
            
            with open("debug_crash.txt", "a", encoding="utf-8") as f: f.write("STEP 9: Init finished completely\n")
            
        except Exception as e:
            err_msg = traceback.format_exc()
            with open("debug_crash.txt", "a", encoding="utf-8") as f: f.write(f"CRASH IN INIT: {e}\n{err_msg}\n")
            raise e

    def _setup_window_geometry(self):
        """设置窗口尺寸，自适应屏幕大小"""
        screen = QApplication.primaryScreen()
        if screen:
            screen_geometry = screen.availableGeometry()
            screen_width = screen_geometry.width()
            screen_height = screen_geometry.height()

            # 窗口占屏幕的 85%，但有最大最小限制
            window_width = min(max(int(screen_width * 0.85), 900), 1400)
            window_height = min(max(int(screen_height * 0.85), 650), 900)

            self.resize(window_width, window_height)

            # 居中显示
            x = (screen_width - window_width) // 2 + screen_geometry.x()
            y = (screen_height - window_height) // 2 + screen_geometry.y()
            self.move(x, y)
        else:
            self.resize(1100, 750)

    def closeEvent(self, event):
        """窗口关闭时清理资源"""
        if self._ai_thread and self._ai_thread.isRunning():
            self._ai_thread.requestInterruption()
            self._ai_thread.wait(1000)  # 等待最多1秒
        if self._load_data_thread and self._load_data_thread.isRunning():
            self._load_data_thread.requestInterruption()
            self._load_data_thread.wait(1000)  # 等待最多1秒
        if self._load_week_data_thread and self._load_week_data_thread.isRunning():
            self._load_week_data_thread.requestInterruption()
            self._load_week_data_thread.wait(1000)
        if self._load_blog_list_thread and self._load_blog_list_thread.isRunning():
            self._load_blog_list_thread.requestInterruption()
            self._load_blog_list_thread.wait(1000)
        event.accept()

    def _setup_ui(self):
        # 主布局 - DeepSeek 风格：左侧边栏 + 右侧主内容区
        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # ========== 左侧边栏 ==========
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setMinimumWidth(200)
        sidebar.setMaximumWidth(400)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(16, 20, 16, 20)
        sidebar_layout.setSpacing(16)

        # 侧边栏标题
        sidebar_title = QLabel(PROJECT_NAME)
        sidebar_title.setObjectName("SidebarTitle")
        sidebar_layout.addWidget(sidebar_title)

        # AI 生成记录标题和清空按钮
        gen_header = QWidget()
        gen_header_layout = QHBoxLayout(gen_header)
        gen_header_layout.setContentsMargins(0, 0, 0, 0)

        generated_label = QLabel("⏱️ 生成历史")
        generated_label.setObjectName("SidebarLabel")
        gen_header_layout.addWidget(generated_label)

        gen_header_layout.addStretch()

        self.btn_clear_history = QPushButton("清空")
        self.btn_clear_history.setToolTip("清空历史")
        self.btn_clear_history.setFixedSize(32, 20)
        self.btn_clear_history.setCursor(Qt.PointingHandCursor)
        self.btn_clear_history.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #6B7280;
                border: none;
                font-size: 11px;
                padding: 0;
            }
            QPushButton:hover {
                color: #EF4444;
            }
        """)
        self.btn_clear_history.clicked.connect(self._clear_generated_history)
        gen_header_layout.addWidget(self.btn_clear_history)

        sidebar_layout.addWidget(gen_header)

        self.generated_widget = QListWidget()
        self.generated_widget.setObjectName("HistoryList")
        self.generated_widget.itemDoubleClicked.connect(self._fill_from_history)
        self.generated_widget.setMaximumHeight(200)
        sidebar_layout.addWidget(self.generated_widget)

        # 已提交记录
        submitted_label = QLabel("✅ 已提交")
        submitted_label.setObjectName("SidebarLabel")
        sidebar_layout.addWidget(submitted_label)

        self.submitted_widget = QListWidget()
        self.submitted_widget.setObjectName("HistoryList")
        self.submitted_widget.itemDoubleClicked.connect(self._open_blog_detail)
        sidebar_layout.addWidget(self.submitted_widget)

        # 分页控件
        pagination_layout = QHBoxLayout()
        pagination_layout.setContentsMargins(0, 0, 0, 0)
        
        self.btn_prev = QPushButton("◀")
        self.btn_prev.setFixedSize(24, 24)
        self.btn_prev.setCursor(Qt.PointingHandCursor)
        self.btn_prev.clicked.connect(self._prev_page)
        self.btn_prev.setStyleSheet("""
            QPushButton { background: transparent; color: #6B7280; border: 1px solid #2D313E; border-radius: 4px; }
            QPushButton:hover { border-color: #4A90D9; color: #E8EAED; }
            QPushButton:disabled { color: #2D313E; border-color: #1F2233; }
        """)
        
        self.lbl_page = QLabel("1/1")
        self.lbl_page.setAlignment(Qt.AlignCenter)
        self.lbl_page.setStyleSheet("color: #6B7280; font-size: 11px;")
        
        self.btn_next = QPushButton("▶")
        self.btn_next.setFixedSize(24, 24)
        self.btn_next.setCursor(Qt.PointingHandCursor)
        self.btn_next.clicked.connect(self._next_page)
        self.btn_next.setStyleSheet(self.btn_prev.styleSheet())

        pagination_layout.addWidget(self.btn_prev)
        pagination_layout.addWidget(self.lbl_page)
        pagination_layout.addWidget(self.btn_next)
        
        sidebar_layout.addLayout(pagination_layout)

        # 兼容旧代码
        self.generated_container = self.generated_widget
        self.submitted_container = self.submitted_widget

        sidebar_layout.addStretch()

        sidebar_layout.addStretch()

        # main_layout.addWidget(sidebar) 已移除，改为添加到 Splitter

        # ========== 右侧主内容区 ==========
        content_area = QFrame()
        content_area.setObjectName("ContentArea")
        content_layout = QVBoxLayout(content_area)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setObjectName("MainScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setFrameShape(QFrame.NoFrame)

        # 中央内容容器
        central_widget = QWidget()
        central_widget.setObjectName("CentralWidget")
        central_layout = QVBoxLayout(central_widget)
        central_layout.setSpacing(0)
        central_layout.setContentsMargins(60, 40, 60, 30)

        # ========== 顶部弹性空间（对话开始后隐藏）==========
        self._top_spacer = QWidget()
        self._top_spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        central_layout.addWidget(self._top_spacer, 1)

        # ========== 主标题（对话开始后隐藏）==========
        self._title_container = QWidget()
        self._title_container.setObjectName("TitleContainer")
        title_layout = QVBoxLayout(self._title_container)
        title_layout.setContentsMargins(0, 0, 0, 40)
        title_layout.setSpacing(0)
        title_layout.setAlignment(Qt.AlignCenter)

        main_title = QLabel("✨ 今天有什么可以帮到你？")
        main_title.setObjectName("MainTitle")
        main_title.setAlignment(Qt.AlignCenter)
        title_layout.addWidget(main_title)

        central_layout.addWidget(self._title_container)

        # ========== 聊天消息显示区域 ==========
        self.chat_container = QFrame()
        self.chat_container.setObjectName("ChatContainer")
        self.chat_container.setMinimumWidth(750)
        self.chat_container.setMaximumWidth(900)
        chat_layout = QVBoxLayout(self.chat_container)
        chat_layout.setContentsMargins(0, 0, 0, 0)
        chat_layout.setSpacing(12)

        # 聊天消息滚动区域
        self.chat_scroll = QScrollArea()
        self.chat_scroll.setObjectName("ChatScrollArea")
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.chat_scroll.setFrameShape(QFrame.NoFrame)

        # 聊天消息容器
        self.chat_messages = QWidget()
        self.chat_messages.setObjectName("ChatMessages")
        self.chat_messages_layout = QVBoxLayout(self.chat_messages)
        self.chat_messages_layout.setContentsMargins(20, 20, 20, 20)
        self.chat_messages_layout.setSpacing(20)
        self.chat_messages_layout.addStretch()

        self.chat_scroll.setWidget(self.chat_messages)
        chat_layout.addWidget(self.chat_scroll)

        # 居中显示聊天区域（初始隐藏）
        self._chat_area_widget = QWidget()
        chat_wrapper = QHBoxLayout(self._chat_area_widget)
        chat_wrapper.setContentsMargins(0, 0, 0, 0)
        chat_wrapper.addStretch()
        chat_wrapper.addWidget(self.chat_container)
        chat_wrapper.addStretch()

        self._chat_area_widget.setVisible(False)
        central_layout.addWidget(self._chat_area_widget, 1)  # stretch factor 1

        # ========== 底部输入区域容器 ==========
        input_container = QFrame()
        input_container.setObjectName("InputContainer")
        input_container.setMinimumWidth(750)
        input_container.setMaximumWidth(900)
        input_container_layout = QVBoxLayout(input_container)
        input_container_layout.setContentsMargins(12, 10, 12, 8)
        input_container_layout.setSpacing(0)

        # 保存引用以便后续操作
        self._input_container = input_container

        # 隐藏的标题输入（兼容旧代码，自动生成标题）
        self.title_input = QLineEdit()
        self.title_input.setVisible(False)

        # 隐藏的加载按钮引用（兼容旧代码）
        self.btn_load_data = QPushButton("加载数据")

        # 单一主输入框（自动调整高度）
        self.editor = QTextEdit()
        self.editor.setPlaceholderText("发送消息...")
        self.editor.setObjectName("MainEditor")
        self._editor_min_height = 40
        self._editor_max_height = 150
        self.editor.setMinimumHeight(self._editor_min_height)
        self.editor.setMaximumHeight(self._editor_min_height)  # 初始为最小高度
        self.editor.textChanged.connect(self._adjust_editor_height)
        # 安装事件过滤器以捕获 Enter 键
        self.editor.installEventFilter(self)
        input_container_layout.addWidget(self.editor)

        # 隐藏的 AI 提示词输入（兼容旧代码）
        self.role_input = QLineEdit()
        self.role_input.setVisible(False)

        # 隐藏的配置选项（兼容旧代码）
        self.year_combo = NoWheelComboBox()
        self.year_combo.setVisible(False)
        self.year_combo.currentIndexChanged.connect(self._on_year_changed)
        self.year_combo.activated.connect(self._stop_auto_finding)
        
        self.month_combo = NoWheelComboBox()
        self.month_combo.setPlaceholderText("选择月份")
        self.month_combo.currentIndexChanged.connect(self._on_month_changed)
        self.month_combo.activated.connect(self._stop_auto_finding)

        self.week_combo = NoWheelComboBox()
        self.week_combo.setVisible(False)

        self.permission_combo = NoWheelComboBox()
        self.permission_combo.setVisible(False)
        self.permission_combo.addItem("仅老师可见", 2)
        self.permission_combo.addItem("仅老师和同学可见", 0)
        self.permission_combo.addItem("全网可见", 1)
        self.permission_combo.setCurrentIndex(0)

        # 底部工具栏（只有 AI 生成按钮）
        toolbar_row = QHBoxLayout()
        toolbar_row.setSpacing(8)
        toolbar_row.setContentsMargins(0, 0, 0, 0)

        # 清空对话按钮
        self.btn_clear = QPushButton("🗑️ 清空对话")
        self.btn_clear.setObjectName("ToolbarBtn")
        self.btn_clear.setCursor(Qt.PointingHandCursor)
        self.btn_clear.clicked.connect(self._clear_chat_session)
        toolbar_row.addWidget(self.btn_clear)

        toolbar_row.addStretch()

        # AI 生成按钮
        self.btn_ai = QPushButton("🔺发送")
        self.btn_ai.clicked.connect(self._generate_with_ai)
        self.btn_ai.setObjectName("AIBtn")
        self.btn_ai.setCursor(Qt.PointingHandCursor)
        toolbar_row.addWidget(self.btn_ai)

        input_container_layout.addLayout(toolbar_row)

        # 居中显示输入容器
        input_wrapper = QHBoxLayout()
        input_wrapper.addStretch()
        input_wrapper.addWidget(input_container)
        input_wrapper.addStretch()
        central_layout.addLayout(input_wrapper)

        # ========== 底部弹性空间（对话开始后隐藏）==========
        self._bottom_spacer = QWidget()
        self._bottom_spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        central_layout.addWidget(self._bottom_spacer, 2)

        # 设置滚动区域内容
        scroll_area.setWidget(central_widget)
        content_layout.addWidget(scroll_area)

        # ========== 主布局 ==========
        # main_layout 已在函数开头定义
        # main_layout.setContentsMargins(0, 0, 0, 0)
        # main_layout.setSpacing(0)

        # 创建浮动工具栏
        self.floating_bar = FloatingActionBar(self, self._copy_text_to_clipboard, self.submit_journal_from_text)

        # 使用 Splitter 实现可拖动侧边栏
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setHandleWidth(1)  # 细线
        self.splitter.setStyleSheet("QSplitter::handle { background-color: #2D313E; }")

        # 添加侧边栏和内容区域到 Splitter
        self.splitter.addWidget(sidebar)
        self.splitter.addWidget(content_area)

        # 设置伸缩因子，让内容区域占用更多空间
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setCollapsible(0, False)

        main_layout.addWidget(self.splitter)

        # 当前 AI 回复的消息标签（用于流式更新）
        self._current_ai_message = None

    def eventFilter(self, obj, event):
        """事件过滤器：捕获 Enter 键发送消息"""
        from PySide6.QtCore import QEvent

        if obj == self.editor and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
                # Shift+Enter 换行，Enter 发送
                if not event.modifiers() & Qt.ShiftModifier:
                    self._generate_with_ai()
                    return True
        return super().eventFilter(obj, event)

    def _add_user_message(self, text):
        """添加用户消息"""
        bubble = UserMessageBubble(self, text)

        # 在 stretch 之前插入消息，右对齐
        self.chat_messages_layout.insertWidget(self.chat_messages_layout.count() - 1, bubble, 0, Qt.AlignRight)

        # 滚动到底部
        QTimer.singleShot(50, self._scroll_chat_to_bottom)

    def _add_ai_message(self, initial_text: str = ""):
        """添加 AI 消息到聊天区域，返回消息对象用于流式更新"""
        bubble = AIMessageBubble(self, initial_text)

        # 在 stretch 之前插入消息，左对齐
        self.chat_messages_layout.insertWidget(self.chat_messages_layout.count() - 1, bubble, 0, Qt.AlignLeft)

        # 滚动到底部
        QTimer.singleShot(50, self._scroll_chat_to_bottom)

        return bubble

    def _copy_text_to_clipboard(self, text):
        """复制文本到剪贴板"""
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        ToastManager.instance().show("内容已复制", "success")

    # def submit_journal_from_text(self, content):
    #     """提交周记"""
    #     if not content:
    #         ToastManager.instance().show("内容为空", "warning")
    #         return
    #
    #     if not hasattr(self, 'trainee_id') or not self.trainee_id:
    #         ToastManager.instance().show("正在加载数据，请稍候...", "info")
    #         if hasattr(self, '_load_data_thread') and self._load_data_thread and self._load_data_thread.isRunning():
    #              return
    #         self._load_year_month_data()
    #         return
    #
    #     if self.week_combo.count() == 0:
    #         ToastManager.instance().show("未加载周次信息，请等待数据加载", "warning")
    #         return
    #
    #     week_data = self.week_combo.currentData()
    #     # 如果没有选中，选第一个
    #     if not week_data and self.week_combo.count() > 0:
    #          self.week_combo.setCurrentIndex(0)
    #          week_data = self.week_combo.currentData()
    #
    #     if not week_data:
    #          ToastManager.instance().show("无法获取周次信息", "error")
    #          return
    #
    #     start_date = week_data.get('startDate')
    #     end_date = week_data.get('endDate')
    #
    #     # 处理标题（第一行作为标题，最多20字）
    #     title = content.strip().split('\n')[0][:20] if content else "实习周记"
    #     permission = 0 # 默认 仅老师和同学可见 (我们在UI里虽然有combo但是可能没变)
    #     if hasattr(self, 'permission_combo') and self.permission_combo.count() > 0:
    #          permission = self.permission_combo.currentData()
    #
    #     reply = QMessageBox.question(
    #         self,
    #         "确认提交",
    #         f"周次：{start_date} 至 {end_date}\n标题：{title}\n\n确认提交为本周周记？",
    #         QMessageBox.Yes | QMessageBox.No,
    #         QMessageBox.Yes
    #     )
    #
    #     if reply == QMessageBox.Yes:
    #         self._submit_thread = SubmitJournalThread(
    #             self.args, self.config,
    #             title, content, start_date, end_date,
    #             permission, self.trainee_id
    #         )
    #         self._submit_thread.finished_signal.connect(self._on_submit_finished)
    #         self._submit_thread.error_signal.connect(self._on_submit_error)
    #         self._submit_thread.start()
    #         ToastManager.instance().show("正在提交周记...", "info")

    # def _on_submit_finished(self, result):
    #     ToastManager.instance().show("🎉 周记提交成功！", "success")
    #     if hasattr(self, '_submit_thread'):
    #         append_journal_entry("submitted", self._submit_thread.content)
    #         self._load_history()

    def _scroll_smart(self):
        """智能滚动：如果 AI 消息过长，则对齐顶部；否则对齐底部"""
        if not self._current_ai_message:
            self._scroll_chat_to_bottom()
            return

        bubble = self._current_ai_message

        # 确保布局更新以获取正确高度
        bubble.adjustSize()
        self.chat_messages.adjustSize()

        viewport_height = self.chat_scroll.viewport().height()
        bubble_height = bubble.height()
        bubble_y = bubble.y()  # 假如 chat_messages 是 ScrollArea 的 widget，pos() 就是相对坐标

        if bubble_height > viewport_height:
            # 对齐顶部
            self.chat_scroll.verticalScrollBar().setValue(bubble_y)
        else:
            # 短消息，滚到底部
            self._scroll_chat_to_bottom()

    def _clear_all(self):
        """清空内容"""
        self.editor.clear()

    def _clear_generated_history(self):
        """清空生成历史"""
        if self.generated_widget.count() == 0:
            return

        if not self._show_custom_confirm("确认清空",
                                         "确定要清空所有 AI 生成的历史记录吗？\n此操作将清除左侧列表中的所有记录。",
                                         confirm_text="🗑️ 清空",
                                         is_danger=True):
            return

        self.history["generated"] = []
        self.generated_widget.clear()
        clear_journal_history("generated")
        ToastManager.instance().show("生成历史已清空", "success")

    def _adjust_editor_height(self):
        """根据内容自动调整输入框高度"""
        # 获取文档高度
        doc = self.editor.document()
        doc_height = doc.size().height()

        # 计算目标高度（加上一些内边距）
        target_height = int(doc_height + 20)

        # 限制在最小和最大高度之间
        target_height = max(self._editor_min_height, min(target_height, self._editor_max_height))

        # 设置新高度
        self.editor.setMaximumHeight(target_height)
        self.editor.setMinimumHeight(target_height)

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
        # self._populate_list(self.submitted_widget, data.get("submitted", [])) # 不再加载本地提交记录

    def _load_blog_list_from_server(self, page=1):
        """从服务器加载周记列表"""
        if not self.args:
            return
        if self._is_loading_blog_list:
            return

        self.current_page = page
        self.lbl_page.setText(f"{self.current_page}/...")
        
        self.submitted_widget.clear()
        item = QListWidgetItem("正在加载...")
        item.setTextAlignment(Qt.AlignCenter)
        item.setFlags(Qt.NoItemFlags)
        self.submitted_widget.addItem(item)
        
        self.btn_prev.setEnabled(False)
        self.btn_next.setEnabled(False)
        self._is_loading_blog_list = True

        if not self.config:
             self.config = read_config(CONFIG_FILE)

        self._blog_list_request_id += 1
        req_id = self._blog_list_request_id
        self._load_blog_list_thread = LoadBlogListThread(self.args, self.config['input'], page)
        self._load_blog_list_thread.finished_signal.connect(
            lambda data, rid=req_id: self._on_blog_list_loaded(data, rid)
        )
        self._load_blog_list_thread.error_signal.connect(
            lambda err, rid=req_id: self._on_blog_list_error(err, rid)
        )
        self._load_blog_list_thread.start()

    def _on_blog_list_loaded(self, data, req_id=None):
        if req_id is not None and req_id != self._blog_list_request_id:
            return
        self._is_loading_blog_list = False
        self._load_blog_list_thread = None
        self.submitted_widget.clear()
        
        # 假设 data 是一个列表或者包含 list 的字典
        # 根据XYB接口通常返回，data可能直接是list，或者包含 list 和 pagination info
        # 这里先做通用处理
        blog_list = []
        total_pages = 1
        
        # 尝试解析数据结构
        if isinstance(data, list):
            blog_list = data
            # 如果是纯列表，可能没法知道总页数，除非列表为空说明到底了
            total_pages = self.current_page + 1 if len(blog_list) > 0 else self.current_page
        elif isinstance(data, dict):
            blog_list = data.get('list', [])
            total_pages = data.get('maxPage', 1)

        try:
            parsed_total_pages = int(total_pages)
        except (TypeError, ValueError):
            parsed_total_pages = self.current_page
        self.total_pages = max(1, parsed_total_pages)
        self.lbl_page.setText(f"{self.current_page}/{self.total_pages}")
        
        self.btn_prev.setEnabled(self.current_page > 1)
        self.btn_next.setEnabled(self.current_page < self.total_pages)

        if not blog_list:
            item = QListWidgetItem("暂无数据")
            item.setTextAlignment(Qt.AlignCenter)
            item.setFlags(Qt.NoItemFlags)
            self.submitted_widget.addItem(item)
            return

        for blog in blog_list:
            self._add_server_blog_item(blog)

    def _add_server_blog_item(self, blog):
        # 提取字段
        title = blog.get('blogTitle', '无标题')
        # 优先使用提交日期，如果没有则使用结束日期
        date_str = blog.get('commitDate') or blog.get('endDate') or ''
        # 如果包含年份则简化（假设当前年份）
        if len(date_str) > 5 and '.' in date_str:
            # 2025.11.23 -> 11.23
            parts = date_str.split('.')
            if len(parts) >= 2:
                date_str = f"{parts[-2]}.{parts[-1]}"
        
        blog_id = blog.get('blogId')
        content = blog.get('blogBody', '')
        week_range = f"{blog.get('startDate', '')}-{blog.get('endDate', '')}"
        
        # 创建列表项
        item = QListWidgetItem()
        # 存储数据
        item.setData(Qt.UserRole, content) 
        item.setData(Qt.UserRole + 1, blog_id)
        item.setData(Qt.UserRole + 2, title)
        item.setData(Qt.UserRole + 3, f"{date_str}  |  {week_range}")
        
        # 创建自定义 Widget
        widget = QWidget()
        widget.setStyleSheet("""
            QWidget {
                background-color: transparent;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)
        
        # 标题行
        title_label = QLabel(title)
        title_label.setStyleSheet("""
            font-family: "Microsoft YaHei", "Segoe UI";
            font-size: 13px;
            font-weight: bold;
            color: #E8EAED;
        """)
        title_label.setWordWrap(True)
        
        # 信息行 (日期 | 时间范围)
        info_layout = QHBoxLayout()
        info_layout.setSpacing(10)
        info_layout.setContentsMargins(0, 2, 0, 0)
        
        date_label = QLabel(f"{date_str}")
        date_label.setStyleSheet("color: #4A90D9; font-size: 11px; font-weight: 500;")
        
        range_label = QLabel(week_range)
        range_label.setStyleSheet("color: #80868B; font-size: 11px;")
        
        info_layout.addWidget(date_label)
        info_layout.addWidget(range_label)
        info_layout.addStretch()
        
        layout.addWidget(title_label)
        layout.addLayout(info_layout)
        
        # 强制设置合适的高度，避免挤压
        item.setSizeHint(QSize(200, 68))
        
        self.submitted_widget.addItem(item)
        self.submitted_widget.setItemWidget(item, widget)

    def _open_blog_detail(self, item: QListWidgetItem):
        """打开周记详情弹窗"""
        content = item.data(Qt.UserRole)
        blog_id = item.data(Qt.UserRole + 1)
        
        # 从 ItemWidget 中获取标题等信息（或者重新解析）
        # 这里简单起见，我们根据 Item 的显示习惯，或者重新获取 currentData?
        # 由于我们存了 content，但 title 没有存 UserRole，我们可以存一下
        title = item.data(Qt.UserRole + 2)
        date_info = item.data(Qt.UserRole + 3) # date | range
        
        dialog = BlogDetailDialog(title, date_info, content, self)
        if dialog.exec() == QDialog.Accepted and dialog.action == "use":
             # "使用此内容" - 覆盖当前编辑器
             self.editor.setPlainText(content)
             # 如果需要，也可以切换界面状态
             if self._title_container.isVisible():
                self._title_container.hide()
                self._top_spacer.hide()
                self._bottom_spacer.hide()
                self._chat_area_widget.setVisible(True)

    def _on_blog_list_error(self, err_msg, req_id=None):
        if req_id is not None and req_id != self._blog_list_request_id:
            return
        self._is_loading_blog_list = False
        self._load_blog_list_thread = None
        self.submitted_widget.clear()
        item = QListWidgetItem(f"加载失败")
        item.setToolTip(err_msg)
        item.setForeground(Qt.red)
        self.submitted_widget.addItem(item)
        self.btn_prev.setEnabled(self.current_page > 1)
        self.btn_next.setEnabled(self.current_page < self.total_pages)
        ToastManager.instance().show(f"加载列表失败: {err_msg}", "warning")

    def _prev_page(self):
        if self.current_page > 1:
            self._load_blog_list_from_server(self.current_page - 1)

    def _next_page(self):
        # 这里简单判断，只要当前页不是最后一页
        if self.current_page < self.total_pages:
            self._load_blog_list_from_server(self.current_page + 1)

    def _populate_list(self, widget: QListWidget, entries):
        if widget is None:
            return
        widget.clear()
        for entry in entries:
            content = entry.get("content", "")
            # 截取前20个字符作为预览
            content_preview = content[:20].replace("\n", " ") + "..." if len(content) > 20 else content
            # 去除年份显示 (YYYY-MM-DD HH:MM -> MM-DD HH:MM)
            timestamp = entry.get("timestamp", "")
            if len(timestamp) >= 5:
                timestamp = timestamp[5:]

            item_text = f"[{timestamp}] {content_preview}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, content)
            widget.addItem(item)

    def _generate_with_ai(self):
        if self._ai_busy:
            return

        prompt_context = self.editor.toPlainText().strip()

        if not prompt_context:
            return

        # 第一次发送消息时，切换布局
        if self._title_container.isVisible():
            self._title_container.hide()
            self._top_spacer.hide()
            self._bottom_spacer.hide()
            self._chat_area_widget.setVisible(True)

        # 添加用户消息到聊天区域
        self._add_user_message(prompt_context)

        self._set_ai_busy(True)
        self.editor.clear()

        # 创建 AI 消息标签用于流式更新
        self._current_ai_message = self._add_ai_message("正在思考...")
        self._ai_response_text = ""

        # 创建并启动异步线程
        self._ai_thread = AIGenerationThread(self.args, self.config['input'], prompt_context, SYSTEM_PROMPT)
        self._ai_thread.delta_signal.connect(self._on_ai_delta)
        self._ai_thread.finished_signal.connect(self._on_ai_finished)
        self._ai_thread.error_signal.connect(self._on_ai_error)
        self._ai_thread.start()

    def _on_ai_delta(self, delta: str):
        """处理AI生成的增量内容 - 流式输出效果"""
        if self._current_ai_message:
            self._ai_response_text += delta
            # 更新UI
            self._current_ai_message.setText(self._ai_response_text)

            # 智能滚动
            self._scroll_smart()

    def _on_ai_finished(self, full_text: str):
        """AI生成完成"""
        self._set_ai_busy(False)
        if self._current_ai_message:
            self._current_ai_message.setText(full_text)
            self._scroll_smart()

        # 记录到历史
        if not full_text.strip():
            return
        append_journal_entry("generated", full_text)
        # ToastManager.instance().show("AI 回复已生成", "success")
        self._load_history()
        self._current_ai_message = None
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
            with open("debug_crash.txt", "a", encoding="utf-8") as f: f.write("STEP 10: Entering _load_year_month_data\n")
            if self._is_loading_year_data:
                return
            if not self.config:
                self.config = read_config(CONFIG_FILE)
            # 在子线程中加载数据，避免阻塞UI
            with open("debug_crash.txt", "a", encoding="utf-8") as f: f.write("STEP 11: Creating LoadYearDataThread\n")
            self._is_loading_year_data = True
            self._load_data_thread = LoadYearDataThread(self.config, self.args)
            self._load_data_thread.finished_signal.connect(self._on_year_data_loaded)
            self._load_data_thread.error_signal.connect(self._on_year_data_error)
            self._load_data_thread.start()
            with open("debug_crash.txt", "a", encoding="utf-8") as f: f.write("STEP 12: LoadYearDataThread started\n")
            self.btn_load_data.setEnabled(False)
            self.btn_load_data.setText("加载中...")
        except Exception as e:
            self._is_loading_year_data = False
            with open("debug_crash.txt", "a", encoding="utf-8") as f: f.write(f"CRASH IN _load_year_month_data: {e}\n")
            logging.error(f"加载年月数据失败: {e}")
            ToastManager.instance().show(f"加载失败: {str(e)}", "warning")

    def _on_year_data_loaded(self, login_args, trainee_id, year_data):
        """年份数据加载完成"""
        try:
            with open("debug_crash.txt", "a", encoding="utf-8") as f: f.write("STEP 13: _on_year_data_loaded called\n")
            self.args = login_args
            self.trainee_id = trainee_id
            self.year_data = year_data
            # 更新UI（阻断信号，避免填充过程触发重复加载）
            self.year_combo.blockSignals(True)
            self.year_combo.clear()
            
            if self.year_data is None:
                self.year_data = []

            for i, year_item in enumerate(self.year_data):
                year_name = str(year_item.get('name', ''))
                # 改为存储索引，避免C++层崩溃
                self.year_combo.addItem(year_name, i)
            
            # 保持阻断直到设置完 index
            if self.year_combo.count() > 0:
                self.year_combo.setCurrentIndex(0)
            
            self.year_combo.blockSignals(False)
            
            if self.year_combo.count() > 0:
                self._on_year_changed()

            self._is_loading_year_data = False
            self._load_data_thread = None
            self.btn_load_data.setEnabled(True)
            self.btn_load_data.setText("加载年月")
            
            ToastManager.instance().show("年月数据加载成功", "success")
            
            # 登录信息更新后，加载第一页周记列表
            self._load_blog_list_from_server(1)

        except Exception as e:
            import traceback
            err_msg = traceback.format_exc()
            self._is_loading_year_data = False
            self._load_data_thread = None
            # 再次抛出以便全局捕获（如果有）
            raise e

    def _on_year_data_error(self, error_msg):
        """年份数据加载失败"""
        logging.error(f"加载年份数据失败: {error_msg}")
        self._is_loading_year_data = False
        self._load_data_thread = None
        self.btn_load_data.setEnabled(True)
        self.btn_load_data.setText("加载年月")
        if "缓存登录失败" in error_msg or "过期" in error_msg or "失效" in error_msg:
            ToastManager.instance().show("登录信息已过期，请先执行签到操作以获取新的登录信息", "warning")
        else:
            ToastManager.instance().show(f"加载失败: {error_msg}", "warning")

    def _load_year_data(self):
        """加载年份和月份数据"""
        try:
            if not self.args or not self.trainee_id:
                return
            self.year_data = load_blog_year(self.args, self.config['input'])
            self.year_combo.blockSignals(True)
            self.year_combo.clear()
            for i, year_item in enumerate(self.year_data):
                year_name = year_item.get('name', '')
                self.year_combo.addItem(year_name, i)
            if self.year_combo.count() > 0:
                self.year_combo.setCurrentIndex(0)
            self.year_combo.blockSignals(False)
            if self.year_combo.count() > 0:
                self._on_year_changed()
        except Exception as e:
            logging.error(f"加载年份数据失败: {e}")
            ToastManager.instance().show(f"加载年份失败: {str(e)}", "warning")

    def _stop_auto_finding(self):
        """用户手动操作时停止自动跳转"""
        self._auto_finding_next = False

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
            with open("debug_crash.txt", "a", encoding="utf-8") as f: f.write("STEP YC.1: _on_year_changed called\n")
            year_idx = self.year_combo.currentData()

            if year_idx is None or not isinstance(year_idx, int):
                with open("debug_crash.txt", "a", encoding="utf-8") as f: f.write(f"STEP YC.1.1: Invalid year_idx: {year_idx}, returning\n")
                return

            if not self.year_data or year_idx >= len(self.year_data):
                with open("debug_crash.txt", "a", encoding="utf-8") as f: f.write(f"STEP YC.1.2: year_data empty or index out of bounds: {year_idx}, returning\n")
                return

            year_item = self.year_data[year_idx]
            with open("debug_crash.txt", "a", encoding="utf-8") as f: f.write(f"STEP YC.2: Got year_item index {year_idx} (name: {year_item.get('name')})\n")

            raw_months = year_item.get('months', [])
            try:
                self.current_months = sorted(raw_months, key=lambda x: int(x.get('id', 0)))
            except Exception as e:
                logging.error(f"月份排序失败: {e}")
                self.current_months = raw_months

            with open("debug_crash.txt", "a", encoding="utf-8") as f: f.write(f"STEP YC.3: months sorted ({len(self.current_months)} items)\n")

            # 阻断信号
            self.month_combo.blockSignals(True)
            self.month_combo.clear()
            for i, month_item in enumerate(self.current_months):
                month_name = month_item.get('name', '')
                self.month_combo.addItem(month_name, i) # 存储索引

            with open("debug_crash.txt", "a", encoding="utf-8") as f: f.write("STEP YC.4: month_combo populated\n")

            # 手动调用一次自动查找逻辑
            if self.month_combo.count() > 0:
                self.month_combo.setCurrentIndex(0)

            # 解除阻断 (但在手动调用前保持阻断也可以，或者解除后不依靠信号)
            # 为了防止 setCurrentIndex 触发信号（如果它变了），我们将解除阻断放在后面，或者就是依靠显式调用
            # 实际上 setCurrentIndex(0) 如果之前是空，可能会触发。我们希望屏蔽它。

            self.month_combo.blockSignals(False)

            if self.month_combo.count() > 0:
                 with open("debug_crash.txt", "a", encoding="utf-8") as f: f.write("STEP YC.5: calling _on_month_changed explicitly\n")
                 self._on_month_changed()

            with open("debug_crash.txt", "a", encoding="utf-8") as f: f.write("STEP YC.End: _on_year_changed finished\n")
        except Exception as e:
            msg = f"CRASH IN _on_year_changed: {e}"
            with open("debug_crash.txt", "a", encoding="utf-8") as f: f.write(msg + "\n")
            logging.error(f"更新月份失败: {e}")


    def _on_month_changed(self):
        """月份改变时更新周信息"""
        try:
            with open("debug_crash.txt", "a", encoding="utf-8") as f: f.write("STEP MC.1: _on_month_changed called\n")
            # 标志位：防止重复触发导致并发请求堆积
            if self._is_loading_week_data:
                with open("debug_crash.txt", "a", encoding="utf-8") as f: f.write("STEP MC.Skip: already loading week data\n")
                return

            year_idx = self.year_combo.currentData()
            month_idx = self.month_combo.currentData()
            
            if year_idx is None or month_idx is None: 
                return
            
            if not isinstance(year_idx, int) or not isinstance(month_idx, int):
                with open("debug_crash.txt", "a", encoding="utf-8") as f: f.write(f"STEP MC.Error: invalid indices {year_idx}, {month_idx}\n")
                return

            year_item = self.year_data[year_idx]
            month_item = self.current_months[month_idx]
            with open("debug_crash.txt", "a", encoding="utf-8") as f: f.write(f"STEP MC.2: Selected {year_item.get('name')} - {month_item.get('name')}\n")

            year_id = year_item.get('id')
            month_id = month_item.get('id')
            if not year_id or not month_id:
                return

            current_key = f"{year_id}-{month_id}"
            if self._last_loaded_year_month_key == current_key and self.week_combo.count() > 0:
                with open("debug_crash.txt", "a", encoding="utf-8") as f: f.write(f"STEP MC.Skip: duplicated year-month {current_key}\n")
                return
            self._current_year_month_key = current_key
             
            # 使用线程异步加载
            self.week_combo.blockSignals(True)
            self.week_combo.clear()
            self.week_combo.addItem("加载中...", None)
            self.week_combo.blockSignals(False)
            
            # 禁用相关控件防止并发操作
            self.year_combo.setEnabled(False)
            self.month_combo.setEnabled(False)
            self.week_combo.setEnabled(False)
            self._is_loading_week_data = True

            self._load_week_data_thread = LoadWeekDataThread(self.args, self.config['input'], year_id, month_id)
            self._load_week_data_thread.finished_signal.connect(self._on_week_data_loaded)
            self._load_week_data_thread.error_signal.connect(self._on_week_data_error)
            self._load_week_data_thread.start()
            with open("debug_crash.txt", "a", encoding="utf-8") as f: f.write("STEP MC.3: Week thread started\n")

        except Exception as e:
            msg = f"CRASH IN _on_month_changed: {e}"
            with open("debug_crash.txt", "a", encoding="utf-8") as f: f.write(msg + "\n")
            self._is_loading_week_data = False
            logging.error(f"更新周信息失败: {e}")
            ToastManager.instance().show(f"加载周信息失败: {str(e)}", "warning")

    def _on_week_data_loaded(self, week_data):
        try:
            with open("debug_crash.txt", "a", encoding="utf-8") as f: f.write("STEP WD.1: _on_week_data_loaded called\n")
            self.week_data = week_data
            self.week_combo.clear()
            target_index = 0
            found_unsubmitted = False

            with open("debug_crash.txt", "a", encoding="utf-8") as f: f.write(f"STEP WD.2: week_data len: {len(week_data)}\n")

            for i, week_item in enumerate(self.week_data):
                week_num = week_item.get('week', 0)
                start_date = week_item.get('startDate', '')
                end_date = week_item.get('endDate', '')
                blog_count = week_item.get('blogCount', 0)

                # 调试：更稳健的状态检查
                raw_status = week_item.get('status')
                status_code = str(raw_status) if raw_status is not None else "2"
                is_submitted = (status_code == "1")

                status_text = "已提交" if is_submitted else "未提交"
                week_text = f"第{week_num}周 ({start_date} ~ {end_date}) - {status_text} ({blog_count}篇)"
                # 改为存储索引
                self.week_combo.addItem(week_text, i)

                # 记录第一个未提交的周次索引
                if not found_unsubmitted and not is_submitted:
                    target_index = i
                    found_unsubmitted = True

            with open("debug_crash.txt", "a", encoding="utf-8") as f: f.write("STEP WD.3: week_combo populated\n")

            # 恢复控件状态
            self.year_combo.setEnabled(True)
            self.month_combo.setEnabled(True)
            self.week_combo.setEnabled(True)
            self._load_week_data_thread = None
            self._is_loading_week_data = False
            self._last_loaded_year_month_key = self._current_year_month_key

            # 默认选中第一个
            if self.week_combo.count() > 0:
                self.week_combo.setCurrentIndex(0)



        except Exception as e:
            with open("debug_crash.txt", "a", encoding="utf-8") as f: f.write(f"CRASH IN _on_week_data_loaded: {e}\n")
            logging.error(f"加载周数据失败: {e}")



    def _on_week_data_error(self, err_msg):
        self.week_combo.clear()
        self.week_combo.addItem("加载失败", None)
        ToastManager.instance().show(f"加载周信息失败: {err_msg}", "warning")
        
        # 恢复控件状态
        self.year_combo.setEnabled(True)
        self.month_combo.setEnabled(True)
        self.week_combo.setEnabled(True)
        self._load_week_data_thread = None
        self._is_loading_week_data = False

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

        # 获取内容
        full_content = self.editor.toPlainText().strip()
        if not full_content:
            ToastManager.instance().show("请先输入或生成周记内容", "info")
            return

        # 从内容解析标题和正文
        lines = full_content.split('\n')
        first_line = lines[0].strip()
        week_idx = self.week_combo.currentData()
        week_item = None
        if isinstance(week_idx, int) and self.week_data and 0 <= week_idx < len(self.week_data):
            week_item = self.week_data[week_idx]

        # 如果第一行看起来像标题（较短且不以标点结尾），则使用第一行作为标题
        if len(first_line) <= 50 and not first_line.endswith(('。', '！', '？', '.', '!', '?', ',')):
            title = first_line
            content = '\n'.join(lines[1:]).strip() if len(lines) > 1 else first_line
        else:
            # 否则自动生成标题
            if week_item:
                week_num = week_item.get('week', '')
                title = f"第{week_num}周实习周记"
            else:
                title = "实习周记"
            content = full_content

        # 检查是否选择了周
        if not week_item:
            ToastManager.instance().show("请选择要绑定的周", "warning")
            return

        # 检查登录信息
        if not self.args or not self.trainee_id:
            ToastManager.instance().show("登录信息无效，请先执行签到操作以获取登录信息", "warning")
            return

        try:
            # 获取选中的周信息
            start_date = week_item.get('startDate', '')
            end_date = week_item.get('endDate', '')
            blog_open_type = self.permission_combo.currentData()

            # 提交周记
            try:
                blog_id = submit_blog(args=self.args, config=self.config['input'], blog_title=title, blog_body=content,
                                      start_date=start_date, end_date=end_date, blog_open_type=blog_open_type,
                                      trainee_id=self.trainee_id)

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
                    self.args = None
                    self.trainee_id = None
                else:
                    raise
        except Exception as e:
            logging.error(f"提交周记失败: {e}")
            ToastManager.instance().show(f"提交周记失败: {str(e)}", "error")

    def submit_journal_from_text(self, content):
        """从文本提交周记（工具栏调用）"""
        if hasattr(self, '_submit_thread') and self._submit_thread and self._submit_thread.isRunning():
            ToastManager.instance().show("正在提交中，请稍后...", "warning")
            return

        # 弹出配置与确认对话框 (内部处理提交逻辑)
        self._show_submit_config_dialog(content)

    def _show_submit_config_dialog(self, content):
        """显示提交配置对话框"""
        # 检查当前是否需要自动跳转（如果当前已加载的全部已提交）
        if self.week_data:
            all_submitted = all(w.get('status') == 1 for w in self.week_data)
            if all_submitted:
                self._auto_finding_next = True
                # 尝试触发一次跳转
                if not self._try_auto_switch_next():
                    self._auto_finding_next = False

        dialog = QDialog(self)
        dialog.setWindowTitle("提交周记配置")
        dialog.setFixedWidth(500)
        dialog.setStyleSheet("""
            QDialog { background-color: #1E1E1E; color: white; }
            QLabel { color: #CCCCCC; font-size: 14px; }
            QTextEdit, QLineEdit { background-color: #2D2D2D; border: 1px solid #3E3E3E; padding: 8px; border-radius: 4px; color: white; }
            QPushButton { 
                padding: 6px 16px; border-radius: 4px; font-size: 13px; 
                background-color: #3E3E3E; color: white; border: 1px solid #555;
            }
            QPushButton:hover { background-color: #4E4E4E; }
        """)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(16)

        # 1. 配置项布局 (复用 hidden combos)
        # 注意：此处我们将 combos "借用" 到对话框中显示，关闭时必须还回去
        self.year_combo.setVisible(True)
        self.month_combo.setVisible(True)
        self.week_combo.setVisible(True)
        self.permission_combo.setVisible(True)

        # 设置下拉框样式以适配 Dialog
        combo_style = """
            QComboBox {
                background-color: #2D2D2D; color: white; border: 1px solid #3E3E3E; 
                padding: 4px 8px; border-radius: 4px; min-width: 120px;
            }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView {
                background-color: #2D2D2D; color: white; selection-background-color: #3E3E3E;
            }
        """
        self.year_combo.setStyleSheet(combo_style)
        self.month_combo.setStyleSheet(combo_style)
        self.week_combo.setStyleSheet(combo_style)
        self.permission_combo.setStyleSheet(combo_style)

        form_layout = QHBoxLayout()  # 使用水平布局排列配置项
        form_layout.addWidget(QLabel("年份:"))
        form_layout.addWidget(self.year_combo)
        form_layout.addWidget(QLabel("月份:"))
        form_layout.addWidget(self.month_combo)
        form_layout.addStretch()

        form_layout2 = QHBoxLayout()
        form_layout2.addWidget(QLabel("周次:"))
        form_layout2.addWidget(self.week_combo, 1)  # 周次较长
        form_layout2.addWidget(QLabel("权限:"))
        form_layout2.addWidget(self.permission_combo)

        layout.addLayout(form_layout)
        layout.addLayout(form_layout2)

        # 1.5 标题 (可编辑)
        title_layout = QHBoxLayout()
        title_layout.addWidget(QLabel("标题:"))
        title_edit = QLineEdit()
        # 默认标题
        week_idx = self.week_combo.currentData()
        if week_idx is not None and isinstance(week_idx, int) and self.week_data:
            current_week_item = self.week_data[week_idx]
            title_edit.setText(f"第{current_week_item.get('week', '')}周实习周记")
        else:
            title_edit.setText("实习周记")
        title_layout.addWidget(title_edit)
        layout.addLayout(title_layout)

        # 2. 内容编辑
        layout.addWidget(QLabel("周记内容 (可编辑):"))
        content_edit = QTextEdit()
        content_edit.setPlainText(content)
        content_edit.setMinimumHeight(200)
        layout.addWidget(content_edit)

        # 3. 按钮
        btn_box = QHBoxLayout()
        btn_cancel = QPushButton("取消")
        btn_submit = QPushButton("🚀 确认提交")
        btn_submit.setStyleSheet("""
            QPushButton { 
                background-color: #2563EB; color: white; border: none; font-weight: bold;
            }
            QPushButton:hover { background-color: #1D4ED8; }
            QPushButton:disabled { background-color: #4B5563; color: #9CA3AF; }
        """)

        btn_cancel.clicked.connect(dialog.reject)
        
        # 定义提交逻辑
        def on_submit_click():
             week_idx = self.week_combo.currentData()
             if week_idx is None or not isinstance(week_idx, int):
                 ToastManager.instance().show("请先选择周次", "warning")
                 return
             
             week_item = self.week_data[week_idx]
             
             start_date = week_item.get('startDate')
             end_date = week_item.get('endDate')
             permission = self.permission_combo.currentData()
             final_title = title_edit.text().strip()
             final_content = content_edit.toPlainText()
             
             # 禁用UI
             btn_submit.setEnabled(False)
             btn_submit.setText("提交中...")
             title_edit.setEnabled(False)
             content_edit.setEnabled(False)
             btn_cancel.setEnabled(False)
             
             # 启动线程 (临时属性挂到 dialog 上避免被回收)
             dialog._thread = SubmitJournalThread(
                args=self.args, config=self.config['input'],
                blog_title=final_title, blog_body=final_content, 
                start_date=start_date, end_date=end_date,
                blog_open_type=permission, trainee_id=self.trainee_id
             )
             
             def on_success(msg):
                 ToastManager.instance().show(msg, "success")
                 append_journal_entry("submitted", final_content)
                 # 刷新列表
                 self._load_blog_list_from_server(1)
                 # 关闭对话框
                 dialog.accept()
                 
             def on_error(err):
                 ToastManager.instance().show(f"提交失败: {err}", "error")
                 # 恢复UI
                 btn_submit.setEnabled(True)
                 btn_submit.setText("🚀 确认提交")
                 title_edit.setEnabled(True)
                 content_edit.setEnabled(True)
                 btn_cancel.setEnabled(True)
                 
             dialog._thread.finished_signal.connect(on_success)
             dialog._thread.error_signal.connect(on_error)
             dialog._thread.start()

        btn_submit.clicked.connect(on_submit_click)

        btn_box.addStretch()
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_submit)
        layout.addLayout(btn_box)

        # 执行对话框
        dialog.exec()

        # 4. 恢复 Combos (无论结果如何都归还)
        # 必须先重新设置 parent，否则 visible 设为 false 可能没用（如果 dialog 销毁）
        self.year_combo.setParent(self)
        self.month_combo.setParent(self)
        self.week_combo.setParent(self)
        self.permission_combo.setParent(self)

        self.year_combo.setVisible(False)
        self.month_combo.setVisible(False)
        self.week_combo.setVisible(False)
        self.permission_combo.setVisible(False)

    def _fill_from_history(self, item: QListWidgetItem):
        content = item.data(Qt.UserRole)
        if content:
            # 确保切换到聊天模式（隐藏主标题和占位符）
            if self._title_container.isVisible():
                self._title_container.hide()
                self._top_spacer.hide()
                self._bottom_spacer.hide()
                self._chat_area_widget.setVisible(True)

            # 将历史记录展示在聊天窗口，而不是覆盖输入框
            self._add_ai_message(content)
            # 滚动到底部确保可见
            QTimer.singleShot(100, lambda: self._scroll_chat_to_bottom())

    def _scroll_chat_to_bottom(self):
        """滚动聊天记录到底部"""
        bar = self.chat_scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _clear_chat_session(self):
        """清空当前对话内容并恢复初始状态"""
        if self._chat_area_widget.isHidden() and not self.editor.toPlainText().strip():
            # 已经在初始状态且无内容，无需操作
            return

        # 使用自定义确认对话框
        # if not self._show_custom_confirm("确认清空", "确定要清空当前对话内容吗？\n此操作无法撤销。",
        #                                  confirm_text="🗑️ 清空", is_danger=True):
        #     return

        # 清空聊天消息
        while self.chat_messages_layout.count() > 0:
            item = self.chat_messages_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 重新添加底部弹簧
        self.chat_messages_layout.addStretch()

        # 恢复初始布局状态
        self._chat_area_widget.hide()
        self._title_container.show()
        self._top_spacer.show()
        self._bottom_spacer.show()

        # 清空输入框
        self.editor.clear()
        self.btn_ai.setEnabled(True)

    def _show_custom_confirm(self, title, text, confirm_text="确认", is_danger=False):
        """显示自定义样式的确认对话框 (使用 CustomConfirmDialog)"""
        dialog = CustomConfirmDialog(self, title, text, confirm_text, is_danger)
        return dialog.exec() == QDialog.Accepted

    # ---------------------- Server Helpers ----------------------
    def _setup_styles(self):
        self.setStyleSheet("""
            /* ========== 全局样式 - DeepSeek 风格 ========== */
            QWidget {
                font-family: "Google Sans", "Segoe UI", "Microsoft YaHei", sans-serif;
            }
            QDialog {
                background-color: #131726;
                color: #E8EAED;
            }

            /* ========== 左侧边栏 ========== */
            QFrame#Sidebar {
                background-color: #0D1117;
                border-right: 1px solid rgba(138, 180, 248, 0.08);
            }
            QLabel#SidebarTitle {
                color: #E8EAED;
                font-size: 18px;
                font-weight: 600;
                padding: 8px 0 16px 0;
                letter-spacing: 0.5px;
            }
            QLabel#SidebarLabel {
                color: #6B7280;
                font-size: 11px;
                font-weight: 500;
                padding-top: 12px;
                padding-bottom: 4px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            QListWidget#HistoryList {
                background-color: transparent;
                border: none;
                border-radius: 8px;
                padding: 0;
                outline: none;
            }
            QListWidget#HistoryList::item {
                padding: 8px 10px;
                margin: 1px 0;
                border-radius: 6px;
                color: #9AA0A6;
                font-size: 12px;
                border-left: 2px solid transparent;
            }
            QListWidget#HistoryList::item:selected {
                background-color: rgba(74, 144, 217, 0.15);
                color: #E8EAED;
                border-left: 2px solid #4A90D9;
            }
            QListWidget#HistoryList::item:hover {
                background-color: rgba(255, 255, 255, 0.03);
            }

            /* ========== 右侧内容区 ========== */
            QFrame#ContentArea {
                background-color: #131726;
            }
            QScrollArea#MainScrollArea {
                background-color: #131726;
                border: none;
            }
            QWidget#CentralWidget {
                background-color: #131726;
            }

            /* ========== 聊天区域 ========== */
            QFrame#ChatContainer {
                background-color: transparent;
            }
            QScrollArea#ChatScrollArea {
                background-color: transparent;
                border: none;
            }
            QWidget#ChatMessages {
                background-color: transparent;
            }

            /* ========== 用户消息 ========== */
            QFrame#UserMessage {
                background-color: transparent;
            }
            QLabel#UserMessageText {
                background-color: #2563EB;
                color: #FFFFFF;
                padding: 12px 16px;
                border-radius: 18px;
                border-bottom-right-radius: 4px;
                font-size: 14px;
                line-height: 1.5;
            }

            /* ========== AI 消息 ========== */
            QFrame#AIMessage {
                background-color: transparent;
            }
            QLabel#AIIcon {
                font-size: 20px;
                padding: 4px 8px 4px 0;
            }
            QLabel#AIMessageText {
                background-color: rgba(32, 39, 55, 0.6);
                color: #E8EAED;
                padding: 12px 16px;
                border-radius: 18px;
                border-bottom-left-radius: 4px;
                font-size: 14px;
                line-height: 1.5;
            }

            /* ========== 主标题 ========== */
            QLabel#MainTitle {
                color: #E8EAED;
                font-size: 24px;
                font-weight: 500;
                letter-spacing: 0.3px;
            }

            /* ========== 输入容器 ========== */
            QFrame#InputContainer {
                background-color: rgba(32, 39, 55, 0.6);
                border: 1px solid rgba(138, 180, 248, 0.12);
                border-radius: 24px;
            }

            /* ========== 配置容器 ========== */
            QFrame#ConfigContainer {
                background-color: rgba(32, 39, 55, 0.4);
                border: 1px solid rgba(138, 180, 248, 0.08);
                border-radius: 16px;
            }
            QLabel#ConfigLabel {
                color: #9AA0A6;
                font-size: 12px;
                font-weight: 500;
            }

            /* ========== 标签样式 ========== */
            QLabel {
                color: #9AA0A6;
                font-size: 13px;
                font-weight: 500;
                letter-spacing: 0.3px;
            }

            /* ========== 文本编辑区 - 玻璃态效果 ========== */
            QTextEdit {
                background-color: rgba(32, 39, 55, 0.85);
                border: 1px solid rgba(138, 180, 248, 0.15);
                border-radius: 16px;
                padding: 20px;
                font-size: 15px;
                line-height: 1.8;
                color: #E8EAED;
                selection-background-color: rgba(138, 180, 248, 0.3);
            }
            QTextEdit:focus {
                border: 1px solid rgba(138, 180, 248, 0.5);
                background-color: rgba(32, 39, 55, 0.95);
            }
            QTextEdit#MainEditor {
                background-color: transparent;
                border: none;
                border-radius: 0;
                padding: 8px 4px;
                font-size: 15px;
                min-height: 60px;
            }
            QTextEdit#MainEditor:focus {
                border: none;
                background-color: transparent;
            }

            /* ========== 输入框样式 ========== */
            QLineEdit {
                background-color: rgba(32, 39, 55, 0.7);
                border: 1px solid rgba(138, 180, 248, 0.15);
                border-radius: 12px;
                padding: 12px 16px;
                font-size: 14px;
                color: #E8EAED;
            }
            QLineEdit:focus {
                border: 1px solid rgba(138, 180, 248, 0.6);
                background-color: rgba(32, 39, 55, 0.9);
            }
            QLineEdit::placeholder {
                color: #5F6368;
            }

            /* ========== 历史记录列表 ========== */
            QListWidget {
                background-color: rgba(32, 39, 55, 0.6);
                border: 1px solid rgba(138, 180, 248, 0.1);
                border-radius: 16px;
                outline: none;
                padding: 8px;
            }
            QListWidget::item {
                padding: 14px 16px;
                margin: 4px 0;
                border-radius: 12px;
                border: none;
                color: #BDC1C6;
            }
            QListWidget::item:selected {
                background-color: rgba(138, 180, 248, 0.15);
                color: #E8EAED;
            }
            QListWidget::item:hover {
                background-color: rgba(138, 180, 248, 0.08);
            }

            /* ========== 卡片容器 - 玻璃态 ========== */
            QFrame#ConfigCard {
                background-color: rgba(32, 39, 55, 0.75);
                border: 1px solid rgba(138, 180, 248, 0.12);
                border-radius: 20px;
            }
            QFrame#ContentCard {
                background-color: rgba(32, 39, 55, 0.65);
                border: 1px solid rgba(138, 180, 248, 0.10);
                border-radius: 20px;
            }
            QFrame#HistoryCard {
                background-color: rgba(32, 39, 55, 0.55);
                border: 1px solid rgba(138, 180, 248, 0.08);
                border-radius: 20px;
            }
            QFrame#RoleCard {
                background-color: rgba(32, 39, 55, 0.5);
                border: 1px solid rgba(138, 180, 248, 0.08);
                border-radius: 14px;
            }

            /* ========== 输入框变体 ========== */
            QLineEdit#PromptInput {
                background-color: rgba(32, 39, 55, 0.4);
                font-size: 13px;
                border-radius: 10px;
            }
            QLineEdit#TitleInput {
                font-size: 18px;
                font-weight: 600;
                padding: 14px 18px;
                background-color: rgba(32, 39, 55, 0.5);
                border-radius: 14px;
                letter-spacing: 0.5px;
            }

            /* ========== 下拉框样式 ========== */
            QComboBox {
                background-color: #2a2d3e;
                border: none;
                border-radius: 20px;
                padding: 8px 14px;
                color: #FFFFFF;
                min-height: 22px;
                font-size: 13px;
            }
            QComboBox:hover {
                background-color: #363a4d;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QComboBox QAbstractItemView {
                background-color: #1F2233;
                border: 1px solid #2F3342;
                border-radius: 8px;
                color: #B0B3B8;
                outline: none;
                padding: 4px;
            }
            QComboBox QAbstractItemView::item {
                padding: 12px 14px;
                border-bottom: 1px solid rgba(255, 255, 255, 0.08);
            }
            QComboBox QAbstractItemView::item:selected {
                background-color: #363B4C;
                color: #FFFFFF;
                border-radius: 6px;
                border-left: 3px solid #4F6BFF;
                padding-left: 11px;
            }

            /* ========== 按钮基础样式 ========== */
            QPushButton {
                border-radius: 12px;
                padding: 12px 24px;
                font-weight: 600;
                font-size: 14px;
                border: none;
                letter-spacing: 0.3px;
            }

            /* ========== 工具栏下拉框 ========== */
            QComboBox#ToolbarCombo {
                background-color: #2a2d3e;
                border: none;
                border-radius: 20px;
                padding: 8px 14px;
                color: #FFFFFF;
                font-size: 13px;
                min-height: 18px;
            }
            QComboBox#ToolbarCombo:hover {
                background-color: #363a4d;
            }

            /* ========== 工具栏按钮 ========== */
            QPushButton#ToolbarBtn {
                background-color: transparent;
                border: 1px solid rgba(138, 180, 248, 0.2);
                color: #9AA0A6;
                padding: 8px 16px;
                border-radius: 8px;
                font-size: 13px;
            }
            QPushButton#ToolbarBtn:hover {
                border-color: rgba(138, 180, 248, 0.4);
                color: #E8EAED;
                background-color: rgba(138, 180, 248, 0.08);
            }

            /* ========== 发送按钮（已废弃，保留兼容） ========== */
            QPushButton#SendBtn {
                background-color: #4A90D9;
                color: #FFFFFF;
                padding: 8px 12px;
                border-radius: 10px;
                font-size: 16px;
                min-width: 36px;
                max-width: 36px;
            }
            QPushButton#SendBtn:hover {
                background-color: #5A9FE8;
            }

            /* ========== AI 主按钮（纯色） ========== */
            QPushButton#PrimaryBtn {
                background-color: #4A90D9;
                color: #FFFFFF;
                font-weight: 600;
                padding: 12px 24px;
                border-radius: 12px;
            }
            QPushButton#PrimaryBtn:hover {
                background-color: #5A9FE8;
            }
            QPushButton#PrimaryBtn:pressed {
                background-color: #3A80C9;
            }
            QPushButton#PrimaryBtn:disabled {
                background-color: rgba(74, 144, 217, 0.4);
                color: rgba(255, 255, 255, 0.5);
            }

            /* ========== 提交按钮 - 成功色 ========== */
            QPushButton#SuccessBtn {
                background-color: #2a2d3e;
                color: #FFFFFF;
                font-weight: 500;
                padding: 8px 16px;
                border-radius: 20px;
                font-size: 13px;
            }
            QPushButton#SuccessBtn:hover {
                background-color: #363a4d;
            }
            QPushButton#SuccessBtn:pressed {
                background-color: #22253a;
            }

            QPushButton#AIBtn {
                background: #191B2A;
                color: #D0D5FF;
                border: 1px solid #22263A;
                padding: 8px 16px;
                border-radius: 10px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton#AIBtn:hover {
                border-color: #4F6BFF;
                color: white;
            }
            QPushButton#AIBtn:pressed {
                background: #15182a;
                border-color: #3A60DD;
            }
            QPushButton#AIBtn:disabled {
                background: rgba(25, 27, 42, 0.5);
                color: rgba(208, 213, 255, 0.4);
                border-color: rgba(34, 38, 58, 0.5);
            }

            /* ========== 提交按钮（统一样式） ========== */
            QPushButton#SubmitBtn {
                background-color: #2a2d3e;
                color: #FFFFFF;
                font-weight: 500;
                padding: 8px 16px;
                border-radius: 20px;
                font-size: 13px;
            }
            QPushButton#SubmitBtn:hover {
                background-color: #363a4d;
            }
            QPushButton#SubmitBtn:pressed {
                background-color: #22253a;
            }

            /* ========== 幽灵按钮 ========== */
            QPushButton#GhostBtn {
                background-color: transparent;
                border: 1px solid rgba(138, 180, 248, 0.25);
                color: #9AA0A6;
                padding: 12px 20px;
            }
            QPushButton#GhostBtn:hover {
                border-color: rgba(138, 180, 248, 0.5);
                color: #E8EAED;
                background-color: rgba(138, 180, 248, 0.08);
            }
            QPushButton#GhostBtn:pressed {
                background-color: rgba(138, 180, 248, 0.15);
            }

            /* ========== 图标按钮 ========== */
            QPushButton#IconBtn {
                background-color: transparent;
                border: 1px solid rgba(138, 180, 248, 0.2);
                color: #9AA0A6;
                padding: 10px 12px;
                border-radius: 10px;
                min-width: 36px;
                max-width: 36px;
            }
            QPushButton#IconBtn:hover {
                border-color: rgba(138, 180, 248, 0.4);
                color: #E8EAED;
                background-color: rgba(138, 180, 248, 0.08);
            }
            QPushButton#IconBtn:pressed {
                background-color: rgba(138, 180, 248, 0.15);
            }

            /* ========== 分割器 ========== */
            QSplitter::handle {
                background-color: rgba(138, 180, 248, 0.1);
                height: 2px;
                margin: 8px 0;
            }
            QSplitter::handle:hover {
                background-color: rgba(138, 180, 248, 0.3);
            }

            /* ========== 滚动条样式 ========== */
            QScrollBar:vertical {
                border: none;
                background: transparent;
                width: 10px;
                margin: 4px;
            }
            QScrollBar::handle:vertical {
                background: rgba(138, 180, 248, 0.2);
                min-height: 30px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(138, 180, 248, 0.4);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent;
            }

            /* ========== 工具提示 ========== */
            QToolTip {
                background-color: #202737;
                color: #E8EAED;
                border: 1px solid rgba(138, 180, 248, 0.2);
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 12px;
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
            self.server_status.setStyleSheet(
                "color:#58D68D; font-size: 9pt; padding: 0 8px; cursor: pointer; text-decoration: underline;")
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

    def _set_ai_busy(self, busy: bool):
        if busy:
            self.btn_ai.setEnabled(False)
            self.btn_ai.setText("生成中...")
            self._ai_busy = True
        else:
            self.btn_ai.setEnabled(True)
            self.btn_ai.setText("🔺发送")
            self._ai_busy = False

    def _confirm_generation(self, role: str) -> bool:
        summary = (f"职业/岗位：{role or '未填写'}\n\n"
                   "请确认这些提示词信息无误，是否继续生成？")
        reply = QMessageBox.question(self, "确认提示词", summary, QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes, )
        return reply == QMessageBox.Yes


class BlogDetailDialog(QDialog):
    def __init__(self, title, date_info, content, parent=None):
        super().__init__(parent)
        self.setWindowTitle("周记详情")
        self.setFixedSize(600, 700)
        self.action = None # "use" or None
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        
        # 样式
        self.setStyleSheet("""
            QDialog { background-color: #1E1E2E; color: #E8EAED; }
            QLabel { color: #E8EAED; }
            QTextBrowser { 
                background-color: #262939; 
                border: 1px solid #363A4D; 
                border-radius: 8px; 
                padding: 16px;
                color: #B0B5C2;
                font-size: 14px;
                line-height: 1.6;
            }
            QPushButton {
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton#Primary { background-color: #4F6BFF; color: white; border: none; }
            QPushButton#Primary:hover { background-color: #3D5CE5; }
            QPushButton#Secondary { background-color: #2D313E; color: #9AA0A6; border: 1px solid #3E4252; }
            QPushButton#Secondary:hover { background-color: #363A4D; color: white; }
        """)

        # 头部
        header_layout = QVBoxLayout()
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("font-size: 20px; font-weight: bold; color: white;")
        title_lbl.setWordWrap(True)
        
        meta_layout = QHBoxLayout()
        date_lbl = QLabel(date_info)
        date_lbl.setStyleSheet("color: #717684; font-size: 12px;")
        meta_layout.addWidget(date_lbl)
        meta_layout.addStretch()
        
        header_layout.addWidget(title_lbl)
        header_layout.addLayout(meta_layout)
        
        layout.addLayout(header_layout)
        
        # 内容
        self.browser = QTextBrowser()
        # 简单的 HTML 渲染
        html = content.replace('\n', '<br>')
        self.browser.setHtml(html)
        layout.addWidget(self.browser)
        
        # 底部按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        btn_copy = QPushButton("复制内容")
        btn_copy.setObjectName("Secondary")
        btn_copy.clicked.connect(self._copy_content)
        
        btn_use = QPushButton("✏️ 编辑引用")
        btn_use.setObjectName("Primary")
        btn_use.setToolTip("将此内容填入主编辑器")
        btn_use.clicked.connect(self._use_content)
        
        btn_layout.addWidget(btn_copy)
        btn_layout.addWidget(btn_use)
        
        layout.addLayout(btn_layout)

    def _copy_content(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.browser.toPlainText())
        ToastManager.instance().show("内容已复制到剪贴板", "success")

    def _use_content(self):
        self.action = "use"
        self.accept()
