from typing import Optional, Dict, Any

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
            response = requests.get(
                self.check_url,
                params={"version": self.current_version},
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()
            
            # 期望的响应格式：
            # {
            #   "latest_version": "v1.2.0",
            #   "current_version": "v1.1.0",
            #   "has_update": true,
            #   "download_url": "https://...",
            #   "release_notes": "更新内容..."
            # }
            self.result_signal.emit(True, data)
        except Exception as exc:
            self.result_signal.emit(False, {"error": str(exc)})


