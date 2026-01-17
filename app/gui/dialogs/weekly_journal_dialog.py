import logging

from PySide6.QtCore import Qt, QThread, Signal, QTimer, QPoint
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QTextEdit,
    QPushButton,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QWidget,
    QFrame,
    QLineEdit,
    QMessageBox,
    QComboBox,
    QScrollArea,
    QSizePolicy,
    QSplitter,
)

from app.apis.xybsyw import login, get_plan, load_blog_year, load_blog_date, submit_blog, handle_invalid_session, \
    xyb_completion
from app.config.common import SYSTEM_PROMPT, CONFIG_FILE, PROJECT_NAME
from app.gui.components.toast import ToastManager
from app.gui.dialogs.journal_auth_dialog import JournalAuthDialog
from app.utils.files import load_journal_history, append_journal_entry, read_config, clear_journal_history
from app.utils.model_client import ModelConfigurationError


class AIGenerationThread(QThread):
    """AI生成周记的异步线程"""
    delta_signal = Signal(str)
    finished_signal = Signal(str)
    error_signal = Signal(str, str)  # error_type, message

    def __init__(self, args, config, prompt, system_prompt):
        super().__init__()
        self.args = args
        self.config = config
        self.prompt = prompt
        self.system_prompt = system_prompt

    def run(self):
        try:
            def on_delta(delta: str):
                self.delta_signal.emit(delta)

            content = xyb_completion(
                args=self.args,
                config=self.config,
                prompt=self.prompt,
                on_delta=on_delta
            )

            self.finished_signal.emit(content)
        except ModelConfigurationError as e:
            self.error_signal.emit("config", str(e))
        except Exception as e:
            self.error_signal.emit("error", f"调用模型失败：{e}")


class CustomConfirmDialog(QDialog):
    """自定义样式的确认对话框"""
    def __init__(self, parent, title, text, confirm_text="确认", is_danger=False):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedWidth(380)
        # 移除问号图标，使用纯净样式
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self._setup_ui(text, confirm_text, is_danger)

    def _setup_ui(self, text, confirm_text, is_danger):
        self.setStyleSheet("""
            QDialog { background-color: #1E1E1E; }
            QLabel { color: #E8EAED; font-size: 14px; line-height: 1.5; }
            QPushButton { 
                padding: 8px 16px; border-radius: 6px; font-size: 13px; font-weight: 500;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setSpacing(24)
        layout.setContentsMargins(24, 24, 24, 24)
        
        msg_label = QLabel(text)
        msg_label.setWordWrap(True)
        # 稍微增加字间距
        msg_layout = QHBoxLayout()
        msg_layout.addWidget(msg_label)
        layout.addLayout(msg_layout)
        
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        btn_layout.addStretch()
        
        btn_cancel = QPushButton("取消")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setStyleSheet("""
            background-color: transparent; border: 1px solid #3E3E3E; color: #CCCCCC;
        """)
        btn_cancel.clicked.connect(self.reject)
        
        btn_confirm = QPushButton(confirm_text)
        btn_confirm.setCursor(Qt.PointingHandCursor)
        if is_danger:
            btn_confirm.setStyleSheet("QPushButton { background-color: #EF4444; color: white; border: none; } QPushButton:hover { background-color: #DC2626; }")
        else:
            btn_confirm.setStyleSheet("QPushButton { background-color: #2563EB; color: white; border: none; } QPushButton:hover { background-color: #1D4ED8; }")
            
        btn_confirm.clicked.connect(self.accept)
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_confirm)
        
        layout.addLayout(btn_layout)
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


class SubmitJournalThread(QThread):
    """提交周记的异步线程"""
    finished_signal = Signal(dict)
    error_signal = Signal(str)

    def __init__(self, args, config, blog_title, blog_body, start_date, end_date, blog_open_type, trainee_id):
        super().__init__()
        self.args = args
        self.config = config
        self.blog_title = blog_title
        self.blog_body = blog_body
        self.start_date = start_date
        self.end_date = end_date
        self.blog_open_type = blog_open_type
        self.trainee_id = trainee_id
        self.content = blog_body

    def run(self):
        try:
            from app.apis.xybsyw import submit_blog
            result = submit_blog(
                self.args, self.config,
                self.blog_title, self.blog_body,
                self.start_date, self.end_date,
                self.blog_open_type, self.trainee_id
            )
            self.finished_signal.emit(result)
        except Exception as e:
            self.error_signal.emit(str(e))



class FloatingActionBar(QFrame):
    def __init__(self, parent=None, callback_copy=None, callback_submit=None):
        super().__init__(parent)
        self.callback_copy = callback_copy
        self.callback_submit = callback_submit
        self.current_text = ""
        self.hide_timer = QTimer(self)
        self.hide_timer.setInterval(100)
        self.hide_timer.timeout.connect(self.hide)
        self.hide() # 确保初始隐藏
        self._init_ui()
        
    def _init_ui(self):
        self.setObjectName("FloatingActionBar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)
        self.setStyleSheet("""
            QFrame#FloatingActionBar {
                background-color: rgba(40, 44, 52, 0.95);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
            }
        """)
        
        self.btn_copy = QPushButton("复制")
        self._style_btn(self.btn_copy)
        self.btn_copy.clicked.connect(lambda: self.callback_copy(self.current_text))
        layout.addWidget(self.btn_copy)
        
        # 分割线
        self.divider = QFrame()
        self.divider.setFixedSize(1, 14)
        self.divider.setStyleSheet("background-color: rgba(255, 255, 255, 0.2);")
        layout.addWidget(self.divider)
        
        self.btn_submit = QPushButton("📝 提交为周记")
        self._style_btn(self.btn_submit)
        self.btn_submit.clicked.connect(lambda: self.callback_submit(self.current_text))
        layout.addWidget(self.btn_submit)
        
    def _style_btn(self, btn):
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedHeight(24)
        btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #BDC1C6;
                border: none;
                padding: 0 8px;
                font-size: 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
                color: #FFFFFF;
            }
        """)

    def show_for(self, target_widget, text, show_submit=False):
        self.hide_timer.stop()
        self.current_text = text
        self.btn_submit.setVisible(show_submit)
        self.divider.setVisible(show_submit)
        self.adjustSize()
        
        # Calculate position: Bottom Left of target widget, mapped to parent dialog
        target_pos = target_widget.mapTo(self.parent(), QPoint(0, 0))
        x = target_pos.x()
        y = target_pos.y() + target_widget.height() + 4
        
        self.move(x, y)
        self.show()
        self.raise_()
        
    def enterEvent(self, event):
        self.hide_timer.stop()
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        self.hide_timer.start()
        super().leaveEvent(event)
        
    def schedule_hide(self):
        self.hide_timer.start()


