import os

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QHBoxLayout,
    QPushButton,
    QProgressBar,
    QTextEdit,
)

from app.config.common import PROJECT_VERSION
from app.gui.components.toast import ToastManager
from app.workers.update_worker import UpdateDownloadWorker


class UpdateDialog(QDialog):
    """更新对话框"""

    def __init__(self, update_info: dict, parent=None):
        super().__init__(parent)
        self.update_info = update_info
        self.download_url = self.update_info.get("download_url")
        self.download_worker = None
        self.download_file_path = None
        self.setWindowTitle("检查更新")
        self.resize(500, 400)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self._setup_style()
        self._setup_ui()

    def _setup_style(self):
        self.setStyleSheet("""
            QDialog {
                background: #0F111C;
                color: #E8EBFF;
            }
            QLabel {
                color: #9BA3C6;
            }
            #TitleLabel {
                color: #F5F6FF;
                font-size: 16pt;
                font-weight: bold;
            }
            #VersionLabel {
                color: #BAC3FF;
                font-size: 11pt;
            }
            QTextEdit {
                background: #1E2238;
                border: 1px solid #2F3654;
                border-radius: 10px;
                padding: 12px;
                color: #F5F6FF;
                font-size: 10pt;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 10px;
                margin: 6px 2px 6px 0;
            }
            QScrollBar::handle:vertical {
                background: #4A537C;
                min-height: 28px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background: #6471A8;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
                background: transparent;
                border: none;
            }
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {
                background: transparent;
            }
            QScrollBar:horizontal {
                background: transparent;
                height: 10px;
                margin: 0 6px 2px 6px;
            }
            QScrollBar::handle:horizontal {
                background: #4A537C;
                min-width: 28px;
                border-radius: 5px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #6471A8;
            }
            QScrollBar::add-line:horizontal,
            QScrollBar::sub-line:horizontal {
                width: 0px;
                background: transparent;
                border: none;
            }
            QScrollBar::add-page:horizontal,
            QScrollBar::sub-page:horizontal {
                background: transparent;
            }
            QPushButton#PrimaryBtn {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4E8BFF, stop:1 #7C5BFF);
                color: white;
                border: none;
                border-radius: 22px;
                padding: 10px 20px;
                font-weight: bold;
            }
            QPushButton#PrimaryBtn:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #5C96FF, stop:1 #8A68FF);
            }
            QPushButton#OutlinedBtn {
                background: transparent;
                border: 1px solid #3A4062;
                color: #9BA3C6;
                border-radius: 22px;
                padding: 10px 16px;
                font-weight: bold;
            }
            QPushButton#OutlinedBtn:hover {
                border-color: #7C89FF;
                color: #F5F6FF;
            }
        """)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # 标题
        title = QLabel("发现新版本！")
        title.setObjectName("TitleLabel")
        layout.addWidget(title)

        # 版本信息
        current_version = self.update_info.get("current_version", PROJECT_VERSION)
        latest_version = self.update_info.get("latest_version", "未知")
        version_text = f"当前版本：{current_version}\n最新版本：{latest_version}"
        version_label = QLabel(version_text)
        version_label.setObjectName("VersionLabel")
        layout.addWidget(version_label)

        # 更新内容
        release_notes = self.update_info.get("release_notes", "暂无更新说明")
        notes_edit = QTextEdit()
        notes_edit.setReadOnly(True)
        notes_edit.setPlainText(release_notes)
        layout.addWidget(notes_edit)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.hide()
        layout.addWidget(self.progress)

        # 按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.btn_download = None
        if self.download_url:
            self.btn_download = QPushButton("自动下载")
            self.btn_download.setObjectName("PrimaryBtn")
            self.btn_download.clicked.connect(self._start_auto_download)
            btn_row.addWidget(self.btn_download)

            btn_browser = QPushButton("浏览器下载")
            btn_browser.setObjectName("OutlinedBtn")
            btn_browser.clicked.connect(lambda: self._open_download_url(self.download_url))
            btn_row.addWidget(btn_browser)

        btn_close = QPushButton("关闭")
        btn_close.setObjectName("OutlinedBtn")
        btn_close.clicked.connect(self.close)
        btn_row.addWidget(btn_close)

        layout.addLayout(btn_row)

    def _open_download_url(self, url: str):
        """打开下载链接"""
        try:
            QDesktopServices.openUrl(QUrl(url))
        except Exception as e:
            ToastManager.instance().show(f"打开链接失败：{e}", "error")

    def _start_auto_download(self):
        if not self.download_url:
            ToastManager.instance().show("下载链接为空", "error")
            return

        if self.download_worker and self.download_worker.isRunning():
            ToastManager.instance().show("正在下载，请稍候...", "info")
            return

        save_dir = os.path.join(os.path.expanduser("~"), "Downloads", "sign-sign-in")
        self.download_worker = UpdateDownloadWorker(self.download_url, save_dir=save_dir, timeout=120)
        self.download_worker.progress_signal.connect(self._on_download_progress)
        self.download_worker.status_signal.connect(self._on_download_status)
        self.download_worker.result_signal.connect(self._on_download_result)

        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFormat("准备下载...")
        self.progress.setTextVisible(True)
        self.progress.show()
        if self.btn_download:
            self.btn_download.setEnabled(False)
            self.btn_download.setText("下载中...")

        self.download_worker.start()
        ToastManager.instance().show("开始下载更新包...", "info")

    def _on_download_progress(self, value: int):
        if value < 0:
            # 未知总大小：显示忙碌动画
            self.progress.setRange(0, 0)
            return

        if self.progress.maximum() == 0:
            # 从忙碌动画切回百分比
            self.progress.setRange(0, 100)
        self.progress.setValue(max(0, min(100, value)))

    def _on_download_status(self, text: str):
        if text:
            self.progress.setFormat(text)

    def _on_download_result(self, success: bool, data: dict):
        if self.btn_download:
            self.btn_download.setEnabled(True)

        if not success:
            if self.btn_download:
                self.btn_download.setText("自动下载")
            err = data.get("error", "下载失败")
            ToastManager.instance().show(f"下载失败：{err}", "error")
            return

        self.progress.setRange(0, 100)
        self.progress.setValue(100)
        self.progress.setFormat("下载完成")
        self.download_file_path = data.get("file_path")
        if self.btn_download:
            self.btn_download.setText("打开目录")
            self.btn_download.clicked.disconnect()
            self.btn_download.clicked.connect(self._open_download_folder)

        ToastManager.instance().show(f"下载完成：{self.download_file_path}", "success")

    def _open_download_folder(self):
        if not self.download_file_path:
            return
        folder = os.path.dirname(self.download_file_path)
        QDesktopServices.openUrl(QUrl.fromLocalFile(folder))


class UpdateCheckResultDialog(QDialog):
    """更新检查结果对话框（无更新时显示）"""

    def __init__(self, message: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("检查更新")
        self.resize(400, 200)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self._setup_style()
        self._setup_ui(message)

    def _setup_style(self):
        self.setStyleSheet("""
            QDialog {
                background: #0F111C;
                color: #E8EBFF;
            }
            QLabel {
                color: #9BA3C6;
                font-size: 11pt;
            }
            QPushButton#OutlinedBtn {
                background: transparent;
                border: 1px solid #3A4062;
                color: #9BA3C6;
                border-radius: 22px;
                padding: 10px 16px;
                font-weight: bold;
            }
            QPushButton#OutlinedBtn:hover {
                border-color: #7C89FF;
                color: #F5F6FF;
            }
        """)

    def _setup_ui(self, message: str):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        label = QLabel(message)
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_close = QPushButton("确定")
        btn_close.setObjectName("OutlinedBtn")
        btn_close.clicked.connect(self.close)
        btn_row.addWidget(btn_close)

        layout.addLayout(btn_row)


