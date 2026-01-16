import logging
import os
import subprocess
import threading
import time
from datetime import datetime

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QFrame, QVBoxLayout, QLabel, QGridLayout, QPushButton, \
    QButtonGroup, QRadioButton, QProgressBar, QSizePolicy, QMessageBox, QApplication, QTextEdit, QDialog

from app.config.common import QQ_GROUP, VERSION, CONFIG_FILE, MITM_PROXY, API_URL
from app.gui.components.log_viewer import QTextEditLogger
from app.gui.components.toast import ToastManager
from app.gui.dialogs.dialogs.config_dialog import ConfigDialog
from app.gui.dialogs.feedback_dialog import FeedbackDialog
from app.gui.dialogs.image_manager_dialog import ImageManagerDialog
from app.gui.dialogs.photo_sign_dialog import PhotoSignDialog
from app.gui.dialogs.sponsor_dialog import SponsorSubmitDialog
from app.gui.dialogs.update_dialog import UpdateDialog
from app.gui.dialogs.weekly_journal_dialog import WeeklyJournalDialog
from app.mitm.service import MitmService
from app.utils.commands import get_net_io, bash, get_network_type, get_local_ip, get_system_proxy, check_port_listening, \
    check_cert
from app.utils.files import validate_config, read_config
from app.workers.monitor_thread import MonitorThread
from app.workers.sign_task import SignTaskThread, GetCodeAndSessionThread
from app.workers.update_worker import UpdateCheckWorker


class ModernWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle(f"🔰 Sign Sign In {VERSION} - 实习打卡助手")
        self.resize(900, 540)  # 进一步收紧高度
        self.is_running = False
        self.is_getting_code = False
        self.photo_image_path = None
        self.btn_get_code_original_style = None  # 保存按钮原始样式

        # 自动守护：monitor 会调用 mitm.start()
        self.mitm = MitmService()
        self.monitor = MonitorThread(self.mitm)
        self.monitor.data_signal.connect(self.update_status)
        self.monitor.start()

        self.setup_style()
        self.init_ui()

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

        title = QLabel("🔰 Sign Sign In")
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
            ("🔗 系统代理", lambda: bash('rundll32.exe shell32.dll,Control_RunDLL inetcpl.cpl,,4')),
            ("🔒 证书管理", lambda: bash('certmgr.msc')),
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
        l_vbox.addLayout(t_grid)

        btn_journal = QPushButton("提交周记（测试）")
        btn_journal.setObjectName("BtnJournal")
        btn_journal.clicked.connect(self.open_weekly_journal)
        l_vbox.addWidget(btn_journal)

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
        self.btn_get_code_original_style = """
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #28A745, stop:1 #20C997);
            color: white;
            border-radius: 20px;
            padding: 10px;
            font-size: 12pt;
            font-weight: bold;
            border: none;
        """
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
        btn_git.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://gitee.com/ckkk524334/sign-sign-in")))
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
                border: none;
            }
            #BtnGetCode:hover { opacity: 0.92; }
            #BtnStart {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3D7CFF, stop:1 #7A4DFF);
                color: white;
                border-radius: 20px;
                padding: 10px;
                font-size: 12pt;
                font-weight: bold;
                border: none;
            }
            #BtnStart:hover { opacity: 0.92; }
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
        return None

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

    def check_update(self, silent: bool = False):
        """检查更新"""
        if hasattr(self, 'update_worker') and self.update_worker.isRunning():
            if not silent:
                ToastManager.instance().show("正在检查更新，请稍候...", "info")
            return

        self.update_worker = UpdateCheckWorker(API_URL + "/api/check-update", VERSION)
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

        WeeklyJournalDialog(config.get("model", {}), self).exec()

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
        self.is_getting_code = False
        self.btn_get_code.setEnabled(True)
        self.btn_get_code.setText("获取code")
        # 恢复原始样式
        self.btn_get_code.setStyleSheet(self.btn_get_code_original_style)
        self.prog.hide()
        self.btn_run.setEnabled(True)
        for btn in self.grp.buttons():
            btn.setEnabled(True)

        if success:
            ToastManager.instance().show("获取成功！", "success")
            # 更新JSESSIONID显示
            self._update_session_display()
        else:
            if msg != "任务已停止":
                ToastManager.instance().show(msg, "error")

    def _update_session_display(self):
        """更新JSESSIONID显示"""
        from app.utils.files import load_session_cache
        from datetime import datetime

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

    def toggle(self):
        if not self.is_running:
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
        self.btn_run.setStyleSheet("""
            background: #007ACC;
            color: white;
            border-radius: 4px;
            padding: 8px;
            font-size: 11pt;
            font-weight: bold;
        """)
        self.prog.hide()
        self.btn_get_code.setEnabled(True)
        for btn in self.grp.buttons():
            btn.setEnabled(True)

        # 更新session显示，确保清除过期session后状态栏能及时更新
        self._update_session_display()

        if success:
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

    def closeEvent(self, event):
        """Ensure background services exit when the window closes."""
        try:
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