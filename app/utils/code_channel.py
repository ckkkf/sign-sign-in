import json
import logging
import queue
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from app.config.common import CODE_RECEIVER_HOST, CODE_RECEIVER_PORT


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


class CodeChannel:
    _instance = None
    _instance_lock = threading.Lock()

    def __init__(self):
        self.host = CODE_RECEIVER_HOST
        self.port = CODE_RECEIVER_PORT
        self._queue = queue.Queue(maxsize=1)
        self._server = None
        self._thread = None
        self._lock = threading.Lock()

    @classmethod
    def instance(cls):
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def start(self):
        with self._lock:
            if self._server is not None:
                return

            channel = self

            class Handler(BaseHTTPRequestHandler):
                def do_POST(self):
                    if self.path != "/code":
                        self.send_response(404)
                        self.end_headers()
                        return

                    length = int(self.headers.get("Content-Length", "0") or 0)
                    raw = self.rfile.read(length)

                    try:
                        payload = json.loads(raw.decode("utf-8") or "{}")
                    except Exception:
                        payload = {}

                    code = str(payload.get("code") or "").strip()
                    if not code:
                        self.send_response(400)
                        self.end_headers()
                        self.wfile.write(b'{"ok":false,"msg":"code empty"}')
                        return

                    channel.publish(code)
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(b'{"ok":true}')

                def log_message(self, format, *args):
                    return

            self._server = ReusableThreadingHTTPServer((self.host, self.port), Handler)
            self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
            self._thread.start()
            logging.info(f"📡 Code 接收服务已启动: http://{self.host}:{self.port}/code")

    def reset(self):
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def publish(self, code: str):
        code = str(code or "").strip()
        if not code:
            return

        self.reset()
        self._queue.put_nowait(code)
        logging.info("📥 已接收到新的 code")

    def wait_code(self, timeout_seconds: int, stop_check=None, heartbeat=None):
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            if stop_check:
                stop_check()
            if heartbeat:
                heartbeat()
            try:
                code = self._queue.get(timeout=0.1)
                return str(code).strip()
            except queue.Empty:
                continue
        raise RuntimeError("获取 Code 超时")

