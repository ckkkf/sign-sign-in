import os
import time
import platform
import subprocess

from app.config.common import MITMDUMP_FILE, ADDONS_DIR, MITM_PROXY
from app.utils.commands import check_port_listening, get_process_by_port, kill_process_tree


class MitmService:
    def __init__(self):
        self.host, port = MITM_PROXY.split(":")
        self.port = int(port)
        self.addon = os.path.join(ADDONS_DIR, "get_code.py")

    def is_running(self):
        return check_port_listening(self.host, self.port, 0.05)

    def stop_mitm(self):
        proc = get_process_by_port(self.port)
        if proc:
            kill_process_tree(proc.pid)
            time.sleep(0.3)

    def start(self):
        # 若已运行 → 先杀
        if self.is_running():
            self.stop_mitm()

        # 启动
        subprocess.Popen(
            [
                MITMDUMP_FILE,
                "-p", str(self.port),
                "-s", self.addon,
                "--quiet"
            ],
            creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
        )

        time.sleep(0.5)
        return self.is_running()
