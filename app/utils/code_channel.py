import json
import logging
import os
import threading
import time

from app.config.common import CODE_FILE


class CodeChannel:
    """通过文件轮询方式接收 mitm addon 写入的 code，兼容打包环境。"""

    _instance = None
    _instance_lock = threading.Lock()

    def __init__(self):
        self._code_file = CODE_FILE

    @classmethod
    def instance(cls):
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def start(self):
        os.makedirs(os.path.dirname(self._code_file), exist_ok=True)
        logging.info(f"📡 Code 文件通道已就绪: {self._code_file}")

    def reset(self):
        try:
            if os.path.exists(self._code_file):
                os.remove(self._code_file)
        except OSError:
            pass

    def wait_code(self, timeout_seconds: int, stop_check=None, heartbeat=None):
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            if stop_check:
                stop_check()
            if heartbeat:
                heartbeat()

            code = self._try_read_code()
            if code:
                logging.info("📥 已接收到新的 code")
                return code

            time.sleep(0.3)

        raise RuntimeError("获取 Code 超时")

    def _try_read_code(self) -> str | None:
        if not os.path.exists(self._code_file):
            return None
        try:
            with open(self._code_file, "r", encoding="utf-8") as f:
                payload = json.load(f)
            code = str(payload.get("code") or "").strip()
            if code:
                os.remove(self._code_file)
                return code
        except (json.JSONDecodeError, OSError, KeyError):
            pass
        return None

