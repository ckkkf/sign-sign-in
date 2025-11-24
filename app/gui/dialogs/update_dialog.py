from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QHBoxLayout,
    QPushButton,
    QTextEdit,
)

from app.config.common import VERSION
from app.gui.components.toast import ToastManager


class UpdateDialog(QDialog):
    """更新对话框"""

    def __init__(self, update_info: dict, parent=None):
        super().__init__(parent)
        self.update_info = update_info
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
        current_version = self.update_info.get("current_version", VERSION)
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

        # 按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        download_url = self.update_info.get("download_url")
        if download_url:
            btn_download = QPushButton("前往下载")
            btn_download.setObjectName("PrimaryBtn")
            btn_download.clicked.connect(lambda: self._open_download_url(download_url))
            btn_row.addWidget(btn_download)

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


