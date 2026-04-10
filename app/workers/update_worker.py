import platform
import re
from html import unescape
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import unquote, urlparse

import requests
from PySide6.QtCore import QThread, Signal

from app.config.common import CONFIG_FILE
from app.utils.files import read_config


class UpdateCheckWorker(QThread):
    """更新检查线程。"""

    result_signal = Signal(bool, dict)

    def __init__(
        self,
        check_url: str,
        current_version: str,
        timeout: int = 10,
        mode: str = "latest",
        page_size: int = 5,
        history_cursor: Optional[dict] = None,
        exclude_tag: str = "",
    ):
        super().__init__()
        self.check_url = check_url
        self.current_version = current_version
        self.timeout = timeout
        self.mode = mode
        self.page_size = max(1, int(page_size or 5))
        self.history_cursor = history_cursor or {}
        self.exclude_tag = exclude_tag

    def run(self):
        try:
            if "github.com" in (self.check_url or "").lower():
                data = self._check_from_github_release(self.check_url, self.current_version)
            else:
                data = self._check_from_backend(self.check_url, self.current_version)
            self.result_signal.emit(True, data)
        except Exception as exc:
            self.result_signal.emit(False, {"error": str(exc)})

    def _check_from_backend(self, check_url: str, current_version: str) -> dict:
        response = requests.get(check_url, params={"version": current_version}, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def _check_from_github_release(self, repo_url: str, current_version: str) -> dict:
        owner, repo = self._parse_github_repo(repo_url)
        repo_key = f"{owner}/{repo}"

        start_index = 0 if self.mode == "center" else int(self.history_cursor.get("start", 1) or 1)
        needed = 1 if self.mode == "latest" else start_index + self.page_size + 1
        releases = self._fetch_official_releases(owner, repo, needed)
        if self.exclude_tag:
            releases = [item for item in releases if item.get("tag_name") != self.exclude_tag]
        if not releases:
            raise RuntimeError("未获取到任何正式版 release")

        releases = self.build_compare_urls(releases, repo_key)
        latest_release = releases[0]
        latest_version = latest_release.get("tag_name") or ""
        has_update = self._is_newer(latest_version, current_version)

        payload = {
            "latest_version": latest_version,
            "current_version": current_version,
            "has_update": has_update,
            "download_url": latest_release.get("download_url", ""),
            "download_name": latest_release.get("download_name", ""),
            "download_source": self._get_update_source_name(),
            "release_notes": latest_release.get("body") or "暂无更新说明",
            "latest_release": latest_release,
            "history_releases": [],
            "history_cursor": None,
            "mode": self.mode,
            "repo": repo_key,
        }

        if self.mode in {"center", "history"}:
            history_start = 1 if self.mode == "center" else start_index
            history_slice = releases[history_start : history_start + self.page_size]
            payload["history_releases"] = history_slice
            if len(releases) > history_start + self.page_size:
                payload["history_cursor"] = {"start": history_start + self.page_size}

        if self.mode == "history":
            payload["download_url"] = ""
            payload["download_name"] = ""
            payload["release_notes"] = ""

        return payload

    def _fetch_official_releases(self, owner: str, repo: str, limit: int) -> List[Dict[str, Any]]:
        releases: List[Dict[str, Any]] = []
        seen_tags = set()
        page = 1
        empty_pages = 0

        while len(releases) < limit and empty_pages < 2:
            html = self._fetch_releases_page(owner, repo, page)
            page_releases = self._parse_releases_page(html, owner, repo)
            fresh_items = []
            for item in page_releases:
                tag = item.get("tag_name") or ""
                if not tag or tag in seen_tags:
                    continue
                seen_tags.add(tag)
                fresh_items.append(item)
            if not fresh_items:
                empty_pages += 1
            else:
                empty_pages = 0
                releases.extend(fresh_items)
            if not self._has_next_page(html):
                break
            page += 1

        return releases[:limit]

    def _fetch_releases_page(self, owner: str, repo: str, page: int) -> str:
        url = f"https://github.com/{owner}/{repo}/releases"
        if page > 1:
            url = f"{url}?page={page}"
        response = requests.get(url, headers=self._github_headers(), timeout=self.timeout)
        response.raise_for_status()
        return response.text

    def _parse_releases_page(self, html: str, owner: str, repo: str) -> List[Dict[str, Any]]:
        matches = list(
            re.finditer(
                rf'href="(?:https://github\.com)?/{re.escape(owner)}/{re.escape(repo)}/releases/tag/([^"#?]+)"[^>]*>(.*?)</a>',
                html,
                flags=re.IGNORECASE | re.DOTALL,
            )
        )
        releases: List[Dict[str, Any]] = []
        repo_key = f"{owner}/{repo}"

        for index, match in enumerate(matches):
            start = match.start()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(html)
            block = html[start:end]
            if self._is_unofficial_release_block(block):
                continue

            tag_name = unquote(match.group(1).strip())
            title = self._strip_html(match.group(2)) or tag_name
            body = self._extract_release_body(block) or "暂无更新说明"
            published_at = self._extract_release_time(block)
            html_url = f"https://github.com/{repo_key}/releases/tag/{tag_name}"
            assets = self._parse_release_assets(block)
            asset = self._pick_download_asset({"assets": assets})
            raw_download_url = asset.get("browser_download_url", "")
            download_name = asset.get("name", "")
            suffix = Path(download_name).suffix.lower()
            install_kind = "exe" if suffix == ".exe" else "zip" if suffix == ".zip" else ""

            releases.append(
                {
                    "tag_name": tag_name,
                    "name": title,
                    "body": body,
                    "published_at": published_at,
                    "html_url": html_url,
                    "raw_download_url": raw_download_url,
                    "download_url": self._apply_download_source(raw_download_url),
                    "download_name": download_name,
                    "download_source": self._get_update_source_name(),
                    "compare_url": "",
                    "asset_available": bool(download_name and raw_download_url),
                    "install_kind": install_kind,
                    "install_supported": install_kind in {"exe", "zip"},
                }
            )

        return releases

    @staticmethod
    def _extract_release_body(block: str) -> str:
        patterns = [
            r'<div[^>]*class="[^"]*markdown-body[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*data-test-selector="body-content"[^>]*>(.*?)</div>',
        ]
        for pattern in patterns:
            match = re.search(pattern, block, flags=re.IGNORECASE | re.DOTALL)
            if match:
                return UpdateCheckWorker._strip_html(match.group(1))
        return ""

    @staticmethod
    def _extract_release_time(block: str) -> str:
        patterns = [
            r'<relative-time[^>]*datetime="([^"]+)"',
            r'<time[^>]*datetime="([^"]+)"',
        ]
        for pattern in patterns:
            match = re.search(pattern, block, flags=re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return ""

    @staticmethod
    def _is_unofficial_release_block(block: str) -> bool:
        lowered = re.sub(r"\s+", " ", block.lower())
        markers = [
            ">draft<",
            ">pre-release<",
            ">pre release<",
            'aria-label="draft"',
            'aria-label="pre-release"',
            'aria-label="pre release"',
        ]
        return any(marker in lowered for marker in markers)

    @staticmethod
    def _has_next_page(html: str) -> bool:
        return bool(
            re.search(
                r'(?:rel="next"|aria-label="Next"|href="[^"]*[?&]page=\d+[^"]*")',
                html,
                flags=re.IGNORECASE,
            )
        )

    @staticmethod
    def _parse_release_assets(html: str) -> List[Dict[str, Any]]:
        assets: List[Dict[str, Any]] = []
        seen = set()
        for raw_href in re.findall(r'href="([^"]+/releases/download/[^"]+)"', html, flags=re.IGNORECASE):
            href = unescape(raw_href)
            if href.startswith("/"):
                href = f"https://github.com{href}"
            name = Path(urlparse(href).path).name
            if not name or href in seen:
                continue
            seen.add(href)
            assets.append({"name": name, "browser_download_url": href})
        return assets

    @staticmethod
    def _strip_html(value: str) -> str:
        text = re.sub(r"<br\s*/?>", "\n", value, flags=re.IGNORECASE)
        text = re.sub(r"</p\s*>", "\n\n", text, flags=re.IGNORECASE)
        text = re.sub(r"</li\s*>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<li[^>]*>", "- ", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", "", text)
        text = unescape(text)
        text = re.sub(r"\r\n?", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @staticmethod
    def build_compare_urls(releases: List[Dict[str, Any]], repo_key: str) -> List[Dict[str, Any]]:
        stable = [dict(item) for item in releases]
        for index, item in enumerate(stable):
            older = stable[index + 1] if index + 1 < len(stable) else None
            tag = item.get("tag_name") or ""
            older_tag = (older or {}).get("tag_name") or ""
            item["compare_url"] = (
                f"https://github.com/{repo_key}/compare/{older_tag}...{tag}" if older_tag and tag else ""
            )
        return stable

    @staticmethod
    def _parse_github_repo(repo_url: str) -> Tuple[str, str]:
        raw = (repo_url or "").strip().rstrip("/")
        if not raw:
            raise ValueError("GitHub 仓库地址为空")
        if raw.startswith("http://") or raw.startswith("https://"):
            match = re.search(r"github\.com/([^/]+)/([^/]+)", raw, re.IGNORECASE)
            if not match:
                raise ValueError(f"无法解析 GitHub 仓库地址: {repo_url}")
            owner, repo = match.group(1), match.group(2)
        else:
            parts = raw.split("/")
            if len(parts) != 2:
                raise ValueError(f"仓库格式应为 owner/repo，当前: {repo_url}")
            owner, repo = parts[0], parts[1]
        return owner, repo.removesuffix(".git")

    @staticmethod
    def _github_headers() -> Dict[str, str]:
        return {"User-Agent": "sign-sign-in-updater", "Accept": "text/html,application/xhtml+xml,*/*"}

    @staticmethod
    def _version_tuple(version: str) -> Tuple[int, ...]:
        nums = re.findall(r"\d+", (version or "").lstrip("vV"))
        if not nums:
            return (0,)
        return tuple(int(item) for item in nums)

    def _is_newer(self, latest: str, current: str) -> bool:
        return self._version_tuple(latest) > self._version_tuple(current)

    @staticmethod
    def _load_update_settings() -> Dict[str, Any]:
        try:
            config = read_config(CONFIG_FILE)
        except Exception:
            return {}
        settings = config.get("settings") or {}
        update_settings = settings.get("update") or {}
        return update_settings if isinstance(update_settings, dict) else {}

    @classmethod
    def _get_update_sources(cls) -> Dict[str, str]:
        default_sources = {
            "github": "",
            "gh_proxy": "https://gh-proxy.org/{url}",
            "gh_proxy_hk": "https://hk.gh-proxy.org/{url}",
            "gh_proxy_cdn": "https://cdn.gh-proxy.org/{url}",
            "gh_proxy_edgeone": "https://edgeone.gh-proxy.org/{url}",
        }
        update_settings = cls._load_update_settings()
        custom_sources = update_settings.get("sources") or {}
        if not isinstance(custom_sources, dict):
            return default_sources
        merged = dict(default_sources)
        for key, value in custom_sources.items():
            if key and isinstance(value, str):
                merged[str(key)] = value.strip()
        return merged

    @classmethod
    def _get_update_source_name(cls) -> str:
        update_settings = cls._load_update_settings()
        source_name = str(update_settings.get("source") or "github").strip()
        return source_name or "github"

    @classmethod
    def _apply_download_source(cls, url: str) -> str:
        raw_url = (url or "").strip()
        if not raw_url:
            return ""
        source_name = cls._get_update_source_name()
        source_value = str(cls._get_update_sources().get(source_name, "") or "").strip()
        if not source_value or source_name == "github":
            return raw_url
        if "{url}" in source_value:
            return source_value.replace("{url}", raw_url)
        if source_value.endswith("/"):
            return f"{source_value}{raw_url}"
        return f"{source_value}/{raw_url}"

    @staticmethod
    def _pick_download_asset(release: Dict[str, Any]) -> Dict[str, Any]:
        assets = release.get("assets") or []
        if not assets:
            return {"name": "", "browser_download_url": ""}
        system = platform.system().lower()

        def valid(asset: Dict[str, Any]) -> bool:
            return bool(asset.get("browser_download_url"))

        def pick(predicate):
            return next((asset for asset in assets if valid(asset) and predicate(str(asset.get("name", "")).lower())), None)

        if "windows" in system:
            preferred = [
                lambda name: "windows" in name and name.endswith(".zip"),
                lambda name: "windows" in name and name.endswith(".exe"),
                lambda name: name.endswith(".exe"),
                lambda name: name.endswith(".zip") and "mac" not in name,
            ]
        elif "darwin" in system or "mac" in system:
            preferred = [
                lambda name: ("macos" in name or "mac" in name or "darwin" in name) and name.endswith(".zip"),
                lambda name: name.endswith(".zip") and "windows" not in name,
            ]
        else:
            preferred = [lambda name: name.endswith(".zip"), lambda name: name.endswith(".exe")]

        for matcher in preferred:
            asset = pick(matcher)
            if asset:
                return asset
        return next((asset for asset in assets if valid(asset)), {"name": "", "browser_download_url": ""})


class UpdateDownloadWorker(QThread):
    """更新包下载线程。"""

    progress_signal = Signal(int)
    status_signal = Signal(str)
    result_signal = Signal(bool, dict)

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
                    self.progress_signal.emit(-1)
                    self.status_signal.emit("下载中...（总大小未知）")
                last_pct = -1
                last_status_emit = 0
                with open(file_path, "wb") as handle:
                    for chunk in resp.iter_content(chunk_size=64 * 1024):
                        if not chunk:
                            continue
                        handle.write(chunk)
                        written += len(chunk)
                        if total > 0:
                            pct = min(100, max(0, int(written * 100 / total)))
                            if pct != last_pct:
                                self.progress_signal.emit(pct)
                                last_pct = pct
                            if written - last_status_emit >= 512 * 1024 or pct == 100:
                                self.status_signal.emit(
                                    f"已下载 {written / 1024 / 1024:.1f} / {total / 1024 / 1024:.1f} MB"
                                )
                                last_status_emit = written
                        elif written - last_status_emit >= 512 * 1024:
                            self.status_signal.emit(f"已下载 {written / 1024 / 1024:.1f} MB")
                            last_status_emit = written
                self.progress_signal.emit(100)
                self.status_signal.emit("下载完成")
                self.result_signal.emit(True, {"file_path": str(file_path)})
        except Exception as exc:
            self.result_signal.emit(False, {"error": str(exc)})

    @staticmethod
    def _resolve_filename(response: requests.Response, url: str) -> str:
        content_disposition = response.headers.get("Content-Disposition", "")
        ext_match = re.search(r"filename\*\s*=\s*UTF-8''([^;]+)", content_disposition, re.IGNORECASE)
        if ext_match:
            name = unquote(ext_match.group(1).strip().strip('"'))
            if name:
                return name
        match = re.search(r'filename\s*=\s*"([^"]+)"', content_disposition, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            if name:
                return name
        name = Path(urlparse(url).path).name
        return name or "update_package.bin"
