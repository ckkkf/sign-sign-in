from typing import Any, Dict, Optional

import requests
from PySide6.QtCore import QThread, Signal


class HttpWorker(QThread):
    result_signal = Signal(bool, str)

    def __init__(self, url: str, data: Dict[str, Any], headers: Optional[Dict[str, str]] = None, timeout: int = 10):
        super().__init__()
        self.url = url
        self.data = data
        self.headers = headers or {}
        self.timeout = timeout

    def run(self):
        try:
            response = requests.post(self.url, json=self.data, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()
            text = (response.text or "").strip()
            self.result_signal.emit(True, text[:200] or "success")
        except Exception as exc:
            self.result_signal.emit(False, str(exc))
