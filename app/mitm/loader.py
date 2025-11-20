import os
import platform
import subprocess
import time

from PySide6.QtCore import QThread

from app.config.common import MITMDUMP_FILE, ADDONS_DIR
from app.utils.commands import check_port_listening, get_process_by_port, kill_process_tree


class MitmLoaderThread(QThread):
    def __init__(self, port=13140):
        super().__init__()
        self.target_port = port

    def run(self):
        mitmdump_path = MITMDUMP_FILE
        addons_path = os.path.join(ADDONS_DIR, 'get_code.py')
        if not os.path.exists(mitmdump_path): return
        if check_port_listening("127.0.0.1", self.target_port, 0.1): return

        proc = get_process_by_port(self.target_port)
        if proc:
            kill_process_tree(proc.pid)
            time.sleep(0.5)

        subprocess.Popen([mitmdump_path, "-p", str(self.target_port), "-s", addons_path, "--quiet"],
                         creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == 'Windows' else 0)
