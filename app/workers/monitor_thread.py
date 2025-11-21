import logging
import time

from PySide6.QtCore import QThread, Signal

from app.config.common import MITM_PROXY
from app.utils.commands import (
    get_net_io, get_network_type, get_local_ip, get_system_proxy,
    check_port_listening, check_cert
)


class MonitorThread(QThread):
    data_signal = Signal(dict)

    def __init__(self, mitm):
        super().__init__()
        self.mitm = mitm

    def run(self):
        host, port = MITM_PROXY.split(":")
        port = int(port)

        last_io = get_net_io()
        last_time = time.time()

        while True:
            # =======================
            # ① 监控 mitm 是否运行
            # =======================
            if not check_port_listening(host, port):
                logging.warning("⚠️ Mitm 未运行，尝试自动启动...")
                self.mitm.start()

                # 等待 mitm 启动：最多等 2 秒，每 100ms 检查一次
                started = False
                for _ in range(20):
                    if check_port_listening(host, port):
                        started = True
                        break
                    time.sleep(0.1)

                if started:
                    logging.info("🛡️ Mitm 自动启动成功")
                else:
                    logging.error("❌ Mitm 自动启动失败，请检查程序目录或权限")

            # =======================
            # ② 更新状态数据
            # =======================
            cur_io = get_net_io()
            now = time.time()
            speed_d = speed_u = 0

            if last_io and cur_io:
                dt = now - last_time
                if dt > 0:
                    speed_d = (cur_io.bytes_recv - last_io.bytes_recv) / 1024 / dt
                    speed_u = (cur_io.bytes_sent - last_io.bytes_sent) / 1024 / dt

            last_io = cur_io
            last_time = now

            data = {
                "net": get_network_type(),
                "speed_d": speed_d,
                "speed_u": speed_u,
                "ip": get_local_ip(),
                "proxy": get_system_proxy(),
                "mitm": check_port_listening(host, port),
                "cert": check_cert(),
            }

            self.data_signal.emit(data)
            time.sleep(1)