class AIMessageBubble(QFrame):
    def __init__(self, parent_dialog, initial_text=""):
        super().__init__()
        self.parent_dialog = parent_dialog
        self.text = initial_text
        self.setObjectName("AIMessage")
        self._init_ui()
        
    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignTop) # 顶部对齐
        
        ai_icon = QLabel("✨")
        ai_icon.setObjectName("AIIcon")
        ai_icon.setAlignment(Qt.AlignTop)
        ai_icon.setContentsMargins(0, 4, 0, 0) # 微调图标位置
        layout.addWidget(ai_icon)
        
        # 使用 TextEdit 代替 Label 以支持 Markdown 和 完美自动换行
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setFrameShape(QFrame.NoFrame)
        self.text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.text_edit.setObjectName("AIMessageText")
        self.text_edit.document().setDocumentMargin(0) # 去除默认边距
        
        self.text_edit.setMarkdown(self.text)
        self.text_edit.setMaximumWidth(550)
        self.text_edit.setMinimumWidth(50)
        
        # 样式 - 确保背景透明，使用 label 样式
        self.text_edit.setStyleSheet("""
            QTextEdit {
                background-color: #2A2D3E;
                color: #E8EAED;
                font-size: 14px;
                line-height: 1.5;
                padding: 10px 14px; /* 垂直10，水平14 */
                border: 1px solid #363B4C;
                border-radius: 16px;
                border-bottom-left-radius: 2px;
            }
        """)
        
        layout.addWidget(self.text_edit)
        self._adjust_height()
        
    def setText(self, text):
        self.text = text
        self.text_edit.setMarkdown(text)
        self._adjust_height()
        
    def _adjust_height(self):
        # 自动调整高度
        current_width = self.text_edit.width()
        if current_width <= 0: current_width = 550 # 默认宽度
        
        # 减去 Horizontal Padding (14px * 2 = 28) 和 边框 余量
        # 保持一点额外空间防止换行抖动
        text_width = current_width - 30 
        if text_width < 10: text_width = 10
        
        doc = self.text_edit.document()
        doc.setTextWidth(text_width) 
        h = doc.size().height()
        self.text_edit.setFixedHeight(int(h + 20)) # Vertical Padding (10*2=20)
        
    def resizeEvent(self, event):
        self._adjust_height()
        super().resizeEvent(event)
        
    def enterEvent(self, event):
        if hasattr(self.parent_dialog, 'floating_bar'):
            self.parent_dialog.floating_bar.show_for(self.text_edit, self.text, show_submit=True)
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        if hasattr(self.parent_dialog, 'floating_bar'):
            self.parent_dialog.floating_bar.schedule_hide()
        super().leaveEvent(event)

    def wheelEvent(self, event):
        # 禁用气泡内的滚轮滚动，并将事件忽略以便传递给父级（ScrollArea）
        event.ignore()


