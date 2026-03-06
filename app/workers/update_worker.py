import re
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from urllib.parse import unquote, urlparse

import requests
from PySide6.QtCore import QThread, Signal


class UpdateCheckWorker(QThread):
    """更新检查工作线程"""
    result_signal = Signal(bool, dict)  # success, data

    def __init__(self, check_url: str, current_version: str, timeout: int = 10):
        super().__init__()
        self.check_url = check_url
        self.current_version = current_version
        self.timeout = timeout

    def run(self):
        try:
            # 兼容两种来源：
            # 1) 旧后端接口 /api/check-update
            # 2) GitHub 仓库地址（推荐）
            if "github.com" in (self.check_url or "").lower():
                data = self._check_from_github_release(self.check_url, self.current_version)
            else:
                data = self._check_from_backend(self.check_url, self.current_version)
            self.result_signal.emit(True, data)
        except Exception as exc:
            self.result_signal.emit(False, {"error": str(exc)})

    def _check_from_backend(self, check_url: str, current_version: str) -> dict:
        response = requests.get(
            check_url,
            params={"version": current_version},
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()

    def _check_from_github_release(self, repo_url: str, current_version: str) -> dict:
        owner, repo = self._parse_github_repo(repo_url)
        api = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "sign-sign-in-updater",
        }
        response = requests.get(api, headers=headers, timeout=self.timeout)
        response.raise_for_status()
        release = response.json()

        latest_version = release.get("tag_name") or ""
        has_update = self._is_newer(latest_version, current_version)

        download_url = self._pick_download_url(release)
        release_notes = release.get("body") or "暂无更新说明"

        return {
            "latest_version": latest_version,
            "current_version": current_version,
            "has_update": has_update,
            "download_url": download_url,
            "release_notes": release_notes,
        }

    @staticmethod
    def _parse_github_repo(repo_url: str) -> Tuple[str, str]:
        # 支持：https://github.com/owner/repo 或 owner/repo
        raw = (repo_url or "").strip().rstrip("/")
        if not raw:
            raise ValueError("GitHub 仓库地址为空")

        if raw.startswith("http://") or raw.startswith("https://"):
            m = re.search(r"github\.com/([^/]+)/([^/]+)", raw, re.IGNORECASE)
            if not m:
                raise ValueError(f"无法解析 GitHub 仓库地址: {repo_url}")
            owner, repo = m.group(1), m.group(2)
        else:
            parts = raw.split("/")
            if len(parts) != 2:
                raise ValueError(f"仓库格式应为 owner/repo，当前: {repo_url}")
            owner, repo = parts[0], parts[1]

        repo = repo.removesuffix(".git")
        return owner, repo

    @staticmethod
    def _version_tuple(v: str) -> Tuple[int, ...]:
        nums = re.findall(r"\d+", (v or "").lstrip("vV"))
        if not nums:
            return (0,)
        return tuple(int(x) for x in nums)

    def _is_newer(self, latest: str, current: str) -> bool:
        return self._version_tuple(latest) > self._version_tuple(current)

    @staticmethod
    def _pick_download_url(release: Dict[str, Any]) -> str:
        assets = release.get("assets") or []
        if assets:
            # 优先 exe，其次 zip，最后任意资产
            exe = next((a for a in assets if str(a.get("name", "")).lower().endswith(".exe")), None)
            if exe and exe.get("browser_download_url"):
                return exe["browser_download_url"]

            zip_file = next((a for a in assets if str(a.get("name", "")).lower().endswith(".zip")), None)
            if zip_file and zip_file.get("browser_download_url"):
                return zip_file["browser_download_url"]

            first = assets[0].get("browser_download_url")
            if first:
                return first

        # 无 assets 时回退到 release 页面
        return release.get("html_url") or ""


class UpdateDownloadWorker(QThread):
    """更新包下载线程"""
    progress_signal = Signal(int)  # 0-100
    status_signal = Signal(str)  # 文本进度
    result_signal = Signal(bool, dict)  # success, {"file_path": "..."} / {"error": "..."}

    def __init__(self, download_url: str, save_dir: Optional[str] = None, timeout: int = 20):
        super().__init__()
        self.download_url = download_url
        self.save_dir = save_dir
        self.timeout = timeout

    def run(self):
        try:
            if not self.download_url:
                raise RuntimeError("下载链接为空")

            target_dir = Path(self.save_dir) if self.save_dir else Path.home() / "Downloads" / "sign-sign-in"
            target_dir.mkdir(parents=True, exist_ok=True)

            with requests.get(self.download_url, stream=True, timeout=(10, self.timeout), allow_redirects=True) as resp:
                resp.raise_for_status()
                filename = self._resolve_filename(resp, self.download_url)
                file_path = target_dir / filename

                total = int(resp.headers.get("Content-Length", "0") or "0")
                if total <= 0:
                    # 某些重定向/CDN响应不会带 Content-Length
                    remaining = getattr(resp.raw, "length_remaining", 0) or 0
                    try:
                        total = int(remaining)
                    except Exception:
                        total = 0
                written = 0

                if total > 0:
                    self.progress_signal.emit(0)
                    self.status_signal.emit(f"已下载 0.0 / {total / 1024 / 1024:.1f} MB")
                else:
                    # -1 表示未知总大小，UI 切换为忙碌动画
                    self.progress_signal.emit(-1)
                    self.status_signal.emit("下载中...（总大小未知）")

                last_pct = -1
                last_status_emit = 0

                with open(file_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=64 * 1024):
                        if not chunk:
                            continue
                        f.write(chunk)
                        written += len(chunk)
                        if total > 0:
                            pct = int(written * 100 / total)
                            pct = min(100, max(0, pct))
                            if pct != last_pct:
                                self.progress_signal.emit(pct)
                                last_pct = pct
                            # 约每 512KB 更新一次文本
                            if written - last_status_emit >= 512 * 1024 or pct == 100:
                                self.status_signal.emit(
                                    f"已下载 {written / 1024 / 1024:.1f} / {total / 1024 / 1024:.1f} MB"
                                )
                                last_status_emit = written
                        else:
                            if written - last_status_emit >= 512 * 1024:
                                self.status_signal.emit(f"已下载 {written / 1024 / 1024:.1f} MB")
                                last_status_emit = written

                self.progress_signal.emit(100)
                self.status_signal.emit("下载完成")
                self.result_signal.emit(True, {"file_path": str(file_path)})
        except Exception as exc:
            self.result_signal.emit(False, {"error": str(exc)})

    @staticmethod
    def _resolve_filename(response: requests.Response, url: str) -> str:
        cd = response.headers.get("Content-Disposition", "")
        # filename*=UTF-8''xxx
        m_ext = re.search(r"filename\*\s*=\s*UTF-8''([^;]+)", cd, re.IGNORECASE)
        if m_ext:
            name = unquote(m_ext.group(1).strip().strip('"'))
            if name:
                return name

        # filename="xxx"
        m = re.search(r'filename\s*=\s*"([^"]+)"', cd, re.IGNORECASE)
        if m:
            name = m.group(1).strip()
            if name:
                return name

        # fallback: 从 URL 取文件名
        path = urlparse(url).path
        name = Path(path).name
        if name:
            return name
        return "update_package.bin"


