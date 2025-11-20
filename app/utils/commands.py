import ctypes
import re
import socket
import subprocess

import psutil


def get_network_type():
    try:
        stats = psutil.net_if_stats()
        for iface, stat in stats.items():
            if stat.isup:
                lower = iface.lower()
                if "wi-fi" in lower or "wlan" in lower: return "Wi-Fi"
                if "ethernet" in lower or "以太网" in lower: return "Ethernet"
        return "Unknown"
    except:
        return "Unknown"


def get_net_io():
    try:
        return psutil.net_io_counters()
    except:
        return None


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"



def get_system_proxy():
    # 获取是否开启代理
    stdout_enable = bash(
        r'reg query "HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyEnable'
    )
    if not stdout_enable:
        return None

    m = re.search(r'ProxyEnable\s+REG_DWORD\s+0x(\d+)', stdout_enable)
    if not m:
        return None

    enabled = (m.group(1) == "1")

    # ⭐ 没开启代理 → 当作没有代理
    if not enabled:
        return None

    # 获取代理地址
    stdout_server = bash(
        r'reg query "HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyServer'
    )
    if not stdout_server:
        return None

    m2 = re.search(r'ProxyServer\s+REG_SZ\s+(.+)', stdout_server)
    if not m2:
        return None

    proxy = m2.group(1).strip()
    return proxy if proxy else None


def refresh_system_proxy():
    try:
        ctypes.windll.wininet.InternetSetOptionW(0, 39, 0, 0)
        ctypes.windll.wininet.InternetSetOptionW(0, 37, 0, 0)
    except:
        pass


def set_proxy(proxy):
    origin = get_system_proxy()
    if origin == proxy: return None
    bash(
        r'reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyEnable /t REG_DWORD /d 1 /f >nul 2>nul')
    bash(
        rf'reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyServer /d "{proxy}" /f >nul 2>nul')
    refresh_system_proxy()
    return origin


def reset_proxy(proxy, target_proxy):
    if proxy and proxy != '' and proxy != target_proxy:
        set_proxy(proxy)
    else:
        bash(
            r'reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyEnable /t REG_DWORD /d 0 /f >nul 2>nul')
        bash(
            r'reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyServer /d "" /f >nul 2>nul')
    refresh_system_proxy()

def get_process_by_port(port: int):
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            connections = proc.net_connections()
            for conn in connections:
                if getattr(conn.laddr, 'port', None) == port and conn.status == psutil.CONN_LISTEN:
                    return proc
        except:
            pass
    return None


def is_port_in_use(port: int) -> bool: return get_process_by_port(port) is not None


def bash(command: str) -> str:
    try:
        p = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,  # 让字符串命令可用
            text=True,  # 返回字符串而不是字节
            creationflags=subprocess.CREATE_NO_WINDOW  # ⭐ 隐藏黑窗口（关键）
        )
        out, _ = p.communicate()
        return out if out else ""
    except:
        return ""


def check_port_listening(host, port, timeout=0.05):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except:
        return False


def kill_process_tree(pid: int):
    bash(f"taskkill /PID {pid} /F /T >nul 2>&1")


def check_cert():
    # 使用 os.popen 检查输出
    stdout = bash('certutil -user -store root | findstr mitmproxy')
    return bool(stdout and "mitmproxy" in stdout)