class UserMessageBubble(QFrame):
    def __init__(self, parent_dialog, text):
        super().__init__()
        self.parent_dialog = parent_dialog
        self.text = text
        self._init_ui()
        
    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch()
        layout.setAlignment(Qt.AlignTop)
        
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setFrameShape(QFrame.NoFrame)
        self.text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.text_edit.setObjectName("UserMessageText")
        self.text_edit.document().setDocumentMargin(0) # 去除默认边距
        self.text_edit.setPlainText(self.text)
        self.text_edit.setMaximumWidth(550)
        self.text_edit.setMinimumWidth(20)
        
        self.text_edit.setStyleSheet("""
            QTextEdit {
                background-color: #2563EB;
                color: #FFFFFF;
                font-size: 14px;
                padding: 10px 14px; /* 垂直10，水平14 */
                border-radius: 16px;
                border-bottom-right-radius: 2px;
                border: none;
            }
        """)
        
        layout.addWidget(self.text_edit)
        self._adjust_height()
        
    def _adjust_height(self):
        doc = self.text_edit.document()
        
        # 1. 计算理想宽度
        doc.setTextWidth(-1) # 不换行
        ideal_width = doc.idealWidth()
        
        # 2. 确定气泡宽度 (Horizontal Padding 28 + 额外 2)
        bubble_width = ideal_width + 30
        bubble_width = max(40, min(bubble_width, 550)) # 最小宽度减小到40
        
        self.text_edit.setFixedWidth(int(bubble_width))
        
        # 3. 根据实际宽度计算高度 (减去 Horizontal Padding)
        doc.setTextWidth(bubble_width - 28)
        h = doc.size().height()
        self.text_edit.setFixedHeight(int(h + 20)) # Vertical Padding 20
        
    def resizeEvent(self, event):
        self._adjust_height()
        super().resizeEvent(event)
        
    def enterEvent(self, event):
        if hasattr(self.parent_dialog, 'floating_bar'):
            self.parent_dialog.floating_bar.show_for(self.text_edit, self.text, show_submit=False)
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        if hasattr(self.parent_dialog, 'floating_bar'):
            self.parent_dialog.floating_bar.schedule_hide()
        super().leaveEvent(event)

    def wheelEvent(self, event):
        event.ignore()

    def wheelEvent(self, event):
        event.ignore()


