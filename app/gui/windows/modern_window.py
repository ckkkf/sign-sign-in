import logging
import os
import random
import re
import subprocess
import threading
import time
import ctypes
from datetime import datetime, timedelta

from PySide6.QtCore import Qt, QUrl, QTimer
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QFrame, QVBoxLayout, QLabel, QGridLayout, QPushButton, \
    QButtonGroup, QRadioButton, QProgressBar, QSizePolicy, QMessageBox, QApplication, QTextEdit, QDialog, QFileDialog

from app.config.common import QQ_GROUP, PROJECT_VERSION, CONFIG_FILE, MITM_PROXY, PROJECT_NAME, PROJECT_GITHUB
from app.gui.components.log_viewer import QTextEditLogger
from app.gui.components.toast import ToastManager
from app.gui.dialogs.dialogs.auto_clock_config_dialog import AutoClockConfigDialog
from app.gui.dialogs.dialogs.config_dialog import ConfigDialog
from app.gui.dialogs.feedback_dialog import FeedbackDialog
from app.gui.dialogs.image_manager_dialog import ImageManagerDialog
from app.gui.dialogs.photo_sign_dialog import PhotoSignDialog
from app.gui.dialogs.sponsor_dialog import SponsorSubmitDialog
from app.gui.dialogs.update_dialog import UpdateDialog
from app.gui.dialogs.weekly_journal.WeeklyJournalDialog import WeeklyJournalDialog
from app.mitm.service import MitmService
from app.utils.commands import get_net_io, bash, get_network_type, get_local_ip, get_system_proxy, check_port_listening, \
    check_cert
from app.utils.files import validate_config, read_config
from app.utils.pushplus import notify_pushplus
from app.workers.monitor_thread import MonitorThread
from app.workers.sign_task import SignTaskThread, GetCodeAndSessionThread
from app.workers.update_worker import UpdateCheckWorker


class ModernWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle(f"{PROJECT_NAME} {PROJECT_VERSION} - 实习打卡助手")
        self.resize(900, 540)  # 进一步收紧高度
        self.is_running = False
        self.is_getting_code = False
        self.photo_image_path = None
        self.current_run_source = "manual"
        self.auto_clock_enabled = False
        self.auto_clock_tasks = []
        self.auto_clock_last_trigger = {}
        self.auto_clock_next_trigger = {}
        self.auto_clock_random_minutes = 0
        self.auto_clock_timer = QTimer(self)
        self.auto_clock_timer.setInterval(30 * 1000)
        self.auto_clock_timer.timeout.connect(self._on_auto_clock_tick)
        self.btn_get_code_original_style = None  # 保存按钮原始样式
        self.weekly_journal_dialog = None  # 周记对话框实例

        # 自动守护：monitor 会调用 mitm.start()
        self.mitm = MitmService()
        self.monitor = MonitorThread(self.mitm)
        self.monitor.data_signal.connect(self.update_status)
        self.monitor.start()

        self.setup_style()
        self.init_ui()
        self._load_auto_clock_settings()

    def init_ui(self):
        main = QWidget()
        self.setCentralWidget(main)
        hbox = QHBoxLayout(main)
        hbox.setSpacing(0)
        hbox.setContentsMargins(0, 0, 0, 0)

        # ------------------------- Left Panel -------------------------
        left = QFrame()
        left.setObjectName("LeftPanel")
        l_vbox = QVBoxLayout(left)
        l_vbox.setContentsMargins(15, 20, 15, 20)
        l_vbox.setSpacing(5)

        title = QLabel(PROJECT_NAME)
        title.setObjectName("AppTitle")
        l_vbox.addWidget(title)
        sub = QLabel("—— 自动化实习签到系统")
        sub.setObjectName("AppSubTitle")
        l_vbox.addWidget(sub)

        # QQ Group (click-to-copy)
        qq_lbl = QLabel(f"QQ交流群: {QQ_GROUP} (点我复制)")
        qq_lbl.setStyleSheet("""
            color: #5865F2; 
            font-weight: bold; 
            font-size: 10pt; 
        """)
        qq_lbl.setCursor(Qt.PointingHandCursor)  # 小手指
        qq_lbl.setTextFormat(Qt.RichText)
        qq_lbl.setTextInteractionFlags(Qt.TextBrowserInteraction)
        qq_lbl.mousePressEvent = lambda e: self.copy_log()

        l_vbox.addWidget(qq_lbl)

        # ------------------------- Status Box -------------------------
        # 区域标签
        label = QLabel("状态域")
        label.setObjectName("SectionLabel")
        l_vbox.addWidget(label)

        mon_box = QFrame()
        mon_box.setObjectName("MonitorBox")
        mon_grid = QGridLayout(mon_box)
        mon_grid.setContentsMargins(10, 10, 10, 10)
        mon_grid.setSpacing(5)
        # Set Equal Column Width
        mon_grid.setColumnStretch(0, 1)
        mon_grid.setColumnStretch(1, 1)

        self.lbls = {}
        keys = ["time", "pid", "net", "speed", "proxy", "mitm", "cert", "ip", "session"]
        for k in keys:
            l = QLabel("-")
            l.setObjectName("StatusLabel")
            l.setTextFormat(Qt.RichText)
            self.lbls[k] = l

        mon_grid.addWidget(self.lbls['time'], 0, 0)
        mon_grid.addWidget(self.lbls['pid'], 0, 1)
        mon_grid.addWidget(self.lbls['net'], 1, 0)
        mon_grid.addWidget(self.lbls['speed'], 1, 1)
        mon_grid.addWidget(self.lbls['proxy'], 2, 0)
        mon_grid.addWidget(self.lbls['cert'], 2, 1)
        mon_grid.addWidget(self.lbls['mitm'], 3, 0)
        mon_grid.addWidget(self.lbls['ip'], 3, 1)
        mon_grid.addWidget(self.lbls['session'], 4, 0, 1, 2)  # 跨两列

        l_vbox.addWidget(mon_box)

        # ------------------------- Tools -------------------------
        # 区域标签
        label = QLabel("工具箱")
        label.setObjectName("SectionLabel")
        l_vbox.addWidget(label)

        t_grid = QGridLayout()
        t_grid.setSpacing(8)
        tools = [
            ("🔗 系统代理", lambda: subprocess.Popen('rundll32.exe shell32.dll,Control_RunDLL inetcpl.cpl,,4', shell=True, creationflags=subprocess.CREATE_NO_WINDOW)),
            ("🔒 证书管理", lambda: subprocess.Popen('certmgr.msc', shell=True, creationflags=subprocess.CREATE_NO_WINDOW)),
            ("📄 编辑配置", self.open_config),
            ("🔁 刷新DNS", self.flush_dns),
            ("📤 发送反馈", self.show_feedback),
            ("💻 打开CMD", lambda: subprocess.Popen(["cmd.exe"], creationflags=subprocess.CREATE_NEW_CONSOLE)),
            ("🖼 图片管理", self.open_image_manager),
            ("🔄 检查更新", self.check_update),
        ]
        for i, (name, func) in enumerate(tools):
            b = QPushButton(name)
            b.setObjectName("ToolBtn")
            b.clicked.connect(func)
            t_grid.addWidget(b, i // 4, i % 4)

        btn_journal = QPushButton("✨ AI 与 周记（测试）")
        btn_journal.setObjectName("ToolBtn")
        btn_journal.clicked.connect(self.open_weekly_journal)
        t_grid.addWidget(btn_journal, 2, 0, 1, 2)

        btn_auto_clock = QPushButton("定时打卡配置")
        btn_auto_clock.setObjectName("ToolBtn")
        btn_auto_clock.clicked.connect(self.open_auto_clock_config)
        t_grid.addWidget(btn_auto_clock, 2, 2, 1, 2)
        l_vbox.addLayout(t_grid)

        # ------------------------- Mode -------------------------
        label = QLabel("执行操作（拍照签到签退经纬度不准会导致外勤）")
        label.setObjectName("SectionLabel")
        l_vbox.addWidget(label)

        self.grp = QButtonGroup(self)

        rb_in = QRadioButton("普通签到")
        rb_in.setChecked(True)
        self.grp.addButton(rb_in, 0)

        rb_out = QRadioButton("普通签退")
        self.grp.addButton(rb_out, 1)

        rb_img_in = QRadioButton("拍照签到")
        self.grp.addButton(rb_img_in, 2)

        rb_img_out = QRadioButton("拍照签退")
        self.grp.addButton(rb_img_out, 3)

        # 第一行：签到 + 签退
        mode_row1 = QHBoxLayout()
        mode_row1.setSpacing(10)
        mode_row1.addWidget(rb_in)
        mode_row1.addWidget(rb_out)
        mode_row1.addWidget(rb_img_in)
        mode_row1.addWidget(rb_img_out)
        mode_row1.addStretch()
        l_vbox.addLayout(mode_row1)

        # ------------------------- Progress -------------------------
        self.prog = QProgressBar()
        self.prog.setTextVisible(False)
        self.prog.setRange(0, 0)
        self.prog.hide()
        l_vbox.addWidget(self.prog)

        # ------------------------- Get Code and Session Button -------------------------
        btn_row1 = QHBoxLayout()
        self.btn_get_code = QPushButton("获取code")
        self.btn_get_code.setObjectName("BtnGetCode")
        self.btn_get_code.clicked.connect(self.get_code_and_session)
        # 保存原始样式
        # 保存原始样式（置空，使用 setup_style 中的 ID 样式）
        self.btn_get_code_original_style = ""
        btn_row1.addWidget(self.btn_get_code)
        btn_row1.setContentsMargins(0, 10, 0, 10)  # 左 上 右 下
        btn_row1.setSpacing(5)

        l_vbox.addLayout(btn_row1)

        # ------------------------- Main Buttons -------------------------
        self.btn_run = QPushButton("开始执行")
        self.btn_run.setObjectName("BtnStart")
        self.btn_run.clicked.connect(self.toggle)
        btn_row1.addWidget(self.btn_run)

        btn_row2 = QHBoxLayout()

        btn_don = QPushButton("支持作者")
        btn_don.setObjectName("BtnDonate")
        btn_don.clicked.connect(self.show_support)
        btn_row2.addWidget(btn_don)

        btn_git = QPushButton("开源仓库")
        btn_git.setObjectName("BtnGit")
        btn_git.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(PROJECT_GITHUB)))
        btn_row2.addWidget(btn_git)

        l_vbox.addLayout(btn_row2)

        # ------------------------- Right Panel -------------------------
        right = QFrame()
        right.setObjectName("RightPanel")
        r_vbox = QVBoxLayout(right)
        r_vbox.setContentsMargins(0, 0, 0, 0)
        r_vbox.setSpacing(0)
        right.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        right.setMinimumWidth(520)
        right.setMaximumWidth(520)

        # ------------------------- Header -------------------------
        head = QWidget()
        head.setStyleSheet("background:#333;")
        hh = QHBoxLayout(head)
        hh.setContentsMargins(10, 5, 10, 5)
        hh.addWidget(QLabel(" >_ SYSTEM LOG", objectName="TermHeader"))
        hh.addStretch()

        btn_export = QPushButton("📤 导出日志")
        btn_export.setObjectName("LogActionBtn")
        btn_export.setCursor(Qt.PointingHandCursor)
        btn_export.clicked.connect(self.export_log)
        btn_export.setToolTip("导出日志到文件")
        hh.addWidget(btn_export)

        btn_copy = QPushButton("⧉ 复制日志")
        btn_copy.setObjectName("LogActionBtn")
        btn_copy.setCursor(Qt.PointingHandCursor)
        btn_copy.clicked.connect(self.copy_log)
        btn_copy.setToolTip("复制全部日志到剪贴板")
        btn_clear = QPushButton("🗑 清空日志")
        btn_clear.setObjectName("LogActionBtn")
        btn_clear.clicked.connect(lambda: self.clear_log())
        btn_clear.setCursor(Qt.PointingHandCursor)
        btn_clear.setToolTip("清空当前日志显示内容")
        hh.addWidget(btn_copy)
        hh.addWidget(btn_clear)
        r_vbox.addWidget(head)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setObjectName("LogView")
        r_vbox.addWidget(self.log)

        hbox.addWidget(left, 35)
        hbox.addWidget(right, 65)

        self.log_h = QTextEditLogger(self.log)
        self.log_h.setFormatter(logging.Formatter('%(asctime)s - %(message)s', "%H:%M:%S"))
        logging.getLogger().addHandler(self.log_h)

        # 初始化JSESSIONID显示
        self._update_session_display()

        # 启动时自动检查更新（延迟2秒，避免阻塞启动）
        from PySide6.QtCore import QTimer
        QTimer.singleShot(2000, self.check_update_silent)

    def clear_log(self):
        reply = QMessageBox.question(
            self,
            "确认操作",
            "确定要清空日志吗？此操作不可恢复！",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.log.clear()

    def setup_style(self):
        self.setStyleSheet("""
            QMainWindow { background: #0F111A; }
            #LeftPanel {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #151928, stop:1 #0E111C);
                border-right: 1px solid #1F2233;
            }
            #RightPanel {
                background: #11131D;
                border-left: 1px solid #1A1D2B;
            }
            #AppTitle {
                font-family: "Segoe UI Semibold";
                font-size: 20pt;
                color: #F2F4FF;
            }
            #AppSubTitle {
                font-size: 10pt;
                color: #7D86A7;
            }
            #MonitorBox {
                background: #151826;
                border-radius: 12px;
                border: 1px solid #1E2235;
                padding: 4px;
            }
            #StatusLabel {
                color: #D7DBFF;
                font-family: Consolas;
                font-size: 9.5pt;
            }
            #SectionLabel {
                color: #6C7395;
                font-weight: bold;
                margin-top: 8px;
                letter-spacing: 1px;
            }
            #ToolBtn {
                background: #191B2A;
                color: #D0D5FF;
                border: 1px solid #22263A;
                padding: 6px;
                border-radius: 10px;
                font-weight: 600;
            }
            #ToolBtn:hover {
                border-color: #4F6BFF;
                color: white;
            }
            QRadioButton {
                color: #9EA4C4;
                font-size: 10pt;
            }
            QRadioButton:checked {
                color: #F4F6FF;
                font-weight: bold;
            }
            QRadioButton::indicator {
                width: 16px;
                height: 16px;
                border-radius: 8px;
                border: 2px solid #4F5675;
                background: transparent;
            }
            QRadioButton::indicator:hover { border-color: #7C84AA; }
            QRadioButton::indicator:checked {
                background: #5C7CFF;
                border: 2px solid #5C7CFF;
            }
            #BtnGetCode {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #28A745, stop:1 #20C997);
                color: white;
                border-radius: 20px;
                padding: 10px;
                font-size: 12pt;
                font-weight: bold;
                border: 2px solid transparent;
            }
            #BtnGetCode:hover {
                border-color: #4F6BFF;
            }
            #BtnStart {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3D7CFF, stop:1 #7A4DFF);
                color: white;
                border-radius: 20px;
                padding: 10px;
                font-size: 12pt;
                font-weight: bold;
                border: 2px solid transparent;
            }
            #BtnStart:hover {
                border-color: #4F6BFF;
            }
            #BtnDonate, #BtnGit {
                background: transparent;
                color: #7E86A8;
                border: 1px solid #2F3450;
                border-radius: 18px;
                padding: 6px 14px;
                font-weight: bold;
            }
            #BtnDonate:hover, #BtnGit:hover {
                border-color: #5865F2;
                color: #F5F7FF;
            }
            #BtnJournal {
                background: rgba(92, 124, 255, 0.15);
                color: #B8C1FF;
                border-radius: 8px;
                padding: 8px;
                font-weight: bold;
                border: 1px dashed rgba(92,124,255,0.4);
            }
            #BtnJournal:hover {
                background: rgba(92, 124, 255, 0.25);
                color: white;
            }
            #TermHeader { color: #AAB1D6; font-weight: bold;}
            #LogView {
                background: #08090F;
                border: none;
                color: #C4C9EF;
                font-family: Consolas;
                font-size: 9.5pt;
                padding: 12px;
            }
            #LogActionBtn {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1B2035, stop:1 #2B3558);
                color: #F1F3FF;
                border: 1px solid #2F3654;
                padding: 6px 14px;
                border-radius: 16px;
                margin-left: 5px;
                font-weight: 600;
                letter-spacing: 0.5px;
            }
            #LogActionBtn:hover { border-color: #7A89FF; color: white; }
            QProgressBar {
                background: #1A1D2C;
                border: none;
                height: 4px;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4FACFF, stop:1 #9B59FF);
            }
        """)

    def update_status_v1(self):
        self.lbls['time'].setText(f"🕔 当前时间: <span style='color:#FFF'>{datetime.now().strftime('%H:%M:%S')}</span>")
        self.lbls['pid'].setText(f"🟢 PID: <span style='color:#58D68D'>{os.getpid()}</span>")

        ntype = get_network_type()
        self.lbls['net'].setText(f"📶 网络: <span style='color:#58D68D'>{ntype}</span>")

        cur_io = get_net_io()
        now = time.time()
        if self.last_io and cur_io:
            dt = now - self.last_time
            if dt > 0:
                d = (cur_io.bytes_recv - self.last_io.bytes_recv) / 1024 / dt
                u = (cur_io.bytes_sent - self.last_io.bytes_sent) / 1024 / dt
                self.lbls['speed'].setText(
                    f"🚀 速率: <span style='color:#58D68D'>↓ {d:.0f}K</span> <span style='color:#58D68D'>↑ {u:.0f}K</span>")
        self.last_io = cur_io
        self.last_time = now

        ip = get_local_ip()
        self.lbls['ip'].setText(f"💻 IP: <span style='color:#FFF'>{ip}</span>")

        proxy = get_system_proxy()

        if proxy == "127.0.0.1:13140":
            self.lbls['proxy'].setText(f"🔗 代理: <span style='color:#58D68D'>{proxy}</span>")
        elif proxy:
            self.lbls['proxy'].setText(f"🔗 代理: <span style='color:#F4D03F'>{proxy}</span>")
        else:
            self.lbls['proxy'].setText("🔗 代理: <span style='color:#F4D03F'>直连</span>")

        proxy_split = MITM_PROXY.split(":")
        run = check_port_listening(proxy_split[0], int(proxy_split[1]), 0.05)
        if run:
            self.lbls['mitm'].setText("🛡️ Mitm: <span style='color:#58D68D'>运行中</span>")
        else:
            self.lbls['mitm'].setText("⚙️ Mitm: <span style='color:#F4D03F'>未启动</span>")

        if check_cert():
            self.lbls['cert'].setText("🔒 证书: <span style='color:#58D68D'>正常</span>")
        else:
            self.lbls['cert'].setText("⚠️ 证书: <span style='color:#F4D03F'>异常</span>")

    def update_status(self, data):
        self.lbls['time'].setText(f"🕔 当前时间: <span style='color:#FFF'>{datetime.now().strftime('%H:%M:%S')}</span>")
        self.lbls['pid'].setText(f"🟢 PID: <span style='color:#58D68D'>{os.getpid()}</span>")

        # 使用后台线程传来的数据
        self.lbls['net'].setText(f"📶 网络: <span style='color:#58D68D'>{data['net']}</span>")

        self.lbls['speed'].setText(
            f"🚀 速率: <span style='color:#58D68D'>↓ {data['speed_d']:.0f}K</span>"
            f" <span style='color:#58D68D'>↑ {data['speed_u']:.0f}K</span>"
        )

        self.lbls['ip'].setText(f"💻 IP: <span style='color:#FFF'>{data['ip']}</span>")

        proxy = data['proxy']
        if proxy == "127.0.0.1:13140":
            self.lbls['proxy'].setText(f"🔗 代理: <span style='color:#58D68D'>{proxy}</span>")
        elif proxy:
            self.lbls['proxy'].setText(f"🔗 代理: <span style='color:#F4D03F'>{proxy}</span>")
        else:
            self.lbls['proxy'].setText("🔗 代理: <span style='color:#F4D03F'>直连</span>")

        self.lbls['mitm'].setText(
            "🛡️ Mitm: <span style='color:#58D68D'>运行中</span>" if data['mitm']
            else "⚙️ Mitm: <span style='color:#F4D03F'>未启动</span>"
        )

        self.lbls['cert'].setText(
            "🔒 证书: <span style='color:#58D68D'>正常</span>" if data['cert']
            else "⚠️ 证书: <span style='color:#F4D03F'>异常</span>"
        )

        # 更新session显示，确保清除过期session后状态栏能及时更新
        self._update_session_display()

    def open_config(self):
        if not os.path.exists(CONFIG_FILE):
            ToastManager.instance().show("config.json 文件不存在", "error")
            return
        ConfigDialog(CONFIG_FILE, self).exec()
        self._load_auto_clock_settings()
        return None

    def open_auto_clock_config(self):
        if not os.path.exists(CONFIG_FILE):
            ToastManager.instance().show("config.json 文件不存在", "error")
            return
        if AutoClockConfigDialog(CONFIG_FILE, self).exec() == QDialog.Accepted:
            self._load_auto_clock_settings()

    def show_support(self):
        SponsorSubmitDialog(self).exec()  # SupportDialog(self).exec()

    def show_feedback(self):
        FeedbackDialog(self).exec()

    def flush_dns(self):
        bash("ipconfig /flushdns")
        logging.info(f'DNS 刷新成功')
        ToastManager.instance().show("DNS 刷新成功", "success")

    def copy_log(self):
        QApplication.clipboard().setText(self.log.toPlainText())
        # QMessageBox.information(self, "OK", "日志已复制到剪贴板！")
        ToastManager.instance().show("已复制到剪贴板", "success")

    def open_image_manager(self):
        ImageManagerDialog(self).exec()

    def export_log(self):
        """导出日志到文件"""
        filename, _ = QFileDialog.getSaveFileName(self, "导出日志", "log.txt", "Text Files (*.txt);;All Files (*)")
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.log.toPlainText())
                ToastManager.instance().show("日志导出成功", "success")
            except Exception as e:
                ToastManager.instance().show(f"导出失败: {str(e)}", "error")

    def check_update(self, silent: bool = False):
        """检查更新"""
        if hasattr(self, 'update_worker') and self.update_worker.isRunning():
            if not silent:
                ToastManager.instance().show("正在检查更新，请稍候...", "info")
            return

        # 直接基于 GitHub Release 检查更新
        self.update_worker = UpdateCheckWorker(PROJECT_GITHUB, PROJECT_VERSION)
        self.update_worker.result_signal.connect(
            lambda success, data: self.on_update_check_result(success, data, silent)
        )
        self.update_worker.start()

        if not silent:
            ToastManager.instance().show("正在检查更新...", "info")

    def check_update_silent(self):
        """静默检查更新（启动时调用）"""
        self.check_update(silent=True)

    def on_update_check_result(self, success: bool, data: dict, silent: bool = False):
        """更新检查结果处理"""
        if not success:
            error_msg = data.get("error", "检查更新失败")
            if not silent:
                ToastManager.instance().show(f"检查更新失败：{error_msg}", "error")
            return

        has_update = data.get("has_update", False)
        if has_update:
            # 有新版本，显示更新对话框
            UpdateDialog(data, self).exec()
        else:
            # 无新版本
            if not silent:
                ToastManager.instance().show("当前已是最新版本！", "success")

    def open_weekly_journal(self):
        """打开周记对话框，先检查jsessionid是否有效"""
        try:
            config = read_config(CONFIG_FILE)
        except Exception as exc:
            ToastManager.instance().show(f"读取配置失败：{exc}", "error")
            return

        # 检查jsessionid是否有效
        try:
            from app.apis.xybsyw import login, get_plan
            # 尝试使用缓存的登录信息
            try:
                login_args = login(config['input'], use_cache=True)
            except Exception:
                ToastManager.instance().show("JSESSIONID已失效，请先执行签到操作以获取新的登录信息", "warning")
                return
            # 尝试获取计划来验证session
            get_plan(userAgent=config['input']['userAgent'], args=login_args)
        except Exception as e:
            error_msg = str(e)
            if "失效" in error_msg or "205" in error_msg or "未登录" in error_msg:
                ToastManager.instance().show("JSESSIONID已失效，请先执行签到操作以获取新的登录信息", "warning")
                return
            # 其他错误不影响打开对话框
            logging.warning(f"检查jsessionid时出现错误: {e}")

        if self.weekly_journal_dialog is not None:
            self.weekly_journal_dialog.close()
            self.weekly_journal_dialog.deleteLater()

        try:
            self.weekly_journal_dialog = WeeklyJournalDialog(config.get("model", {}), login_args, self)
            self.weekly_journal_dialog.show()
        except Exception as e:
            import traceback
            logging.error(f"打开周记页面失败: {e}\n{traceback.format_exc()}")
            QMessageBox.critical(self, "程序错误", f"打开周记页面时发生错误:\n{str(e)}\n\n详情请查看日志文件。")

    def get_code_and_session(self):
        """获取Code和JSESSIONID"""
        if self.is_getting_code:
            if hasattr(self, 'code_worker'):
                self.btn_get_code.setEnabled(False)
                self.btn_get_code.setText("停止中...")
                self.code_worker.requestInterruption()
            return

        # 验证数据
        try:
            errMsg = validate_config(read_config(CONFIG_FILE))
            if errMsg:
                ToastManager.instance().show(errMsg, "warning")
                return
        except Exception as e:
            ToastManager.instance().show(f"读取配置失败: {e}", "error")
            return

        self.is_getting_code = True
        self.btn_get_code.setText("停止获取")
        self.btn_get_code.setStyleSheet(
            "background: #C0392B; color: white; border-radius: 20px; padding: 10px; font-size: 12pt; font-weight: bold; border: none;")
        self.prog.show()
        self.btn_run.setEnabled(False)
        for btn in self.grp.buttons():
            btn.setEnabled(False)

        self.code_worker = GetCodeAndSessionThread(CONFIG_FILE)
        self.code_worker.finished_signal.connect(self.on_get_code_done)
        self.code_worker.start()

    def on_get_code_done(self, success, msg):
        """获取Code和JSESSIONID完成"""
        if success:
            self._bring_to_front_retry(tries=4, delay_ms=350)
        self.is_getting_code = False
        self.btn_get_code.setEnabled(True)
        self.btn_get_code.setText("获取code")
        # 无论成功失败，都恢复原始样式
        self.btn_get_code.setStyleSheet("")
        self.btn_get_code.setObjectName("BtnGetCode") # Re-apply ID to be safe
        self.style().polish(self.btn_get_code)        # Force re-polish


        if success:
            ToastManager.instance().show("获取成功！", "success")
            # 更新JSESSIONID显示
            self._update_session_display()
        else:
            if msg and msg != "任务已停止":
                # 只有非手动停止的错误才弹窗
                ToastManager.instance().show(msg, "error")
        
        self.prog.hide()
        self.btn_run.setEnabled(True)
        for btn in self.grp.buttons():
            btn.setEnabled(True)

    def _bring_to_front(self):
        """尽量将主窗口切回前台活动状态"""
        if self.isMinimized():
            self.showNormal()
        self.raise_()
        self.activateWindow()
        self._force_foreground_windows()

    def _bring_to_front_retry(self, tries: int = 3, delay_ms: int = 400):
        self._bring_to_front()
        if tries <= 1:
            return
        QTimer.singleShot(delay_ms, lambda: self._bring_to_front_retry(tries - 1, delay_ms))

    def _force_foreground_windows(self):
        """Windows 下尝试强制前置窗口（Qt 激活失败时兜底）"""
        if os.name != "nt":
            return
        try:
            hwnd = int(self.winId())
            user32 = ctypes.windll.user32
            SW_RESTORE = 9
            user32.ShowWindow(hwnd, SW_RESTORE)
            user32.SetForegroundWindow(hwnd)
            user32.BringWindowToTop(hwnd)
        except Exception:
            pass


    def _update_session_display(self):
        """更新JSESSIONID显示"""
        from app.utils.files import load_session_cache
        from datetime import datetime, timedelta

        cache = load_session_cache()
        if cache and cache.get('sessionId'):
            session_id = cache['sessionId']
            timestamp = cache.get('timestamp', 0)
            if timestamp:
                dt = datetime.fromtimestamp(timestamp)
                time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                display_id = session_id[:10] + "..." if len(session_id) > 10 else session_id
                self.lbls['session'].setText(
                    f"🗝️ SESSION: <span style='color:#58D68D'>{display_id}...</span><span style='color:#58D68D'>({time_str})</span>")
            else:
                self.lbls['session'].setText(f"🗝️ SESSION: <span style='color:#58D68D'>{session_id[:10]}...</span>")
        else:
            self.lbls['session'].setText("🗝️ SESSION: <span style='color:#F4D03F'>未获取</span>")

    def _mode_to_option(self, mode: str, image_path: str = None) -> dict:
        mode_map = {
            "in": {"action": "普通签到", "code": "2"},
            "out": {"action": "普通签退", "code": "1"},
            "photo_in": {"action": "拍照签到", "code": "2"},
            "photo_out": {"action": "拍照签退", "code": "1"},
        }
        if mode not in mode_map:
            raise RuntimeError(f"不支持的定时打卡模式: {mode}")

        opt = dict(mode_map[mode])
        if mode in ("photo_in", "photo_out"):
            if not image_path:
                raise RuntimeError(f"{mode} 需要 image_path")
            opt["image_path"] = image_path
        return opt


    def _build_auto_clock_key(self, idx: int, task: dict) -> str:
        return f"{idx}:{task['mode']}:{task['time']}"

    def _compute_randomized_task_datetime(self, day: datetime, task_time: str) -> datetime:
        hh, mm = task_time.split(":")
        base_minutes = int(hh) * 60 + int(mm)
        if self.auto_clock_random_minutes > 0:
            offset = random.randint(-self.auto_clock_random_minutes, self.auto_clock_random_minutes)
        else:
            offset = 0

        final_minutes = max(0, min(23 * 60 + 59, base_minutes + offset))
        midnight = datetime(day.year, day.month, day.day)
        return midnight + timedelta(minutes=final_minutes)

    def _compute_next_trigger_for_task(self, now: datetime, task: dict) -> datetime:
        today_run = self._compute_randomized_task_datetime(now, task["time"])
        if today_run > now:
            return today_run

        tomorrow = now + timedelta(days=1)
        return self._compute_randomized_task_datetime(tomorrow, task["time"])

    def _reschedule_next_trigger_for_task(self, idx: int, task: dict, now: datetime):
        key = self._build_auto_clock_key(idx, task)
        tomorrow = now + timedelta(days=1)
        self.auto_clock_next_trigger[key] = self._compute_randomized_task_datetime(tomorrow, task["time"])

    def _log_next_auto_clock_times(self):
        if not self.auto_clock_enabled:
            return
        for idx, task in enumerate(self.auto_clock_tasks):
            key = self._build_auto_clock_key(idx, task)
            dt = self.auto_clock_next_trigger.get(key)
            if not dt:
                continue
            logging.info(
                f"Auto-clock task[{idx + 1}] mode={task['mode']} base={task['time']} random=+/-{self.auto_clock_random_minutes}m next={dt.strftime('%Y-%m-%d %H:%M')}"
            )

    def _load_auto_clock_settings(self):
        self.auto_clock_enabled = False
        self.auto_clock_tasks = []
        self.auto_clock_last_trigger = {}
        self.auto_clock_next_trigger = {}
        self.auto_clock_random_minutes = 0

        try:
            config = read_config(CONFIG_FILE)
        except Exception as exc:
            logging.warning(f"Failed to load auto-clock config: {exc}")
            self.auto_clock_timer.stop()
            return

        settings = config.get("settings", {})
        auto_clock = settings.get("auto_clock", {})
        if not isinstance(auto_clock, dict):
            self.auto_clock_timer.stop()
            return

        enabled = bool(auto_clock.get("enabled", False))
        tasks = auto_clock.get("tasks", [])
        poll_seconds = int(auto_clock.get("poll_seconds", 30) or 30)
        random_minutes = int(auto_clock.get("random_minutes", 0) or 0)
        random_minutes = max(0, min(120, random_minutes))

        if not isinstance(tasks, list):
            logging.warning("settings.auto_clock.tasks is not a list, ignored")
            self.auto_clock_timer.stop()
            return

        normalized_tasks = []
        for idx, task in enumerate(tasks):
            if not isinstance(task, dict):
                logging.warning(f"Auto-clock task #{idx + 1} is not an object, ignored")
                continue

            task_time = str(task.get("time", "")).strip()
            mode = str(task.get("mode", "")).strip().lower()
            image_path = task.get("image_path")
            if image_path is not None:
                image_path = str(image_path).strip()

            if not re.match(r"^\d{2}:\d{2}$", task_time):
                logging.warning(f"Auto-clock task #{idx + 1} has invalid time: {task_time}")
                continue

            hh, mm = task_time.split(":")
            if int(hh) > 23 or int(mm) > 59:
                logging.warning(f"Auto-clock task #{idx + 1} has invalid time: {task_time}")
                continue

            if mode not in ("in", "out", "photo_in", "photo_out"):
                logging.warning(f"Auto-clock task #{idx + 1} has invalid mode: {mode}")
                continue

            normalized_tasks.append({
                "time": task_time,
                "mode": mode,
                "image_path": image_path,
            })

        self.auto_clock_enabled = enabled and bool(normalized_tasks)
        self.auto_clock_tasks = normalized_tasks
        self.auto_clock_random_minutes = random_minutes
        self.auto_clock_timer.setInterval(max(10, poll_seconds) * 1000)

        if self.auto_clock_enabled:
            now = datetime.now()
            for idx, task in enumerate(self.auto_clock_tasks):
                key = self._build_auto_clock_key(idx, task)
                self.auto_clock_next_trigger[key] = self._compute_next_trigger_for_task(now, task)

            self.auto_clock_timer.start()
            logging.info(
                f"Auto-clock enabled with {len(self.auto_clock_tasks)} tasks, random window +/-{self.auto_clock_random_minutes} minutes"
            )
            self._log_next_auto_clock_times()
        else:
            self.auto_clock_timer.stop()
            logging.info("Auto-clock disabled")

    def _can_start_sign_task(self) -> bool:

        from app.utils.files import get_valid_session_cache

        has_session = get_valid_session_cache() is not None
        if not has_session:
            ToastManager.instance().show("请先点击“获取code”获取有效 SESSIONID", "warning")
            return False

        try:
            err_msg = validate_config(read_config(CONFIG_FILE))
        except Exception as exc:
            ToastManager.instance().show(f"读取配置失败: {exc}", "error")
            return False

        if err_msg:
            logging.warning(f"配置校验失败: {err_msg}")
            ToastManager.instance().show(err_msg, "warning")
            return False

        return True

    def _start_sign_task(self, opt: dict, source: str = "manual") -> bool:
        if self.is_running or self.is_getting_code:
            logging.info("当前有任务执行中，跳过本次打卡触发")
            return False

        if not self._can_start_sign_task():
            return False

        self.current_run_source = source
        self.is_running = True
        self.btn_run.setText("停止执行")
        self.btn_run.setStyleSheet("background: #C0392B;")
        self.prog.show()
        self.btn_get_code.setEnabled(False)
        for btn in self.grp.buttons():
            btn.setEnabled(False)

        logging.info("")
        logging.info(f"{'=' * 10} TASK {source.upper()} {datetime.now().strftime('%H:%M')} {'=' * 10}")
        self.worker = SignTaskThread(CONFIG_FILE, opt)
        self.worker.finished_signal.connect(self.on_done)
        self.worker.start()
        return True


    def _on_auto_clock_tick(self):
        if not self.auto_clock_enabled:
            return
        if self.is_running or self.is_getting_code:
            return

        now = datetime.now()

        for idx, task in enumerate(self.auto_clock_tasks):
            key = self._build_auto_clock_key(idx, task)
            next_dt = self.auto_clock_next_trigger.get(key)
            if next_dt is None:
                next_dt = self._compute_next_trigger_for_task(now, task)
                self.auto_clock_next_trigger[key] = next_dt

            if now < next_dt:
                continue

            try:
                opt = self._mode_to_option(task["mode"], task.get("image_path"))
            except Exception as exc:
                logging.warning(f"Auto-clock config error, skipped this task: {exc}")
                self._reschedule_next_trigger_for_task(idx, task, now)
                continue

            if self._start_sign_task(opt, source="auto"):
                self.auto_clock_last_trigger[key] = now.strftime("%Y-%m-%d")
                ToastManager.instance().show(
                    f"定时打卡触发: {task['mode']}（计划 {next_dt.strftime('%H:%M')}）",
                    "info"
                )
                self._reschedule_next_trigger_for_task(idx, task, now)
                self._log_next_auto_clock_times()
                break

    def toggle(self):

        if not self.is_running:
            checked_id = self.grp.checkedId()
            photo_image = None
            if checked_id in [2, 3]:
                dialog = PhotoSignDialog(self)
                if dialog.exec() != QDialog.Accepted:
                    logging.info("用户取消了拍照签到操作")
                    return
                photo_image = dialog.selected_image

            if checked_id == 0:
                opt = self._mode_to_option("in")
            elif checked_id == 1:
                opt = self._mode_to_option("out")
            elif checked_id == 2:
                opt = self._mode_to_option("photo_in", photo_image)
            elif checked_id == 3:
                opt = self._mode_to_option("photo_out", photo_image)
            else:
                ToastManager.instance().show("请选择打卡模式", "warning")
                return

            self._start_sign_task(opt, source="manual")
            return
            # 检查是否有有效的JSESSIONID，如果有就直接使用，不需要code
            from app.utils.files import get_valid_session_cache

            has_session = get_valid_session_cache() is not None

            if not has_session:
                ToastManager.instance().show("请先点击'获取code'按钮以获取JSESSIONID", "warning")
                return

            logging.info("")
            logging.info(f"{'=' * 10} 🟢 TASK {datetime.now().strftime('%H:%M')} {'=' * 10}")

            # 验证数据
            errMsg = validate_config(read_config(CONFIG_FILE))
            if errMsg:
                logging.warning(f"配置文件验证失败: {errMsg}")
                ToastManager.instance().show(errMsg, "warning")
                return

            self.is_running = True
            self.btn_run.setText("停止运行")
            self.btn_run.setStyleSheet("background: #C0392B;")
            self.prog.show()
            self.btn_get_code.setEnabled(False)
            for btn in self.grp.buttons():
                btn.setEnabled(False)

            # 操作
            checked_id = self.grp.checkedId()
            photo_image = None
            if checked_id in [2, 3]:
                dialog = PhotoSignDialog(self)
                if dialog.exec() != QDialog.Accepted:
                    logging.info("用户取消了拍照签到操作")
                    return
                photo_image = dialog.selected_image

            if checked_id == 0:
                opt = {"action": "普通签到", "code": "2"}
            elif checked_id == 1:
                opt = {"action": "普通签退", "code": "1"}
            elif checked_id == 2:
                opt = {"action": "拍照签到", "code": "2", "image_path": photo_image}
            elif checked_id == 3:
                opt = {"action": "拍照签退", "code": "1", "image_path": photo_image}

            self.worker = SignTaskThread(CONFIG_FILE, opt)
            self.worker.finished_signal.connect(self.on_done)
            self.worker.start()
        else:
            if hasattr(self, 'worker'):
                self.btn_run.setEnabled(False)
                self.btn_run.setText("停止中...")
                self.worker.requestInterruption()

    def on_done(self, success, msg):
        self.is_running = False
        self.btn_run.setEnabled(True)
        self.btn_run.setText("开始执行")
        self.btn_run.setStyleSheet("")
        self.btn_run.setObjectName("BtnStart")
        self.style().polish(self.btn_run)
        self.prog.hide()
        self.btn_get_code.setEnabled(True)
        for btn in self.grp.buttons():
            btn.setEnabled(True)

        # 更新session显示，确保清除过期session后状态栏能及时更新
        self._update_session_display()
        self._notify_sign_result(success, msg)

        if success and self.current_run_source == "manual":
            # 成功后弹出赞助提交框（检查是否设置了不再显示）
            try:
                config = read_config(CONFIG_FILE)
                settings = config.get("settings", {})
                if not settings.get("dont_show_sponsor", False):
                    SponsorSubmitDialog(self).exec()
            except Exception:
                # 如果读取配置失败，默认显示
                SponsorSubmitDialog(self).exec()
        else:
            if msg != "任务已停止":
                ToastManager.instance().show(msg, "error")
    def _notify_sign_result(self, success: bool, msg: str):
        try:
            config = read_config(CONFIG_FILE)
            settings = config.get("settings", {})
            pushplus = settings.get("pushplus", {})
            token = str(pushplus.get("token", "") or "").strip()
            if not token:
                return
        except Exception as exc:
            logging.warning(f"读取 PushPlus 配置失败，已跳过推送: {exc}")
            return

        status = "成功" if success else "失败"
        source = "定时任务" if self.current_run_source == "auto" else "手动"
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        title = f"打卡{status}"
        content = f"{source}打卡结果：{status}\n时间：{now}\n消息：{msg}"

        threading.Thread(
            target=self._send_pushplus_in_thread,
            args=(token, title, content),
            daemon=True,
        ).start()

    @staticmethod
    def _send_pushplus_in_thread(token: str, title: str, content: str):
        try:
            notify_pushplus(title=title, content=content, token=token)
            logging.info("PushPlus 推送成功")
        except Exception as exc:
            logging.warning(f"PushPlus 推送失败: {exc}")
    def closeEvent(self, event):
        """Ensure background services exit when the window closes."""
        try:
            if hasattr(self, "auto_clock_timer"):
                self.auto_clock_timer.stop()

            # stop monitor thread first to avoid自动重启 mitm
            if hasattr(self, "monitor") and self.monitor.isRunning():
                self.monitor.stop()
                self.monitor.wait(2000)

            if hasattr(self, "worker") and getattr(self, "worker").isRunning():
                self.worker.requestInterruption()
                self.worker.wait(2000)

            if hasattr(self, "code_worker") and getattr(self, "code_worker").isRunning():
                self.code_worker.requestInterruption()
                self.code_worker.wait(2000)

            if hasattr(self, "update_worker") and getattr(self, "update_worker").isRunning():
                self.update_worker.requestInterruption()
                self.update_worker.wait(2000)
        finally:
            # 关闭窗口时停止 mitmdump，防止后台残留
            # self.mitm.stop_mitm()
            # super().closeEvent(event)
            # 异步关闭 mitmdump
            threading.Thread(
                target=self.mitm.stop_mitm,
                daemon=True
            ).start()

            # 继续正常关闭窗口
            super().closeEvent(event)

