import os
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.config.common import (
    BASE_DIR,
    CONFIG_FILE,
    PROJECT_GITHUB,
    PROJECT_VERSION,
    UPDATE_ASSET_CACHE_FILE,
    UPDATE_SETTINGS_FILE,
)
from app.gui.components.toast import ToastManager
from app.utils.files import read_config, save_json_file
from app.workers.update_worker import UpdateCheckWorker, UpdateDownloadWorker


SOURCE_LABELS = {
    "github": "GitHub 官方",
    # "gh_proxy": "gh-proxy 主站",
    "gh_proxy_hk": "gh-proxy 香港",
    "gh_proxy_cdn": "gh-proxy Fastly",
    "gh_proxy_edgeone": "gh-proxy EdgeOne",
    "custom": "自定义",
}


class UpdateDialog(QDialog):
    """更新中心。"""

    def __init__(self, update_info: dict, parent=None):
        super().__init__(parent)
        self.update_info = update_info or {}
        self.has_loaded_update_data = bool(self.update_info)
        self.download_worker = None
        self.history_worker = None
        self.downloaded_files: Dict[str, str] = {}
        self.release_rows: Dict[str, Dict[str, Any]] = {}
        self.current_history_cursor = self.update_info.get("history_cursor")
        self.latest_release = dict(self.update_info.get("latest_release") or {})
        self.history_releases = list(self.update_info.get("history_releases") or [])
        self.repo = self.update_info.get("repo") or PROJECT_GITHUB.split("github.com/")[-1]
        self.current_version = self.update_info.get("current_version", PROJECT_VERSION)
        self.latest_version = self.update_info.get("latest_version", self.latest_release.get("tag_name") or "未知")
        self.release_asset_cache: Dict[str, Dict[str, Any]] = self._load_persisted_asset_cache()
        self._apply_cached_assets_to_releases()

        self.setWindowTitle("更新中心")
        self.resize(780, 600)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self._setup_style()
        self._setup_ui()
        self._render_update_state()
        self._render_release_notes()
        self._render_history_list(reset=True)

    def _setup_style(self):
        self.setStyleSheet(
            """
            QDialog { background: #0F111C; color: #E8EBFF; }
            QLabel { color: #9BA3C6; font-size: 9pt; }
            QLabel#TitleLabel { color: #F5F6FF; font-size: 14pt; font-weight: bold; }
            QLabel#VersionLabel { color: #BAC3FF; font-size: 9.5pt; }
            QLabel#SectionLabel { color: #F2F4FF; font-size: 10pt; font-weight: bold; }
            QLabel#HintLabel { color: #7E88AE; font-size: 8.5pt; }
            QLabel#ReleaseTitle { color: #F5F6FF; font-size: 10pt; font-weight: bold; }
            QLabel#HeroVersion { color: #F8FAFF; font-size: 18pt; font-weight: bold; }
            QLabel#HeroMeta { color: #C6D0F7; font-size: 9pt; }
            QLabel#HeroPath { color: #8EC5FF; font-size: 10.5pt; font-weight: bold; }
            QLabel#VersionPill {
                color: #EFF4FF; background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.16);
                border-radius: 13px; padding: 3px 10px; font-size: 8.5pt; font-weight: bold;
            }
            QLabel#StatusBadge {
                color: #F3F7FF; background: rgba(87, 138, 255, 0.22); border: 1px solid rgba(135, 175, 255, 0.36);
                border-radius: 12px; padding: 3px 10px; font-size: 8.5pt; font-weight: bold;
            }
            QFrame#Card { background: #16192A; border: 1px solid #2A2F45; border-radius: 12px; }
            QFrame#LatestCard {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(33,44,84,0.98), stop:1 rgba(24,28,47,0.98));
                border: 1px solid rgba(96, 132, 255, 0.58);
                border-radius: 14px;
            }
            QFrame#HistoryHeaderRow {
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 10px;
            }
            QFrame#HistoryRow {
                background: rgba(255,255,255,0.02);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 10px;
            }
            QLabel#TableHeader {
                color: #8992B8; font-size: 8.4pt; font-weight: bold;
            }
            QTextEdit, QLineEdit, QComboBox {
                background: #1E2238; border: 1px solid #2F3654; border-radius: 10px; padding: 8px; color: #F5F6FF;
                font-size: 9pt;
            }
            QPushButton#PrimaryBtn {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4E8BFF, stop:1 #7C5BFF);
                color: white; border: none; border-radius: 16px; padding: 7px 14px; font-size: 9pt; font-weight: bold;
            }
            QPushButton#PrimaryBtn:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6298FF, stop:1 #8B68FF);
            }
            QPushButton#PrimaryBtn:pressed {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3E78E8, stop:1 #6846E6);
            }
            QPushButton#PrimaryBtn:disabled {
                background: #2C3658; color: #7E89B1;
            }
            QPushButton#OutlinedBtn {
                background: transparent; border: 1px solid #3A4062; color: #9BA3C6; border-radius: 16px; padding: 6px 12px; font-size: 9pt;
            }
            QPushButton#OutlinedBtn:hover {
                background: rgba(255,255,255,0.05); border-color: #566185; color: #E2E8FF;
            }
            QPushButton#OutlinedBtn:pressed {
                background: rgba(255,255,255,0.09); border-color: #6A769F; color: #F3F6FF;
            }
            QPushButton#OutlinedBtn:disabled {
                background: transparent; border-color: #2B314A; color: #6E779A;
            }
            QPushButton#DangerBtn {
                background: transparent; border: 1px solid #7A3A54; color: #FF9BB7; border-radius: 16px; padding: 6px 12px; font-size: 9pt;
            }
            QPushButton#DangerBtn:hover {
                background: rgba(255, 107, 149, 0.08); border-color: #A44C72; color: #FFD2DF;
            }
            QPushButton#DangerBtn:pressed {
                background: rgba(255, 107, 149, 0.14); border-color: #BE5D84; color: #FFE7EF;
            }
            QPushButton#DangerBtn:disabled {
                background: transparent; border-color: #4F2D3A; color: #8D6574;
            }
            QPushButton#TextBtn {
                background: transparent; border: none; color: #90B4FF; padding: 3px 6px; font-size: 8.8pt; font-weight: bold;
                border-radius: 8px;
            }
            QPushButton#TextBtn:hover {
                color: #D7E5FF; background: rgba(144, 180, 255, 0.14);
            }
            QPushButton#TextBtn:pressed {
                color: #F2F7FF; background: rgba(144, 180, 255, 0.22);
            }
            QPushButton#TextBtn:disabled {
                color: #6E7DAB; background: transparent;
            }
            QScrollArea { border: none; background: transparent; }
            QProgressBar {
                background: #1E2238; border: 1px solid #2F3654; border-radius: 8px; color: #F5F6FF; text-align: center;
            }
            QProgressBar::chunk { background: #5C96FF; border-radius: 7px; }
            """
        )

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        header_row = QHBoxLayout()
        header_row.setSpacing(10)

        title_block = QVBoxLayout()
        title_block.setContentsMargins(0, 0, 0, 0)
        title_block.setSpacing(2)

        title = QLabel("更新中心")
        title.setObjectName("TitleLabel")
        title_block.addWidget(title)

        self.status_label = QLabel("")
        self.status_label.setObjectName("VersionLabel")
        self.status_label.setWordWrap(True)
        title_block.addWidget(self.status_label)
        header_row.addLayout(title_block, 1)

        self.btn_refresh = QPushButton("拉取")
        self.btn_refresh.setObjectName("PrimaryBtn")
        self.btn_refresh.clicked.connect(self._refresh_update_center)
        header_row.addWidget(self.btn_refresh, 0, Qt.AlignTop)
        layout.addLayout(header_row)

        source_card = QFrame()
        source_card.setObjectName("Card")
        source_layout = QVBoxLayout(source_card)
        source_layout.setContentsMargins(10, 10, 10, 10)
        source_layout.setSpacing(6)

        source_row = QHBoxLayout()
        source_row.setSpacing(8)
        source_title = QLabel("下载源")
        source_title.setObjectName("SectionLabel")
        source_row.addWidget(source_title)
        self.source_combo = QComboBox()
        for key, label in SOURCE_LABELS.items():
            self.source_combo.addItem(label, key)
        self.source_combo.currentIndexChanged.connect(self._on_source_changed)
        source_row.addWidget(self.source_combo, 1)

        self.custom_source_input = QLineEdit()
        self.custom_source_input.setPlaceholderText("自定义下载源，支持 {url} 或 URL 前缀")
        self.custom_source_input.editingFinished.connect(self._on_custom_source_changed)
        source_row.addWidget(self.custom_source_input, 2)
        source_layout.addLayout(source_row)

        download_dir_row = QHBoxLayout()
        download_dir_row.setSpacing(8)
        download_dir_title = QLabel("下载路径")
        download_dir_title.setObjectName("SectionLabel")
        download_dir_row.addWidget(download_dir_title)
        self.download_dir_input = QLineEdit()
        self.download_dir_input.setPlaceholderText("默认下载到系统 Downloads/sign-sign-in")
        self.download_dir_input.editingFinished.connect(self._on_download_dir_changed)
        download_dir_row.addWidget(self.download_dir_input, 1)
        self.btn_browse_download_dir = QPushButton("浏览")
        self.btn_browse_download_dir.setObjectName("OutlinedBtn")
        self.btn_browse_download_dir.clicked.connect(self._browse_download_dir)
        download_dir_row.addWidget(self.btn_browse_download_dir)
        self.btn_reset_download_dir = QPushButton("默认")
        self.btn_reset_download_dir.setObjectName("OutlinedBtn")
        self.btn_reset_download_dir.clicked.connect(self._reset_download_dir)
        download_dir_row.addWidget(self.btn_reset_download_dir)
        self.btn_open_download_dir = QPushButton("↗ 打开目录")
        self.btn_open_download_dir.setObjectName("OutlinedBtn")
        self.btn_open_download_dir.clicked.connect(self._open_download_dir)
        download_dir_row.addWidget(self.btn_open_download_dir)
        source_layout.addLayout(download_dir_row)
        layout.addWidget(source_card)

        latest_card = QFrame()
        latest_card.setObjectName("LatestCard")
        latest_layout = QVBoxLayout(latest_card)
        latest_layout.setContentsMargins(10, 10, 10, 10)
        latest_layout.setSpacing(6)

        latest_summary_row = QHBoxLayout()
        latest_summary_row.setSpacing(8)

        self.latest_summary_label = QLabel("")
        self.latest_summary_label.setObjectName("HeroVersion")
        self.latest_summary_label.setWordWrap(True)
        latest_summary_row.addWidget(self.latest_summary_label, 0, Qt.AlignVCenter)

        self.latest_upgrade_path_label = QLabel("")
        self.latest_upgrade_path_label.setObjectName("HeroPath")
        self.latest_upgrade_path_label.setWordWrap(True)
        latest_summary_row.addWidget(self.latest_upgrade_path_label, 0, Qt.AlignVCenter)

        latest_summary_row.addStretch()

        self.latest_badge = QLabel("新版本")
        self.latest_badge.setObjectName("StatusBadge")
        latest_summary_row.addWidget(self.latest_badge, 0, Qt.AlignVCenter)
        self.latest_version_pill = QLabel("")
        self.latest_version_pill.setObjectName("VersionPill")
        latest_summary_row.addWidget(self.latest_version_pill, 0, Qt.AlignVCenter)
        latest_layout.addLayout(latest_summary_row)

        self.latest_meta_label = QLabel("")
        self.latest_meta_label.setObjectName("HeroMeta")
        self.latest_meta_label.setWordWrap(True)
        latest_layout.addWidget(self.latest_meta_label)

        latest_actions = QHBoxLayout()
        latest_actions.setSpacing(8)
        self.btn_latest_browser = QPushButton("↗ 浏览器")
        self.btn_latest_browser.setObjectName("OutlinedBtn")
        self.btn_latest_browser.clicked.connect(lambda: self._open_release_download(self.latest_release))
        latest_actions.addWidget(self.btn_latest_browser)
        self.btn_latest_download = QPushButton("下载")
        self.btn_latest_download.setObjectName("PrimaryBtn")
        self.btn_latest_download.clicked.connect(lambda: self._download_release(self.latest_release))
        latest_actions.addWidget(self.btn_latest_download)
        self.btn_latest_install = QPushButton("安装")
        self.btn_latest_install.setObjectName("OutlinedBtn")
        self.btn_latest_install.clicked.connect(lambda: self._install_release(self.latest_release))
        latest_actions.addWidget(self.btn_latest_install)
        self.btn_latest_compare = QPushButton("↗ 对比")
        self.btn_latest_compare.setObjectName("OutlinedBtn")
        self.btn_latest_compare.clicked.connect(lambda: self._open_release_compare(self.latest_release))
        latest_actions.addWidget(self.btn_latest_compare)
        latest_actions.addStretch()
        self.btn_toggle_latest_notes = QPushButton("展开说明")
        self.btn_toggle_latest_notes.setObjectName("TextBtn")
        self.btn_toggle_latest_notes.clicked.connect(self._toggle_latest_notes)
        latest_actions.addWidget(self.btn_toggle_latest_notes)
        latest_layout.addLayout(latest_actions)

        self.notes_edit = QTextEdit()
        self.notes_edit.setReadOnly(True)
        self.notes_edit.setMinimumHeight(124)
        self.notes_edit.hide()
        latest_layout.addWidget(self.notes_edit)
        layout.addWidget(latest_card)

        history_card = QFrame()
        history_card.setObjectName("Card")
        history_layout = QVBoxLayout(history_card)
        history_layout.setContentsMargins(10, 10, 10, 10)
        history_layout.setSpacing(6)

        history_header = QHBoxLayout()
        history_title = QLabel("历史版本")
        history_title.setObjectName("SectionLabel")
        history_header.addWidget(history_title)
        history_hint = QLabel("说明默认折叠")
        history_hint.setObjectName("HintLabel")
        history_header.addWidget(history_hint)
        history_header.addStretch()
        self.btn_load_more = QPushButton("加载更多")
        self.btn_load_more.setObjectName("OutlinedBtn")
        self.btn_load_more.clicked.connect(self._load_more_history)
        history_header.addWidget(self.btn_load_more)
        history_layout.addLayout(history_header)

        table_header = QFrame()
        table_header.setObjectName("HistoryHeaderRow")
        table_header_layout = QHBoxLayout(table_header)
        table_header_layout.setContentsMargins(12, 8, 12, 8)
        table_header_layout.setSpacing(8)
        version_header = QLabel("版本")
        version_header.setObjectName("TableHeader")
        table_header_layout.addWidget(version_header, 1)
        date_header = QLabel("日期")
        date_header.setObjectName("TableHeader")
        date_header.setAlignment(Qt.AlignCenter)
        date_header.setFixedWidth(88)
        table_header_layout.addWidget(date_header)
        action_header = QLabel("操作")
        action_header.setObjectName("TableHeader")
        action_header.setAlignment(Qt.AlignCenter)
        action_header.setFixedWidth(268)
        table_header_layout.addWidget(action_header)
        detail_header = QLabel("说明")
        detail_header.setObjectName("TableHeader")
        detail_header.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        detail_header.setFixedWidth(70)
        table_header_layout.addWidget(detail_header)
        history_layout.addWidget(table_header)

        self.history_scroll = QScrollArea()
        self.history_scroll.setWidgetResizable(True)
        self.history_container = QWidget()
        self.history_list_layout = QVBoxLayout(self.history_container)
        self.history_list_layout.setContentsMargins(0, 0, 0, 0)
        self.history_list_layout.setSpacing(8)
        self.history_list_layout.addStretch()
        self.history_scroll.setWidget(self.history_container)
        self.history_scroll.setMinimumHeight(300)
        history_layout.addWidget(self.history_scroll)
        layout.addWidget(history_card, 1)

        self.progress = QProgressBar()
        self.progress.hide()
        layout.addWidget(self.progress)

        self.download_action_row = QHBoxLayout()
        self.download_action_row.setContentsMargins(0, 0, 0, 0)
        self.download_action_row.setSpacing(8)
        self.download_action_row.addStretch()
        self.btn_open_last_download_dir = QPushButton("↗ 打开目录")
        self.btn_open_last_download_dir.setObjectName("OutlinedBtn")
        self.btn_open_last_download_dir.clicked.connect(self._open_download_dir)
        self.download_action_row.addWidget(self.btn_open_last_download_dir)
        self.btn_pause_download = QPushButton("暂停下载")
        self.btn_pause_download.setObjectName("OutlinedBtn")
        self.btn_pause_download.clicked.connect(self._toggle_pause_download)
        self.download_action_row.addWidget(self.btn_pause_download)
        self.btn_stop_download = QPushButton("停止下载")
        self.btn_stop_download.setObjectName("DangerBtn")
        self.btn_stop_download.clicked.connect(self._stop_active_download)
        self.download_action_row.addWidget(self.btn_stop_download)
        layout.addLayout(self.download_action_row)
        self._set_download_controls_visible(False)

        footer = QHBoxLayout()
        footer.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.setObjectName("OutlinedBtn")
        close_btn.clicked.connect(self.close)
        footer.addWidget(close_btn)
        layout.addLayout(footer)

        for button in self.findChildren(QPushButton):
            button.setCursor(Qt.PointingHandCursor)

        self._load_source_controls()
        self._load_download_dir_controls()
        self._sync_latest_buttons()

    def _render_update_state(self):
        latest_date = self._release_date_text(self.latest_release)
        if not self.has_loaded_update_data:
            self.status_label.setText("选源后拉取更新")
            self.latest_badge.setText("未拉取")
            self.latest_summary_label.setText("先拉取更新")
            self.latest_upgrade_path_label.setText(f"{self.current_version}  →  --")
            self.latest_meta_label.setText(f"当前 {self.current_version}")
        elif self.update_info.get("has_update"):
            self.status_label.setText("发现新版本")
            self.latest_badge.setText("可更新")
            self.latest_summary_label.setText(f"升级到 {self.latest_version}")
            self.latest_upgrade_path_label.setText(f"{self.current_version}  →  {self.latest_version}")
            meta = f"当前 {self.current_version}  ·  最新 {self.latest_version}"
            if latest_date:
                meta += f"  ·  {latest_date}"
            self.latest_meta_label.setText(meta)
        else:
            self.status_label.setText("已是最新版本")
            self.latest_badge.setText("最新")
            self.latest_summary_label.setText(f"{self.current_version} 已是最新版")
            self.latest_upgrade_path_label.setText(f"{self.current_version}  ✓")
            meta = f"当前 {self.current_version}"
            if latest_date:
                meta += f"  ·  {latest_date}"
            self.latest_meta_label.setText(meta)
        self.latest_version_pill.setText("Latest" if not self.has_loaded_update_data else f"Latest {self.latest_version}")

    def _render_release_notes(self):
        if not self.has_loaded_update_data:
            self.notes_edit.setPlainText("点击“拉取”获取说明")
            return
        self.notes_edit.setPlainText(self.latest_release.get("body") or self.update_info.get("release_notes") or "暂无更新说明")

    def _set_download_controls_visible(self, visible: bool):
        self.btn_open_last_download_dir.setVisible(visible)
        self.btn_pause_download.setVisible(visible)
        self.btn_stop_download.setVisible(visible)
        if not visible:
            self.btn_open_last_download_dir.setEnabled(False)
            self.btn_pause_download.setText("暂停下载")
            self.btn_pause_download.setEnabled(False)
            self.btn_stop_download.setEnabled(False)
            return
        self.btn_open_last_download_dir.setEnabled(True)
        self.btn_pause_download.setEnabled(True)
        self.btn_stop_download.setEnabled(True)

    def _toggle_pause_download(self):
        if not self.download_worker or not self.download_worker.isRunning():
            return
        if self.download_worker.is_paused():
            self.download_worker.resume_download()
            self.btn_pause_download.setText("暂停下载")
            ToastManager.instance().show("继续下载", "info")
            return
        self.download_worker.pause_download()
        self.btn_pause_download.setText("继续下载")
        ToastManager.instance().show("下载已暂停", "info")

    def _stop_active_download(self):
        if not self.download_worker or not self.download_worker.isRunning():
            return
        self.btn_pause_download.setEnabled(False)
        self.btn_stop_download.setEnabled(False)
        self.progress.setFormat("正在停止下载...")
        self.download_worker.stop_download()

    def _release_date_text(self, release: dict) -> str:
        published_at = str((release or {}).get("published_at") or "").strip()
        return published_at[:10] if published_at else ""

    def _set_latest_notes_visible(self, visible: bool):
        self.notes_edit.setHidden(not visible)
        self.btn_toggle_latest_notes.setText("收起说明" if visible else "展开说明")

    def _toggle_latest_notes(self):
        self._set_latest_notes_visible(self.notes_edit.isHidden())

    def _clear_history_rows(self):
        while self.history_list_layout.count() > 1:
            item = self.history_list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.release_rows.clear()

    def _render_history_list(self, reset: bool = False):
        if reset:
            self._clear_history_rows()
        for release in self.history_releases:
            self._append_history_row(release)
        self.btn_load_more.setEnabled(bool(self.current_history_cursor))
        self.btn_load_more.setVisible(bool(self.current_history_cursor))

    def _append_history_row(self, release: dict):
        tag = release.get("tag_name") or ""
        if not tag or tag in self.release_rows:
            return

        card = QFrame()
        card.setObjectName("HistoryRow")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        version_block = QVBoxLayout()
        version_block.setContentsMargins(0, 0, 0, 0)
        version_block.setSpacing(2)
        title = QLabel(f"{release.get('name') or tag}")
        title.setObjectName("ReleaseTitle")
        version_block.addWidget(title)
        tag_label = QLabel(tag)
        tag_label.setObjectName("HintLabel")
        version_block.addWidget(tag_label)
        title_row.addLayout(version_block, 1)
        published_label = QLabel(self._release_date_text(release))
        published_label.setObjectName("HintLabel")
        published_label.setAlignment(Qt.AlignCenter)
        published_label.setFixedWidth(88)
        title_row.addWidget(published_label)

        action_row = QHBoxLayout()
        action_row.setSpacing(6)
        btn_browser = QPushButton("↗ 浏览器")
        btn_browser.setObjectName("OutlinedBtn")
        btn_browser.setFixedWidth(72)
        btn_browser.clicked.connect(lambda _, item=release: self._open_release_download(item))
        action_row.addWidget(btn_browser)

        btn_download = QPushButton("下载")
        btn_download.setObjectName("PrimaryBtn")
        btn_download.setFixedWidth(56)
        btn_download.clicked.connect(lambda _, item=release: self._download_release(item))
        action_row.addWidget(btn_download)

        btn_install = QPushButton("安装")
        btn_install.setObjectName("OutlinedBtn")
        btn_install.setFixedWidth(56)
        btn_install.clicked.connect(lambda _, item=release: self._install_release(item))
        action_row.addWidget(btn_install)

        btn_delete = QPushButton("删除")
        btn_delete.setObjectName("DangerBtn")
        btn_delete.setFixedWidth(56)
        btn_delete.clicked.connect(lambda _, item=release: self._delete_downloaded_release(item))
        action_row.addWidget(btn_delete)

        btn_compare = QPushButton("↗ 对比")
        btn_compare.setObjectName("OutlinedBtn")
        btn_compare.setFixedWidth(68)
        btn_compare.clicked.connect(lambda _, item=release: self._open_release_compare(item))
        action_row.addWidget(btn_compare)
        title_row.addLayout(action_row)

        btn_toggle_notes = QPushButton("展开说明")
        btn_toggle_notes.setObjectName("TextBtn")
        btn_toggle_notes.clicked.connect(lambda _, release_tag=tag: self._toggle_release_notes(release_tag))
        title_row.addWidget(btn_toggle_notes)
        layout.addLayout(title_row)

        notes = QTextEdit()
        notes.setReadOnly(True)
        notes.setMinimumHeight(110)
        notes.setMaximumHeight(150)
        notes.setPlainText(release.get("body") or "暂无更新说明")
        notes.hide()
        layout.addWidget(notes)

        self.history_list_layout.insertWidget(self.history_list_layout.count() - 1, card)
        self.release_rows[tag] = {
            "release": dict(release),
            "download": btn_download,
            "install": btn_install,
            "delete": btn_delete,
            "compare": btn_compare,
            "notes": notes,
            "toggle_notes": btn_toggle_notes,
        }
        self._sync_release_buttons(tag)

    def _set_release_notes_visible(self, tag: str, visible: bool):
        row = self.release_rows.get(tag)
        if not row:
            return
        row["notes"].setHidden(not visible)
        row["toggle_notes"].setText("收起说明" if visible else "展开说明")

    def _toggle_release_notes(self, tag: str):
        row = self.release_rows.get(tag)
        if not row:
            return
        self._set_release_notes_visible(tag, row["notes"].isHidden())

    def _sync_latest_buttons(self):
        self.btn_latest_install.setEnabled(True)
        self.btn_latest_browser.setEnabled(True)
        self.btn_latest_download.setEnabled(True)
        self.btn_latest_compare.setEnabled(True)

    def _sync_release_buttons(self, tag: str):
        row = self.release_rows.get(tag)
        if not row:
            return
        row["install"].setEnabled(True)
        row["delete"].setEnabled(True)
        row["download"].setEnabled(True)
        row["compare"].setEnabled(True)

    def _release_key(self, release: dict) -> str:
        return str((release or {}).get("tag_name") or "")

    def _download_file_for_release(self, release: dict) -> str:
        return self.downloaded_files.get(self._release_key(release), "")

    def _asset_cache_entry(self, asset_info: dict) -> dict:
        entry = {
            "raw_download_url": str(asset_info.get("raw_download_url") or "").strip(),
            "download_name": str(asset_info.get("download_name") or "").strip(),
            "asset_available": bool(asset_info.get("asset_available")),
            "install_kind": str(asset_info.get("install_kind") or "").strip(),
            "install_supported": bool(asset_info.get("install_supported")),
        }
        return entry

    def _normalize_asset_info(self, asset_info: dict) -> dict:
        normalized = dict(asset_info or {})
        raw_url = str(normalized.get("raw_download_url") or "").strip()
        if raw_url and not normalized.get("download_url"):
            normalized["download_url"] = UpdateCheckWorker._apply_download_source(raw_url)
        return normalized

    def _load_persisted_asset_cache(self) -> Dict[str, Dict[str, Any]]:
        cache = self._load_asset_cache_file()
        if not cache:
            cache = self._load_legacy_asset_cache()
            if cache:
                self._persist_asset_cache_payload(cache)
        if not isinstance(cache, dict):
            return {}
        normalized: Dict[str, Dict[str, Any]] = {}
        for tag, payload in cache.items():
            if not tag or not isinstance(payload, dict):
                continue
            normalized[str(tag)] = self._asset_cache_entry(payload)
        return normalized

    def _persist_asset_cache(self):
        payload = {tag: dict(value) for tag, value in self.release_asset_cache.items() if tag}
        self._persist_asset_cache_payload(payload)

    def _load_asset_cache_file(self) -> Dict[str, Any]:
        try:
            payload = read_config(UPDATE_ASSET_CACHE_FILE)
        except Exception:
            return {}
        if not isinstance(payload, dict):
            return {}
        if isinstance(payload.get("settings"), dict):
            return {}
        return payload

    def _load_legacy_asset_cache(self) -> Dict[str, Any]:
        config = self._load_main_config()
        update_settings = ((config.get("settings") or {}).get("update") or {})
        cache = update_settings.get("asset_cache") or {}
        return cache if isinstance(cache, dict) else {}

    def _persist_asset_cache_payload(self, payload: Dict[str, Any]):
        save_json_file(UPDATE_ASSET_CACHE_FILE, payload if isinstance(payload, dict) else {})

    def _apply_cached_assets_to_releases(self):
        for release in [self.latest_release] + self.history_releases:
            tag = self._release_key(release)
            cached = self.release_asset_cache.get(tag)
            if not cached:
                continue
            release.update(self._normalize_asset_info(cached))

    def _merge_release_asset(self, release: dict, asset_info: dict):
        if not release or not asset_info:
            return
        asset_info = self._normalize_asset_info(asset_info)
        tag = self._release_key(release)
        if tag:
            cache_entry = self._asset_cache_entry(asset_info)
            self.release_asset_cache[tag] = cache_entry
            self._persist_asset_cache()
        for target in [self.latest_release] + self.history_releases:
            if self._release_key(target) == tag:
                target.update(asset_info)
        row = self.release_rows.get(tag)
        if row:
            row["release"].update(asset_info)
        release.update(asset_info)
        self._sync_latest_buttons()
        if tag:
            self._sync_release_buttons(tag)

    def _ensure_release_download_ready(self, release: dict) -> bool:
        if (release or {}).get("download_url"):
            return True
        tag = self._release_key(release)
        if not tag:
            return False
        if tag in self.release_asset_cache:
            self._merge_release_asset(release, self.release_asset_cache[tag])
            return bool((release or {}).get("download_url"))
        try:
            worker = UpdateCheckWorker(PROJECT_GITHUB, self.current_version, timeout=10)
            asset_info = worker.get_release_asset(PROJECT_GITHUB, tag)
        except Exception:
            asset_info = {}
        self._merge_release_asset(release, asset_info)
        return bool((release or {}).get("download_url"))

    def _load_main_config(self) -> dict:
        try:
            return read_config(CONFIG_FILE)
        except Exception:
            return {}

    def _load_update_settings(self) -> dict:
        try:
            payload = read_config(UPDATE_SETTINGS_FILE)
        except Exception:
            payload = {}
        if isinstance(payload, dict) and not isinstance(payload.get("settings"), dict):
            return payload
        config = self._load_main_config()
        update_settings = ((config.get("settings") or {}).get("update") or {})
        return dict(update_settings) if isinstance(update_settings, dict) else {}

    def _persist_update_settings(self, update_settings: dict):
        save_json_file(UPDATE_SETTINGS_FILE, dict(update_settings or {}))

    def _load_source_controls(self):
        update_settings = self._load_update_settings()
        source_name = UpdateCheckWorker._get_update_source_name(update_settings)
        custom_sources = update_settings.get("sources") or {}
        index = self.source_combo.findData(source_name)
        if index < 0:
            index = self.source_combo.findData("custom")
        self.source_combo.setCurrentIndex(max(0, index))
        self.custom_source_input.setText(str(custom_sources.get("custom", "")))
        self.custom_source_input.setVisible(self.source_combo.currentData() == "custom")

    def _default_download_dir(self) -> str:
        return os.path.join(os.path.expanduser("~"), "Downloads", "sign-sign-in")

    def _resolved_download_dir(self) -> str:
        value = self.download_dir_input.text().strip()
        return value or self._default_download_dir()

    def _load_download_dir_controls(self):
        update_settings = self._load_update_settings()
        saved_dir = str(update_settings.get("download_dir") or "").strip()
        self.download_dir_input.setText(saved_dir or self._default_download_dir())

    def _persist_download_dir(self, download_dir: str):
        update_settings = self._load_update_settings()
        update_settings["download_dir"] = download_dir.strip()
        self._persist_update_settings(update_settings)

    def _browse_download_dir(self):
        current_dir = self._resolved_download_dir()
        selected = QFileDialog.getExistingDirectory(self, "选择下载路径", current_dir)
        if not selected:
            return
        self.download_dir_input.setText(selected)
        self._persist_download_dir(selected)

    def _on_download_dir_changed(self):
        self._persist_download_dir(self.download_dir_input.text().strip())

    def _reset_download_dir(self):
        self.download_dir_input.setText(self._default_download_dir())
        self._persist_download_dir("")
        ToastManager.instance().show("已恢复默认下载路径", "success")

    def _open_download_dir(self):
        target_dir = Path(self._resolved_download_dir())
        target_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target_dir)))

    def _notify_windows_download_complete(self, release_tag: str, file_path: str):
        message = f"{release_tag} 下载完成：{Path(file_path).name}"
        parent = self.parent()
        if parent and hasattr(parent, "_show_tray_message"):
            parent._show_tray_message("更新下载完成", message, True)
            return
        ToastManager.instance().show(message, "success")

    def _persist_source_settings(self, source_name: str, custom_value: str = ""):
        update_settings = self._load_update_settings()
        sources = update_settings.setdefault("sources", {})
        update_settings["source"] = source_name
        if custom_value:
            sources["custom"] = custom_value.strip()
        elif isinstance(sources, dict):
            sources.pop("custom", None)
        self._persist_update_settings(update_settings)

    def _refresh_release_urls(self):
        current_source = self.source_combo.currentData()
        custom_value = self.custom_source_input.text().strip()
        self._persist_source_settings(current_source, custom_value)
        update_settings = self._load_update_settings()
        for release in [self.latest_release] + self.history_releases:
            raw_url = release.get("raw_download_url") or ""
            if not raw_url:
                release["download_url"] = ""
                continue
            release["download_url"] = UpdateCheckWorker._apply_download_source(raw_url, update_settings)
        self._sync_latest_buttons()
        for tag in list(self.release_rows):
            self._sync_release_buttons(tag)

    def _on_source_changed(self):
        source_name = self.source_combo.currentData()
        self.custom_source_input.setVisible(source_name == "custom")
        self._refresh_release_urls()

    def _on_custom_source_changed(self):
        if self.source_combo.currentData() == "custom":
            self._refresh_release_urls()

    def _refresh_update_center(self):
        if self.history_worker and self.history_worker.isRunning():
            return
        self.btn_refresh.setEnabled(False)
        self.history_worker = UpdateCheckWorker(PROJECT_GITHUB, PROJECT_VERSION, mode="center")
        self.history_worker.result_signal.connect(self._on_refresh_result)
        self.history_worker.start()
        ToastManager.instance().show("正在刷新更新中心...", "info")

    def _on_refresh_result(self, success: bool, data: dict):
        self.btn_refresh.setEnabled(True)
        if not success:
            ToastManager.instance().show(f"检查更新失败：{data.get('error', '未知错误')}", "error")
            return
        self.update_info = data
        self.has_loaded_update_data = True
        self.latest_release = dict(data.get("latest_release") or {})
        self.history_releases = list(data.get("history_releases") or [])
        self.history_releases = UpdateCheckWorker.build_compare_urls(self.history_releases, self.repo)
        self.current_history_cursor = data.get("history_cursor")
        self.latest_version = data.get("latest_version", self.latest_version)
        self.current_version = data.get("current_version", self.current_version)
        self._render_update_state()
        self._render_release_notes()
        self._refresh_release_urls()
        self._render_history_list(reset=True)
        ToastManager.instance().show("更新中心已刷新", "success")

    def _load_more_history(self):
        if not self.current_history_cursor or (self.history_worker and self.history_worker.isRunning()):
            return
        self.btn_load_more.setEnabled(False)
        self.history_worker = UpdateCheckWorker(
            PROJECT_GITHUB,
            PROJECT_VERSION,
            mode="history",
            history_cursor=self.current_history_cursor,
            exclude_tag=self.latest_release.get("tag_name") or "",
        )
        self.history_worker.result_signal.connect(self._on_history_result)
        self.history_worker.start()
        ToastManager.instance().show("正在加载更多历史版本...", "info")

    def _on_history_result(self, success: bool, data: dict):
        self.btn_load_more.setEnabled(True)
        if not success:
            ToastManager.instance().show(f"加载历史版本失败：{data.get('error', '未知错误')}", "error")
            return
        incoming = list(data.get("history_releases") or [])
        self.current_history_cursor = data.get("history_cursor")
        for release in incoming:
            if self._release_key(release) not in {self._release_key(item) for item in self.history_releases}:
                self.history_releases.append(release)
        self.history_releases = UpdateCheckWorker.build_compare_urls(self.history_releases, self.repo)
        self._refresh_release_urls()
        self._render_history_list(reset=True)

    def _open_release_download(self, release: dict):
        if not self.has_loaded_update_data:
            ToastManager.instance().show("请先拉取更新", "info")
            return
        self._ensure_release_download_ready(release)
        url = (release or {}).get("download_url") or ""
        if not url:
            url = (release or {}).get("html_url") or ""
            if not url:
                ToastManager.instance().show("该版本暂无下载资源", "warning")
                return
        self._open_optional_url(url)

    def _open_release_compare(self, release: dict):
        if not self.has_loaded_update_data:
            ToastManager.instance().show("请先拉取更新", "info")
            return
        self._open_optional_url((release or {}).get("compare_url") or "")

    def _open_optional_url(self, url: str):
        if not url:
            ToastManager.instance().show("当前版本没有可打开的链接", "warning")
            return
        QDesktopServices.openUrl(QUrl(url))

    def _download_release(self, release: dict):
        if not self.has_loaded_update_data:
            ToastManager.instance().show("请先拉取更新", "info")
            return
        self._ensure_release_download_ready(release)
        download_url = (release or {}).get("download_url") or ""
        if not download_url:
            fallback_url = (release or {}).get("html_url") or ""
            if fallback_url:
                ToastManager.instance().show("未找到直链，已打开版本页", "info")
                self._open_optional_url(fallback_url)
                return
            ToastManager.instance().show("该版本暂无下载资源", "warning")
            return
        if self.download_worker and self.download_worker.isRunning():
            ToastManager.instance().show("当前已有下载任务，请稍候", "info")
            return
        release_tag = self._release_key(release)
        save_dir = self._resolved_download_dir()
        self.progress.show()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFormat(f"准备下载 {release_tag}...")
        self._set_download_controls_visible(True)
        self.download_worker = UpdateDownloadWorker(download_url, save_dir=save_dir, timeout=120)
        self.download_worker.progress_signal.connect(self._on_download_progress)
        self.download_worker.status_signal.connect(self._on_download_status)
        self.download_worker.result_signal.connect(lambda ok, payload, item=dict(release): self._on_download_result(ok, payload, item))
        self.download_worker.start()
        ToastManager.instance().show(f"开始下载 {release_tag}", "info")

    def _on_download_progress(self, value: int):
        if value < 0:
            self.progress.setRange(0, 0)
            return
        if self.progress.maximum() == 0:
            self.progress.setRange(0, 100)
        self.progress.setValue(max(0, min(100, value)))

    def _on_download_status(self, text: str):
        if text:
            self.progress.setFormat(text)

    def _on_download_result(self, success: bool, data: dict, release: dict):
        self.progress.setRange(0, 100)
        self._set_download_controls_visible(False)
        if not success:
            if data.get("stopped"):
                self.progress.hide()
                self.progress.setFormat("下载已停止")
                ToastManager.instance().show("下载已停止，已删除未完成文件", "info")
                return
            self.progress.setFormat("下载失败")
            ToastManager.instance().show(f"下载失败：{data.get('error', '未知错误')}", "error")
            return
        file_path = data.get("file_path") or ""
        tag = self._release_key(release)
        self.downloaded_files[tag] = file_path
        self.progress.setValue(100)
        self.progress.setFormat(f"下载完成：{Path(file_path).name}")
        self._sync_latest_buttons()
        self._sync_release_buttons(tag)
        self._notify_windows_download_complete(tag, file_path)
        ToastManager.instance().show(f"{tag} 下载完成", "success")

    def _install_release(self, release: dict):
        if not self.has_loaded_update_data:
            ToastManager.instance().show("请先拉取更新", "info")
            return
        file_path = self._download_file_for_release(release)
        if not file_path:
            ToastManager.instance().show("请先下载该版本", "warning")
            return
        package = Path(file_path)
        if not package.exists():
            ToastManager.instance().show("下载文件不存在，可能已被移动或删除", "error")
            self.downloaded_files.pop(self._release_key(release), None)
            self._sync_latest_buttons()
            self._sync_release_buttons(self._release_key(release))
            return
        self._install_package(package)

    def _delete_downloaded_release(self, release: dict):
        file_path = self._download_file_for_release(release)
        if not file_path:
            ToastManager.instance().show("该版本没有已下载文件", "warning")
            return
        try:
            Path(file_path).unlink(missing_ok=True)
        except Exception as exc:
            ToastManager.instance().show(f"删除下载包失败：{exc}", "error")
            return
        tag = self._release_key(release)
        self.downloaded_files.pop(tag, None)
        self._sync_latest_buttons()
        self._sync_release_buttons(tag)
        ToastManager.instance().show(f"已删除 {tag} 的下载包", "success")

    def _install_package(self, package: Path):
        suffix = package.suffix.lower()
        if suffix == ".exe":
            try:
                os.startfile(str(package))
                ToastManager.instance().show("已启动安装程序，请按向导完成更新", "info")
            except Exception as exc:
                ToastManager.instance().show(f"启动安装程序失败：{exc}", "error")
            return

        if suffix != ".zip":
            ToastManager.instance().show("暂不支持该更新包格式，请使用浏览器下载手动更新", "warning")
            return

        reply = QMessageBox.question(
            self,
            "一键更新",
            "将自动替换当前程序并保留 resources/config 配置，完成后自动重启。是否继续？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if reply != QMessageBox.Yes:
            return

        try:
            self._launch_replace_script(str(package), BASE_DIR)
            ToastManager.instance().show("已开始更新，程序即将退出并自动重启...", "info")
            QApplication.instance().quit()
        except Exception as exc:
            ToastManager.instance().show(f"启动更新失败：{exc}", "error")

    def _launch_replace_script(self, package_path: str, app_dir: str):
        pid = os.getpid()
        script = f"""
$ErrorActionPreference = 'Stop'
$pkg = '{package_path.replace("'", "''")}'
$app = '{app_dir.replace("'", "''")}'
$pidToWait = {pid}

while (Get-Process -Id $pidToWait -ErrorAction SilentlyContinue) {{
    Start-Sleep -Milliseconds 300
}}

$extract = Join-Path $env:TEMP ("sign_update_unpack_" + [guid]::NewGuid().ToString("N"))
$backupRoot = Join-Path $env:TEMP ("sign_update_backup_" + [guid]::NewGuid().ToString("N"))
$cfgSrc = Join-Path $app "resources\\config"
$cfgBak = Join-Path $env:TEMP ("sign_cfg_backup_" + [guid]::NewGuid().ToString("N"))

New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
Copy-Item -Path (Join-Path $app "*") -Destination $backupRoot -Recurse -Force

if (Test-Path $cfgSrc) {{
    Copy-Item -Path $cfgSrc -Destination $cfgBak -Recurse -Force
}}

Expand-Archive -LiteralPath $pkg -DestinationPath $extract -Force
$items = Get-ChildItem -LiteralPath $extract
$copyFrom = $extract
if ($items.Count -eq 1 -and $items[0].PSIsContainer) {{
    $copyFrom = $items[0].FullName
}}
Copy-Item -Path (Join-Path $copyFrom "*") -Destination $app -Recurse -Force

if (Test-Path $cfgBak) {{
    New-Item -ItemType Directory -Path (Join-Path $app "resources") -Force | Out-Null
    Copy-Item -Path $cfgBak -Destination (Join-Path $app "resources\\config") -Recurse -Force
}}

$exeCandidates = @(
    (Join-Path $app "SignSignIn.exe"),
    (Join-Path $app "main.exe")
)
$mainExe = $exeCandidates | Where-Object {{ Test-Path $_ }} | Select-Object -First 1
if ($mainExe) {{
    Start-Process -FilePath $mainExe
}}
"""
        fd, script_path = tempfile.mkstemp(prefix="sign_update_", suffix=".ps1")
        os.close(fd)
        with open(script_path, "w", encoding="utf-8") as handle:
            handle.write(script)
        subprocess.Popen(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script_path],
            creationflags=subprocess.CREATE_NO_WINDOW,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
