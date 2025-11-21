import logging
import os
import subprocess
import time
from datetime import datetime

from PySide6.QtCore import QTimer, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QFrame, QVBoxLayout, QLabel, QGridLayout, QPushButton, \
    QButtonGroup, QRadioButton, QProgressBar, QSizePolicy, QMessageBox, QApplication, QTextEdit

from app.config.common import QQ_GROUP, VERSION, CONFIG_FILE, MITM_PROXY
from app.gui.components.log_viewer import QTextEditLogger
from app.gui.components.toast import Toast, ToastManager
from app.gui.dialogs.dialogs.config_dialog import ConfigDialog
from app.gui.dialogs.sponsor_dialog import SponsorSubmitDialog
from app.mitm.service import MitmService
from app.utils.commands import get_net_io, bash, get_network_type, get_local_ip, get_system_proxy, check_port_listening, \
    check_cert
from app.utils.files import validate_config, read_config
from app.workers.sign_task import SignTaskThread
from app.workers.monitor_thread import MonitorThread


class ModernWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle(f"🔰 Sign Sign In {VERSION} - 实习打卡助手")
        self.resize(900, 580)  # 紧凑高度
        self.is_running = False

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
        l_vbox.setSpacing(10)

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
        mon_grid.setSpacing(8)
        # Set Equal Column Width
        mon_grid.setColumnStretch(0, 1)
        mon_grid.setColumnStretch(1, 1)

        self.lbls = {}
        keys = ["time", "pid", "net", "speed", "proxy", "mitm", "cert", "ip"]
        for k in keys:
            l = QLabel("-")
            l.setObjectName("StatusLabel")
            l.setTextFormat(Qt.RichText)
            self.lbls[k] = l

        mon_grid.addWidget(self.lbls['time'], 0, 0)
        mon_grid.addWidget(self.lbls['pid'], 0, 1)
        mon_grid.addWidget(self.lbls['net'], 1, 0)
        mon_grid.addWidget(self.lbls['speed'], 1, 1)
        mon_grid.addWidget(self.lbls['proxy'], 2, 0, 1, 2)  # span 2 cols
        mon_grid.addWidget(self.lbls['mitm'], 3, 0)
        mon_grid.addWidget(self.lbls['cert'], 3, 1)
        mon_grid.addWidget(self.lbls['ip'], 4, 0, 1, 2)

        l_vbox.addWidget(mon_box)

        # ------------------------- Tools -------------------------
        # 区域标签
        label = QLabel("工具箱")
        label.setObjectName("SectionLabel")
        l_vbox.addWidget(label)

        t_grid = QGridLayout()
        t_grid.setSpacing(10)
        tools = [("🔗 系统代理", lambda: bash('rundll32.exe shell32.dll,Control_RunDLL inetcpl.cpl,,4')),
                 ("🔒 证书管理", lambda: bash('certmgr.msc')),
                 ("📄 编辑配置", self.open_config),
                 ("🔁 刷新DNS", self.flush_dns),
                 ("📤 发送反馈", self.show_feedback),
                 ("💻 打开CMD", lambda: subprocess.Popen(["cmd.exe"], creationflags=subprocess.CREATE_NEW_CONSOLE)),
                 # New
                 ]
        for i, (name, func) in enumerate(tools):
            b = QPushButton(name)
            b.setObjectName("ToolBtn")
            b.clicked.connect(func)
            t_grid.addWidget(b, i // 2, i % 2)
        l_vbox.addLayout(t_grid)

        # ------------------------- Mode -------------------------
        label = QLabel("执行操作")
        label.setObjectName("SectionLabel")
        l_vbox.addWidget(label)

        self.grp = QButtonGroup(self)

        rb_in = QRadioButton("普通签到")
        rb_in.setChecked(True)
        self.grp.addButton(rb_in, 0)

        rb_out = QRadioButton("普通签退")
        self.grp.addButton(rb_out, 1)

        rb_img_in = QRadioButton("拍照签到（测试）")
        self.grp.addButton(rb_img_in, 2)

        # 第一行：签到 + 签退
        mode_row1 = QHBoxLayout()
        mode_row1.setSpacing(30)
        mode_row1.addWidget(rb_in)
        mode_row1.addWidget(rb_out)
        mode_row1.addStretch()
        l_vbox.addLayout(mode_row1)

        # 两行之间增加空隙（建议 10 像素）
        l_vbox.addSpacing(10)

        # 第二行：单独的“实习图片签到”
        mode_row2 = QHBoxLayout()
        mode_row2.setSpacing(30)
        mode_row2.addWidget(rb_img_in)
        mode_row2.addStretch()
        l_vbox.addLayout(mode_row2)

        # 下方留空
        l_vbox.addSpacing(20)
        l_vbox.addStretch()

        # ------------------------- Progress -------------------------
        self.prog = QProgressBar()
        self.prog.setTextVisible(False)
        self.prog.setRange(0, 0)
        self.prog.hide()
        l_vbox.addWidget(self.prog)

        # ------------------------- Main Buttons -------------------------
        self.btn_run = QPushButton("开始执行")
        self.btn_run.setObjectName("BtnStart")
        self.btn_run.clicked.connect(self.toggle)
        l_vbox.addWidget(self.btn_run)

        btn_row = QHBoxLayout()

        btn_don = QPushButton("支持作者")
        btn_don.setObjectName("BtnDonate")
        btn_don.clicked.connect(self.show_support)
        btn_row.addWidget(btn_don)

        btn_git = QPushButton("开源仓库")
        btn_git.setObjectName("BtnGit")
        btn_git.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://gitee.com/ckkk524334/sign-sign-in")))
        btn_row.addWidget(btn_git)

        l_vbox.addLayout(btn_row)

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

        btn_copy = QPushButton("复制")
        btn_copy.setObjectName("LogActionBtn")
        btn_copy.clicked.connect(self.copy_log)
        btn_clear = QPushButton("清空")
        btn_clear.setObjectName("LogActionBtn")
        btn_clear.clicked.connect(lambda: self.clear_log())
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
            QMainWindow { background: #1E1E1E; }
            #LeftPanel { background: #252526; border-right: 1px solid #333; }
            #AppTitle { font-family: "Segoe UI"; font-size: 18pt; font-weight: bold; color: white; }
            #AppSubTitle { font-size: 9pt; color: #999; }
            #MonitorBox { background: #2D2D30; border-radius: 4px; border: 1px solid #3E3E42; }
            #StatusLabel { color: #CCC; font-family: Consolas; font-size: 9pt; }
            #SectionLabel { color: #888; font-weight: bold; margin-top: 8px; }

            #ToolBtn { background: #333; color: #DDD; border: 1px solid #555; padding: 4px; border-radius: 3px; }
            #ToolBtn:hover { background: #444; border-color: #007ACC; }

            QRadioButton { color: #888; font-size: 10pt; }
            /* 选中文字 */
            QRadioButton:checked { color: white; font-weight: bold; }
            /* 未选中时的圆形 */
            QRadioButton::indicator { 
                width: 14px;
                height: 14px;
                border-radius: 7px;            /* <-- 圆形关键 */
                border: 2px solid #666;        /* 空心圆的外圈 */
                background: transparent;
            }
            /* 悬停时边框变亮 */
            QRadioButton::indicator:hover { border-color: #AAA; }
            /* 选中状态（蓝色实心圆） */
            QRadioButton::indicator:checked { background: #007ACC; border: 2px solid #007ACC; }


            #BtnStart { background: #007ACC; color: white; border-radius: 4px; padding: 8px; font-size: 11pt; font-weight: bold; }
            #BtnStart:hover { background: #0062A3; }
            #BtnDonate { background: transparent; color: #888; border: 1px solid #444; border-radius: 4px; padding: 4px; margin-top: 4px;}
            #BtnDonate:hover { color: white; border-color: #666; }

            #BtnGit { background: transparent; color: #888; border: 1px solid #444; border-radius: 4px; padding: 4px; margin-top: 4px;}
            #BtnGit:hover { color: white; border-color: #666; }

            #TermHeader { color: #CCC; font-weight: bold;}
            #LogView { background: #1E1E1E; border: none; color: #CCC; font-family: Consolas; font-size: 9pt; padding: 8px; }
            #LogActionBtn { background: #444; color: white; border: none; padding: 2px 8px; border-radius: 2px; margin-left: 5px; }

            QProgressBar { background: #333; border: none; height: 3px; }
            QProgressBar::chunk { background: #007ACC; }
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
            self.lbls['proxy'].setText(f"🔗 代理: <span style='color:#58D68D'>{proxy} (Target)</span>")
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
            self.lbls['proxy'].setText(f"🔗 代理: <span style='color:#58D68D'>{proxy} (Target)</span>")
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

    def open_config(self):
        if not os.path.exists(CONFIG_FILE): return QMessageBox.warning(self, "Error", "config.json文件不存在")
        ConfigDialog(CONFIG_FILE, self).exec()
        return None

    def show_support(self):
        SponsorSubmitDialog(self).exec()  # SupportDialog(self).exec()

    def show_feedback(self):
        QMessageBox.information(self, "开发中", "该功能正在开发中！")  # FeedbackDialog(self).exec()

    def flush_dns(self):
        bash("ipconfig /flushdns")
        logging.info(f'DNS 刷新成功')

    def copy_log(self):
        QApplication.clipboard().setText(self.log.toPlainText())
        # QMessageBox.information(self, "OK", "日志已复制到剪贴板！")
        ToastManager.instance().show("已复制到剪贴板", "success")

    def toggle(self):
        if not self.is_running:
            logging.info("")
            logging.info(f"{'=' * 20} 🟢 TASK {datetime.now().strftime('%H:%M')} {'=' * 20}")

            # 验证数据
            errMsg = validate_config(read_config(CONFIG_FILE))
            if errMsg:
                logging.warning(f"配置文件验证失败: {errMsg}")
                QMessageBox.warning(self, "Error", errMsg)
                return

            self.is_running = True
            self.btn_run.setText("停止运行")
            self.btn_run.setStyleSheet("background: #C0392B;")
            self.prog.show()
            self.grp.buttons()[0].setEnabled(False)
            self.grp.buttons()[1].setEnabled(False)

            checked_id = self.grp.checkedId()
            if checked_id == 0:
                opt = {"action": "普通签到", "code": "2"}
            elif checked_id == 1:
                opt = {"action": "普通签退", "code": "1"}
            elif checked_id == 2:
                opt = {"action": "拍照签到", "image": "bin/photo.jpg"}

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
        self.grp.buttons()[0].setEnabled(True)
        self.grp.buttons()[1].setEnabled(True)

        if success:
            # 成功后弹出赞助提交框
            SponsorSubmitDialog(self).exec()
        else:
            if msg != "任务已停止":
                # QMessageBox.critical(self, "提示", msg)
                ToastManager.instance().show(msg, "error")