class WeeklyJournalDialog(QDialog):
    def __init__(self, model_config: dict, args, parent=None):
        super().__init__(parent)
        self.setWindowTitle("周记提交")

        # 自适应屏幕大小
        self._setup_window_geometry()

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
        self._refresh_timer = QTimer()
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self._enable_refresh_buttons)
        self._refresh_cooldown = 2000  # 2秒冷却时间
        self._refresh_buttons_enabled = True
        self._setup_styles()
        self._setup_ui()
        self._load_history()
        # 初始化编辑器高度
        QTimer.singleShot(0, self._adjust_editor_height)
        # 自动加载年月数据
        QTimer.singleShot(100, self._load_year_month_data)

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
        self.submitted_widget.itemDoubleClicked.connect(self._fill_from_history)
        sidebar_layout.addWidget(self.submitted_widget)

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
        self.year_combo = QComboBox()
        self.year_combo.setVisible(False)
        self.year_combo.currentIndexChanged.connect(self._on_year_changed)

        self.month_combo = QComboBox()
        self.month_combo.setVisible(False)
        self.month_combo.currentIndexChanged.connect(self._on_month_changed)

        self.week_combo = QComboBox()
        self.week_combo.setVisible(False)

        self.permission_combo = QComboBox()
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
        self.splitter.setHandleWidth(1) # 细线
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
        from PySide6.QtGui import QKeyEvent
        
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
        self.chat_messages_layout.insertWidget(
            self.chat_messages_layout.count() - 1, bubble, 0, Qt.AlignRight
        )
        
        # 滚动到底部
        QTimer.singleShot(50, self._scroll_chat_to_bottom)

    def _add_ai_message(self, initial_text: str = ""):
        """添加 AI 消息到聊天区域，返回消息对象用于流式更新"""
        bubble = AIMessageBubble(self, initial_text)
        
        # 在 stretch 之前插入消息，左对齐
        self.chat_messages_layout.insertWidget(
            self.chat_messages_layout.count() - 1, bubble, 0, Qt.AlignLeft
        )
        
        # 滚动到底部
        QTimer.singleShot(50, self._scroll_chat_to_bottom)
        
        return bubble
        
    def _copy_text_to_clipboard(self, text):
        """复制文本到剪贴板"""
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        ToastManager.instance().show("内容已复制", "success")
    
    def submit_journal_from_text(self, content):
        """提交周记"""
        if not content:
            ToastManager.instance().show("内容为空", "warning")
            return
            
        if not hasattr(self, 'trainee_id') or not self.trainee_id:
            ToastManager.instance().show("正在加载数据，请稍候...", "info")
            if hasattr(self, '_load_data_thread') and self._load_data_thread and self._load_data_thread.isRunning():
                 return
            self._load_year_month_data()
            return
            
        if self.week_combo.count() == 0:
            ToastManager.instance().show("未加载周次信息，请等待数据加载", "warning")
            return
            
        week_data = self.week_combo.currentData()
        # 如果没有选中，选第一个
        if not week_data and self.week_combo.count() > 0:
             self.week_combo.setCurrentIndex(0)
             week_data = self.week_combo.currentData()
             
        if not week_data:
             ToastManager.instance().show("无法获取周次信息", "error")
             return
             
        start_date = week_data.get('startDate')
        end_date = week_data.get('endDate')
        
        # 处理标题（第一行作为标题，最多20字）
        title = content.strip().split('\n')[0][:20] if content else "实习周记"
        permission = 0 # 默认 仅老师和同学可见 (我们在UI里虽然有combo但是可能没变)
        if hasattr(self, 'permission_combo') and self.permission_combo.count() > 0:
             permission = self.permission_combo.currentData()
        
        reply = QMessageBox.question(
            self,
            "确认提交",
            f"周次：{start_date} 至 {end_date}\n标题：{title}\n\n确认提交为本周周记？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        
        if reply == QMessageBox.Yes:
            self._submit_thread = SubmitJournalThread(
                self.args, self.config,
                title, content, start_date, end_date,
                permission, self.trainee_id
            )
            self._submit_thread.finished_signal.connect(self._on_submit_finished)
            self._submit_thread.error_signal.connect(self._on_submit_error)
            self._submit_thread.start()
            ToastManager.instance().show("正在提交周记...", "info")

    def _on_submit_finished(self, result):
        ToastManager.instance().show("🎉 周记提交成功！", "success")
        if hasattr(self, '_submit_thread'):
            append_journal_entry("submitted", self._submit_thread.content)
            self._load_history()

    def _on_submit_error(self, error):
        ToastManager.instance().show(f"提交失败: {error}", "error")
    
    def _scroll_chat_to_bottom(self):
        """滚动聊天区域到底部"""
        scrollbar = self.chat_scroll.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

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
        bubble_y = bubble.y() # 假如 chat_messages 是 ScrollArea 的 widget，pos() 就是相对坐标
        
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
            
        if not self._show_custom_confirm(
            "确认清空", 
            "确定要清空所有 AI 生成的历史记录吗？\n此操作将清除左侧列表中的所有记录。", 
            confirm_text="🗑️ 清空",
            is_danger=True
        ):
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
        self._populate_list(self.submitted_widget, data.get("submitted", []))

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
        self._ai_thread = AIGenerationThread(self.args, self.config['input'],
                                             prompt_context, SYSTEM_PROMPT)
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
        self.args = login_args
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
            if not self.args or not self.trainee_id:
                return
            self.year_data = load_blog_year(self.args, self.config['input'])
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
            self.week_data = load_blog_date(self.args, self.config['input'], year_id, month_id)
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

        # 获取内容
        full_content = self.editor.toPlainText().strip()
        if not full_content:
            ToastManager.instance().show("请先输入或生成周记内容", "info")
            return

        # 从内容解析标题和正文
        lines = full_content.split('\n')
        first_line = lines[0].strip()

        # 如果第一行看起来像标题（较短且不以标点结尾），则使用第一行作为标题
        if len(first_line) <= 50 and not first_line.endswith(('。', '！', '？', '.', '!', '?', ',')):
            title = first_line
            content = '\n'.join(lines[1:]).strip() if len(lines) > 1 else first_line
        else:
            # 否则自动生成标题
            week_item = self.week_combo.currentData()
            if week_item:
                week_num = week_item.get('week', '')
                title = f"第{week_num}周实习周记"
            else:
                title = "实习周记"
            content = full_content

        # 检查是否选择了周
        week_item = self.week_combo.currentData()
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
                blog_id = submit_blog(
                    args=self.args,
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

        # 1. 弹出配置与确认对话框
        confirmed, final_title, final_content = self._show_submit_config_dialog(content)
        if not confirmed:
            return

        week_id = self.week_combo.currentData()
        start_date = self.week_combo.itemData(self.week_combo.currentIndex(), Qt.UserRole + 1)
        end_date = self.week_combo.itemData(self.week_combo.currentIndex(), Qt.UserRole + 2)
        permission = self.permission_combo.currentData()

        # 2. 启动提交线程
        self.btn_ai.setEnabled(False)
        self._submit_thread = SubmitJournalThread(
            final_content, 
            final_title, 
            start_date, 
            end_date, 
            permission, 
            week_id
        )
        self._submit_thread.finished_signal.connect(self._on_submit_finished)
        self._submit_thread.error_signal.connect(self._on_submit_error)
        self._submit_thread.start()
        
    def _on_submit_finished(self, msg):
        self.btn_ai.setEnabled(True)
        ToastManager.instance().show(msg, "success")
        append_journal_entry("submitted", self._submit_thread.content) # Record submission
        self._load_history()
        self._submit_thread = None
        
    def _on_submit_error(self, err):
        self.btn_ai.setEnabled(True)
        ToastManager.instance().show(f"提交失败: {err}", "error")
        self._submit_thread = None

    def _show_submit_config_dialog(self, content):
        """显示提交配置对话框"""
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

        form_layout = QHBoxLayout() # 使用水平布局排列配置项
        form_layout.addWidget(QLabel("年份:"))
        form_layout.addWidget(self.year_combo)
        form_layout.addWidget(QLabel("月份:"))
        form_layout.addWidget(self.month_combo)
        form_layout.addStretch()
        
        form_layout2 = QHBoxLayout()
        form_layout2.addWidget(QLabel("周次:"))
        form_layout2.addWidget(self.week_combo, 1) # 周次较长
        form_layout2.addWidget(QLabel("权限:"))
        form_layout2.addWidget(self.permission_combo)
        
        layout.addLayout(form_layout)
        layout.addLayout(form_layout2)
        
        # 1.5 标题 (可编辑)
        title_layout = QHBoxLayout()
        title_layout.addWidget(QLabel("标题:"))
        title_edit = QLineEdit()
        # 默认标题
        current_week_item = self.week_combo.currentData()
        if current_week_item:
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
        """)
        
        btn_cancel.clicked.connect(dialog.reject)
        btn_submit.clicked.connect(dialog.accept)
        
        btn_box.addStretch()
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_submit)
        layout.addLayout(btn_box)
        
        # 执行对话框
        result = dialog.exec()
        
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
        
        if result == QDialog.Accepted:
            return True, title_edit.text().strip(), content_edit.toPlainText()
        return False, None, None

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
        if not self._show_custom_confirm(
            "确认清空", 
            "确定要清空当前对话内容吗？\n此操作无法撤销。", 
            confirm_text="🗑️ 清空",
            is_danger=True
        ):
            return

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
            if not self._ai_busy:
                QApplication.setOverrideCursor(Qt.WaitCursor)
            self._ai_busy = True
        else:
            self.btn_ai.setEnabled(True)
            self.btn_ai.setText("🔺发送")
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
