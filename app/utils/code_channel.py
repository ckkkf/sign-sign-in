import json
import logging
import os
import threading
import time

from app.config.common import CODE_FILE


class CodeChannel:
    """Read code/token payloads written by the mitm addon."""

    _instance = None
    _instance_lock = threading.Lock()

    def __init__(self):
        self._code_file = CODE_FILE
        self._started = False

    @classmethod
    def instance(cls):
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def start(self):
        os.makedirs(os.path.dirname(self._code_file), exist_ok=True)
        if self._started:
            return
        self._started = True
        logging.info(f"Code channel file: {self._code_file}")

    def reset(self):
        self._started = False
        try:
            if os.path.exists(self._code_file):
                os.remove(self._code_file)
        except OSError:
            pass

    def wait_payload(self, timeout_seconds: int, source: str | None = None, stop_check=None, heartbeat=None):
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            if stop_check:
                stop_check()
            if heartbeat:
                heartbeat()

            payload = self._try_read_payload(source=source)
            if payload:
                logging.info("Loaded mitm payload")
                return payload

            time.sleep(0.3)

        if source == "xyb_code":
            raise RuntimeError("Timed out waiting for code")
        raise RuntimeError("Timed out waiting for login callback")

    def wait_code(self, timeout_seconds: int, stop_check=None, heartbeat=None):
        payload = self.wait_payload(
            timeout_seconds=timeout_seconds,
            source="xyb_code",
            stop_check=stop_check,
            heartbeat=heartbeat,
        )
        code = str(payload.get("code") or "").strip()
        if code:
            logging.info("Loaded login code")
            return code
        raise RuntimeError("Timed out waiting for code")

    def _try_read_payload(self, source: str | None = None) -> dict | None:
        payload = self._peek_payload()
        if not isinstance(payload, dict):
            return None

        payload_source = str(payload.get("source") or "").strip()
        if source:
            if payload_source and payload_source != source:
                return None
            if not payload_source and source != "xyb_code":
                return None

        has_value = any(str(payload.get(key) or "").strip() for key in ("code", "token", "uuid"))
        if not has_value:
            return None

        self._consume_payload()
        return payload

    def _peek_payload(self) -> dict | None:
        if not os.path.exists(self._code_file):
            return None
        try:
            with open(self._code_file, "r", encoding="utf-8") as f:
                payload = json.load(f)
            if isinstance(payload, dict):
                return payload
        except (json.JSONDecodeError, OSError, KeyError):
            pass
        return None

    def _consume_payload(self):
        try:
            if os.path.exists(self._code_file):
                os.remove(self._code_file)
        except OSError:
            pass
