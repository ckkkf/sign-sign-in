import logging
import os
import platform
import subprocess
import sys
import time

from app.config.common import ADDONS_DIR, BASE_DIR, LOG_DIR, MITM_DIR, MITM_PROXY
from app.utils.commands import check_port_listening, get_process_by_port, kill_process_tree


class MitmService:
    START_TIMEOUT_SECONDS = 6.0
    POLL_INTERVAL_SECONDS = 0.1

    def __init__(self):
        self.host, port = MITM_PROXY.split(":")
        self.port = int(port)
        self.addon = os.path.join(ADDONS_DIR, "get_code.py")
        self.confdir = os.path.join(MITM_DIR, "conf")
        self.start_log = os.path.join(LOG_DIR, "mitm_start.log")
        self.last_error = ""

    def is_running(self):
        return check_port_listening(self.host, self.port, 0.05)

    def stop_mitm(self):
        proc = get_process_by_port(self.port)
        if proc:
            kill_process_tree(proc.pid)
            time.sleep(0.3)

    @staticmethod
    def _creationflags():
        if platform.system() == "Windows":
            return subprocess.CREATE_NO_WINDOW
        return 0

    def _venv_python(self):
        if platform.system() == "Windows":
            return os.path.join(BASE_DIR, ".venv", "Scripts", "python.exe")
        return os.path.join(BASE_DIR, ".venv", "bin", "python")

    def _python_has_mitmproxy(self, python_executable: str):
        if not python_executable or not os.path.exists(python_executable):
            return False

        try:
            result = subprocess.run(
                [python_executable, "-c", "import mitmproxy"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=self._creationflags(),
                timeout=8,
                check=False,
            )
        except Exception:
            return False
        return result.returncode == 0

    def _resolve_python_executable(self):
        candidates = [self._venv_python(), sys.executable]
        for candidate in candidates:
            if self._python_has_mitmproxy(candidate):
                self.last_error = ""
                return candidate

        self.last_error = "未找到已安装 mitmproxy 的 Python 解释器，请先安装 mitmproxy==12.2.1"
        return sys.executable

    def _build_launch_command(self):
        common_args = [
            "--mitm-runner",
            "--host",
            self.host,
            "--port",
            str(self.port),
            "--addon",
            self.addon,
            "--confdir",
            self.confdir,
        ]

        if getattr(sys, "frozen", False):
            return [sys.executable, *common_args]

        python_executable = self._resolve_python_executable()
        main_script = os.path.join(BASE_DIR, "main.py")
        return [python_executable, main_script, *common_args]

    @staticmethod
    def _build_env():
        env = os.environ.copy()
        env.setdefault("PYTHONUTF8", "1")
        return env

    def start(self):
        if self.is_running():
            self.stop_mitm()

        os.makedirs(self.confdir, exist_ok=True)
        os.makedirs(os.path.dirname(self.start_log), exist_ok=True)
        self.last_error = ""
        command = self._build_launch_command()

        with open(self.start_log, "a", encoding="utf-8") as log_file:
            log_file.write(f"\n==== mitm start {time.strftime('%Y-%m-%d %H:%M:%S')} ====\n")
            log_file.write("CMD: " + " ".join(command) + "\n")
            if self.last_error:
                log_file.write("WARN: " + self.last_error + "\n")
            log_file.flush()

            try:
                process = subprocess.Popen(
                    command,
                    cwd=BASE_DIR,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    creationflags=self._creationflags(),
                    env=self._build_env(),
                )
            except Exception as exc:
                self.last_error = f"启动 mitm 失败: {exc}"
                log_file.write("ERROR: " + self.last_error + "\n")
                logging.error(self.last_error)
                return False

        deadline = time.time() + self.START_TIMEOUT_SECONDS
        while time.time() < deadline:
            if self.is_running():
                return True
            if process.poll() is not None:
                break
            time.sleep(self.POLL_INTERVAL_SECONDS)

        if self.is_running():
            return True

        exit_code = process.poll()
        suffix = f"，退出码: {exit_code}" if exit_code is not None else ""
        self.last_error = f"mitm 启动失败，请查看日志: {self.start_log}{suffix}"
        logging.error(self.last_error)
        return False
