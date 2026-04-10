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

from app.config.common import BASE_DIR, CONFIG_FILE, PROJECT_GITHUB, PROJECT_VERSION
from app.gui.components.toast import ToastManager
from app.utils.files import read_config, save_json_file
from app.workers.update_worker import UpdateCheckWorker, UpdateDownloadWorker


SOURCE_LABELS = {
    "github": "GitHub 官方",
    "gh_proxy": "gh-proxy 主站",
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

        self.setWindowTitle("更新中心")
        self.resize(860, 720)
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
            QLabel { color: #9BA3C6; }
            QLabel#TitleLabel { color: #F5F6FF; font-size: 16pt; font-weight: bold; }
            QLabel#VersionLabel { color: #BAC3FF; font-size: 11pt; }
            QFrame#Card { background: #16192A; border: 1px solid #2A2F45; border-radius: 14px; }
            QTextEdit, QLineEdit, QComboBox {
                background: #1E2238; border: 1px solid #2F3654; border-radius: 10px; padding: 10px; color: #F5F6FF;
            }
            QPushButton#PrimaryBtn {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4E8BFF, stop:1 #7C5BFF);
                color: white; border: none; border-radius: 18px; padding: 9px 16px; font-weight: bold;
            }
            QPushButton#OutlinedBtn {
                background: transparent; border: 1px solid #3A4062; color: #9BA3C6; border-radius: 18px; padding: 8px 14px;
            }
            QPushButton#DangerBtn {
                background: transparent; border: 1px solid #7A3A54; color: #FF9BB7; border-radius: 18px; padding: 8px 14px;
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
        layout.setSpacing(14)

        title = QLabel("更新中心")
        title.setObjectName("TitleLabel")
        layout.addWidget(title)

        self.status_label = QLabel("")
        self.status_label.setObjectName("VersionLabel")
        layout.addWidget(self.status_label)

        source_card = QFrame()
        source_card.setObjectName("Card")
        source_layout = QVBoxLayout(source_card)
        source_layout.setContentsMargins(14, 14, 14, 14)
        source_layout.setSpacing(10)

        top_row = QHBoxLayout()
        self.version_label = QLabel("")
        self.version_label.setObjectName("VersionLabel")
        top_row.addWidget(self.version_label)
        top_row.addStretch()

        self.btn_refresh = QPushButton("检查更新")
        self.btn_refresh.setObjectName("PrimaryBtn")
        self.btn_refresh.clicked.connect(self._refresh_update_center)
        top_row.addWidget(self.btn_refresh)
        source_layout.addLayout(top_row)

        source_row = QHBoxLayout()
        source_row.addWidget(QLabel("下载源"))
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
        layout.addWidget(source_card)

        latest_card = QFrame()
        latest_card.setObjectName("Card")
        latest_layout = QVBoxLayout(latest_card)
        latest_layout.setContentsMargins(14, 14, 14, 14)
        latest_layout.setSpacing(8)
        latest_layout.addWidget(QLabel("最新版本说明"))
        self.notes_edit = QTextEdit()
        self.notes_edit.setReadOnly(True)
        latest_layout.addWidget(self.notes_edit)

        latest_actions = QHBoxLayout()
        self.btn_latest_browser = QPushButton("浏览器下载")
        self.btn_latest_browser.setObjectName("OutlinedBtn")
        self.btn_latest_browser.clicked.connect(lambda: self._open_release_download(self.latest_release))
        latest_actions.addWidget(self.btn_latest_browser)
        self.btn_latest_download = QPushButton("自动下载")
        self.btn_latest_download.setObjectName("PrimaryBtn")
        self.btn_latest_download.clicked.connect(lambda: self._download_release(self.latest_release))
        latest_actions.addWidget(self.btn_latest_download)
        self.btn_latest_install = QPushButton("安装已下载包")
        self.btn_latest_install.setObjectName("OutlinedBtn")
        self.btn_latest_install.clicked.connect(lambda: self._install_release(self.latest_release))
        latest_actions.addWidget(self.btn_latest_install)
        self.btn_latest_compare = QPushButton("Full Changelog")
        self.btn_latest_compare.setObjectName("OutlinedBtn")
        self.btn_latest_compare.clicked.connect(lambda: self._open_optional_url(self.latest_release.get("compare_url")))
        latest_actions.addWidget(self.btn_latest_compare)
        latest_actions.addStretch()
        latest_layout.addLayout(latest_actions)
        layout.addWidget(latest_card)

        history_card = QFrame()
        history_card.setObjectName("Card")
        history_layout = QVBoxLayout(history_card)
        history_layout.setContentsMargins(14, 14, 14, 14)
        history_layout.setSpacing(10)

        history_header = QHBoxLayout()
        history_header.addWidget(QLabel("历史版本（正式版）"))
        history_header.addStretch()
        self.btn_load_more = QPushButton("加载更多")
        self.btn_load_more.setObjectName("OutlinedBtn")
        self.btn_load_more.clicked.connect(self._load_more_history)
        history_header.addWidget(self.btn_load_more)
        history_layout.addLayout(history_header)

        self.history_scroll = QScrollArea()
        self.history_scroll.setWidgetResizable(True)
        self.history_container = QWidget()
        self.history_list_layout = QVBoxLayout(self.history_container)
        self.history_list_layout.setContentsMargins(0, 0, 0, 0)
        self.history_list_layout.setSpacing(10)
        self.history_list_layout.addStretch()
        self.history_scroll.setWidget(self.history_container)
        history_layout.addWidget(self.history_scroll)
        layout.addWidget(history_card, 1)

        self.progress = QProgressBar()
        self.progress.hide()
        layout.addWidget(self.progress)

        footer = QHBoxLayout()
        footer.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.setObjectName("OutlinedBtn")
        close_btn.clicked.connect(self.close)
        footer.addWidget(close_btn)
        layout.addLayout(footer)

        self._load_source_controls()
        self._sync_latest_buttons()

    def _render_update_state(self):
        if self.update_info.get("has_update"):
            self.status_label.setText("发现新版本，可直接下载或回退到历史正式版。")
        else:
            self.status_label.setText("当前已是最新版本，也可以查看历史版本并执行回退。")
        self.version_label.setText(f"当前版本：{self.current_version}    最新版本：{self.latest_version}")

    def _render_release_notes(self):
        self.notes_edit.setPlainText(self.latest_release.get("body") or self.update_info.get("release_notes") or "暂无更新说明")

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
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)

        title_row = QHBoxLayout()
        title = QLabel(f"{release.get('name') or tag}  ({tag})")
        title.setStyleSheet("color:#F5F6FF;font-weight:bold;")
        title_row.addWidget(title)
        title_row.addStretch()
        published_at = release.get("published_at") or ""
        title_row.addWidget(QLabel(published_at[:10] if published_at else ""))
        layout.addLayout(title_row)

        notes = QTextEdit()
        notes.setReadOnly(True)
        notes.setMaximumHeight(110)
        notes.setPlainText(release.get("body") or "暂无更新说明")
        layout.addWidget(notes)

        action_row = QHBoxLayout()
        btn_browser = QPushButton("浏览器下载")
        btn_browser.setObjectName("OutlinedBtn")
        btn_browser.clicked.connect(lambda _, item=release: self._open_release_download(item))
        action_row.addWidget(btn_browser)

        btn_download = QPushButton("下载此版本")
        btn_download.setObjectName("PrimaryBtn")
        btn_download.clicked.connect(lambda _, item=release: self._download_release(item))
        action_row.addWidget(btn_download)

        btn_install = QPushButton("安装已下载包")
        btn_install.setObjectName("OutlinedBtn")
        btn_install.clicked.connect(lambda _, item=release: self._install_release(item))
        action_row.addWidget(btn_install)

        btn_delete = QPushButton("删除下载包")
        btn_delete.setObjectName("DangerBtn")
        btn_delete.clicked.connect(lambda _, item=release: self._delete_downloaded_release(item))
        action_row.addWidget(btn_delete)

        btn_compare = QPushButton("Full Changelog")
        btn_compare.setObjectName("OutlinedBtn")
        btn_compare.clicked.connect(lambda _, url=release.get("compare_url"): self._open_optional_url(url))
        action_row.addWidget(btn_compare)
        action_row.addStretch()
        layout.addLayout(action_row)

        self.history_list_layout.insertWidget(self.history_list_layout.count() - 1, card)
        self.release_rows[tag] = {
            "release": dict(release),
            "download": btn_download,
            "install": btn_install,
            "delete": btn_delete,
            "compare": btn_compare,
        }
        self._sync_release_buttons(tag)

    def _sync_latest_buttons(self):
        has_download = bool(self._download_file_for_release(self.latest_release))
        self.btn_latest_install.setEnabled(has_download)
        self.btn_latest_browser.setEnabled(bool(self.latest_release.get("download_url")))
        self.btn_latest_download.setEnabled(bool(self.latest_release.get("download_url")))
        self.btn_latest_compare.setEnabled(bool(self.latest_release.get("compare_url")))

    def _sync_release_buttons(self, tag: str):
        row = self.release_rows.get(tag)
        if not row:
            return
        release = row["release"]
        has_download = bool(self._download_file_for_release(release))
        row["install"].setEnabled(has_download)
        row["delete"].setEnabled(has_download)
        row["download"].setEnabled(bool(release.get("download_url")))
        row["compare"].setEnabled(bool(release.get("compare_url")))

    def _release_key(self, release: dict) -> str:
        return str((release or {}).get("tag_name") or "")

    def _download_file_for_release(self, release: dict) -> str:
        return self.downloaded_files.get(self._release_key(release), "")

    def _load_update_config(self) -> dict:
        try:
            return read_config(CONFIG_FILE)
        except Exception:
            return {"settings": {"update": {"source": "github", "sources": {}}}}

    def _load_source_controls(self):
        config = self._load_update_config()
        update_settings = ((config.get("settings") or {}).get("update") or {})
        source_name = str(update_settings.get("source") or "github")
        custom_sources = update_settings.get("sources") or {}
        index = self.source_combo.findData(source_name)
        if index < 0:
            index = self.source_combo.findData("custom")
        self.source_combo.setCurrentIndex(max(0, index))
        self.custom_source_input.setText(str(custom_sources.get("custom", "")))
        self.custom_source_input.setVisible(self.source_combo.currentData() == "custom")

    def _persist_source_settings(self, source_name: str, custom_value: str = ""):
        config = self._load_update_config()
        settings = config.setdefault("settings", {})
        update_settings = settings.setdefault("update", {})
        sources = update_settings.setdefault("sources", {})
        update_settings["source"] = source_name
        if custom_value:
            sources["custom"] = custom_value.strip()
        save_json_file(CONFIG_FILE, config)

    def _refresh_release_urls(self):
        current_source = self.source_combo.currentData()
        custom_value = self.custom_source_input.text().strip()
        self._persist_source_settings(current_source, custom_value)
        source_config = self._load_update_config()
        update_settings = ((source_config.get("settings") or {}).get("update") or {})
        sources = update_settings.get("sources") or {}
        source_value = str(sources.get(current_source, "") or "").strip()
        if current_source == "github" or not source_value:
            source_value = ""
        for release in [self.latest_release] + self.history_releases:
            raw_url = release.get("raw_download_url") or ""
            if not raw_url:
                release["download_url"] = ""
                continue
            if not source_value:
                release["download_url"] = raw_url
            elif "{url}" in source_value:
                release["download_url"] = source_value.replace("{url}", raw_url)
            elif source_value.endswith("/"):
                release["download_url"] = f"{source_value}{raw_url}"
            else:
                release["download_url"] = f"{source_value}/{raw_url}"
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
        url = (release or {}).get("download_url") or ""
        if not url:
            ToastManager.instance().show("该版本没有可用下载资源", "warning")
            return
        self._open_optional_url(url)

    def _open_optional_url(self, url: str):
        if not url:
            ToastManager.instance().show("当前版本没有可打开的链接", "warning")
            return
        QDesktopServices.openUrl(QUrl(url))

    def _download_release(self, release: dict):
        download_url = (release or {}).get("download_url") or ""
        if not download_url:
            ToastManager.instance().show("该版本没有可用下载资源", "warning")
            return
        if self.download_worker and self.download_worker.isRunning():
            ToastManager.instance().show("当前已有下载任务，请稍候", "info")
            return
        release_tag = self._release_key(release)
        save_dir = os.path.join(os.path.expanduser("~"), "Downloads", "sign-sign-in")
        self.progress.show()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFormat(f"准备下载 {release_tag}...")
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
        if not success:
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
        ToastManager.instance().show(f"{tag} 下载完成", "success")

    def _install_release(self, release: dict):
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
