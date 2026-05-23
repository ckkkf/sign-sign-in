import ctypes
import locale
import logging
import os
import re
import socket
import subprocess
import sys
import webbrowser
from types import SimpleNamespace

import psutil


def is_windows():
    return sys.platform.startswith("win")


def is_macos():
    return sys.platform == "darwin"


def subprocess_creationflags(new_console=False):
    if not is_windows():
        return 0
    return subprocess.CREATE_NEW_CONSOLE if new_console else subprocess.CREATE_NO_WINDOW


def open_path_or_url(target):
    if is_windows():
        os.startfile(target)
        return
    if is_macos():
        subprocess.Popen(["open", target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return
    webbrowser.open(target)


def open_system_proxy_settings():
    if is_windows():
        subprocess.Popen(
            "rundll32.exe shell32.dll,Control_RunDLL inetcpl.cpl,,4",
            shell=True,
            creationflags=subprocess_creationflags(),
        )
        return True
    if is_macos():
        subprocess.Popen(
            ["open", "x-apple.systempreferences:com.apple.Network-Settings.extension"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    return False


def open_cert_manager():
    if is_windows():
        subprocess.Popen("certmgr.msc", shell=True, creationflags=subprocess_creationflags())
        return True
    if is_macos():
        subprocess.Popen(["open", "/System/Applications/Utilities/Keychain Access.app"])
        return True
    return False


def open_terminal():
    if is_windows():
        subprocess.Popen(["cmd.exe"], creationflags=subprocess_creationflags(new_console=True))
        return True
    if is_macos():
        subprocess.Popen(["open", "-a", "Terminal"])
        return True
    return False


def flush_dns_cache():
    if is_windows():
        bash("ipconfig /flushdns")
        return True
    if is_macos():
        bash("dscacheutil -flushcache")
        bash("killall -HUP mDNSResponder")
        return True
    return False


def get_network_type():
    try:
        stats = psutil.net_if_stats()
        for iface, stat in stats.items():
            if stat.isup:
                lower = iface.lower()
                if "wi-fi" in lower or "wlan" in lower: return "Wi-Fi"
                if "ethernet" in lower or "以太网" in lower: return "Ethernet"
                if (
                    "ppp" in lower
                    or "wan miniport" in lower
                    or "拨号" in lower
                    or "宽带连接" in lower
                    or "ras" in lower
                ):
                    return "拨号上网"
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
    if is_macos():
        return get_macos_system_proxy()
    if not is_windows():
        return None

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


def get_macos_system_proxy():
    for service in macos_network_services():
        stdout = bash(f'networksetup -getwebproxy "{service}"')
        if "Enabled: Yes" not in stdout:
            continue
        server_match = re.search(r"Server:\s*(.+)", stdout)
        port_match = re.search(r"Port:\s*(\d+)", stdout)
        if server_match and port_match:
            return f"{server_match.group(1).strip()}:{port_match.group(1).strip()}"
    return None


def macos_network_services():
    stdout = bash("networksetup -listallnetworkservices")
    if "AuthorizationCreate() failed" in stdout:
        return []
    services = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("An asterisk"):
            continue
        if "AuthorizationCreate() failed" in line:
            continue
        services.append(line.lstrip("*").strip())
    return services


def refresh_system_proxy():
    if not is_windows():
        return
    try:
        ctypes.windll.wininet.InternetSetOptionW(0, 39, 0, 0)
        ctypes.windll.wininet.InternetSetOptionW(0, 37, 0, 0)
    except:
        pass


def set_proxy(proxy):
    origin = get_system_proxy()
    if origin == proxy: return None
    if is_macos():
        services = macos_network_services()
        if not services:
            raise RuntimeError("macOS 获取网络服务失败，无法自动设置系统代理")
        host, port = proxy.split(":", 1)
        for service in services:
            bash(f'networksetup -setwebproxy "{service}" {host} {port}')
            bash(f'networksetup -setsecurewebproxy "{service}" {host} {port}')
        if get_system_proxy() != proxy:
            raise RuntimeError(f"macOS 系统代理设置失败，请手动设置 HTTP/HTTPS 代理为 {proxy}")
        return origin
    if not is_windows():
        return origin
    bash(
        r'reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyEnable /t REG_DWORD /d 1 /f >nul 2>nul')
    bash(
        rf'reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyServer /d "{proxy}" /f >nul 2>nul')
    refresh_system_proxy()
    return origin


def reset_proxy(proxy, target_proxy):
    if is_macos():
        if proxy and proxy != target_proxy:
            set_proxy(proxy)
        else:
            for service in macos_network_services():
                bash(f'networksetup -setwebproxystate "{service}" off')
                bash(f'networksetup -setsecurewebproxystate "{service}" off')
        return
    if not is_windows():
        return
    if proxy and proxy != '' and proxy != target_proxy:
        set_proxy(proxy)
    else:
        bash(
            r'reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyEnable /t REG_DWORD /d 0 /f >nul 2>nul')
        bash(
            r'reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyServer /d "" /f >nul 2>nul')
    refresh_system_proxy()

def get_process_by_port(port: int):
    proc = get_process_by_port_psutil(port)
    if proc is not None:
        return proc
    return get_process_by_port_lsof(port)


def get_process_by_port_psutil(port: int):
    try:
        iterator = psutil.process_iter(['pid', 'name'])
    except Exception:
        return None
    try:
        for proc in iterator:
            try:
                connections = proc.net_connections()
                for conn in connections:
                    if getattr(conn.laddr, 'port', None) == port and conn.status == psutil.CONN_LISTEN:
                        return proc
            except:
                pass
    except Exception:
        return None
    return None


def get_process_by_port_lsof(port: int):
    if is_windows():
        return None
    stdout = bash(f"lsof -tiTCP:{port} -sTCP:LISTEN")
    for line in stdout.splitlines():
        line = line.strip()
        if not line.isdigit():
            continue
        pid = int(line)
        try:
            return psutil.Process(pid)
        except Exception:
            return SimpleNamespace(pid=pid)
    return None


def is_port_in_use(port: int) -> bool: return get_process_by_port(port) is not None


def bash(command: str) -> str:
    try:
        encoding = locale.getpreferredencoding(False) or "utf-8"
        p = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
            text=True,
            encoding=encoding,
            errors="ignore",
            creationflags=subprocess_creationflags()
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
    if is_windows():
        bash(f"taskkill /PID {pid} /F /T >nul 2>&1")
        return
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        for child in children:
            child.terminate()
        parent.terminate()
        _, alive = psutil.wait_procs(children + [parent], timeout=2)
        for proc in alive:
            proc.kill()
    except Exception:
        pass


def check_cert():
    if is_macos():
        stdout = bash('security find-certificate -a -c mitmproxy -Z ~/Library/Keychains/login.keychain-db')
        if stdout and "SHA-1 hash:" in stdout:
            return True
        stdout = bash('security find-certificate -a -c mitmproxy -Z /Library/Keychains/System.keychain')
        return bool(stdout and "SHA-1 hash:" in stdout)
    if not is_windows():
        return False
    # 使用 os.popen 检查输出
    stdout = bash('certutil -user -store root | findstr mitmproxy')
    return bool(stdout and "mitmproxy" in stdout)


def remove_mitmproxy_certs():
    if is_macos():
        stdout = bash('security find-certificate -a -c mitmproxy -Z ~/Library/Keychains/login.keychain-db')
        hashes = re.findall(r"SHA-1 hash:\s*([0-9A-Fa-f]+)", stdout or "")
        for cert_hash in hashes:
            bash(f'security delete-certificate -Z {cert_hash} ~/Library/Keychains/login.keychain-db')
        return len(hashes)
    if not is_windows():
        return 0
    command = (
        "powershell -NoProfile -Command "
        "\"$ErrorActionPreference='SilentlyContinue'; "
        "$certs = Get-ChildItem Cert:\\CurrentUser\\Root | Where-Object { $_.Subject -like '*mitmproxy*' }; "
        "$count = @($certs).Count; "
        "foreach ($cert in $certs) { Remove-Item -LiteralPath $cert.PSPath -Force }; "
        "Write-Output $count\""
    )
    output = (bash(command) or "").strip()
    try:
        return int(output.splitlines()[-1]) if output else 0
    except (ValueError, IndexError):
        return 0


def install_mitmproxy_cert(file_name):
    removed = remove_mitmproxy_certs()
    if removed > 0:
        logging.info(f"已清理 {removed} 个旧 mitmproxy 证书")

    if is_windows():
        while True:
            stdout = bash(f'certutil -user -addstore Root "{file_name}"')
            if stdout and ("命令成功完成" in stdout or "completed successfully" in stdout.lower()) and check_cert():
                return
            logging.warning("⚠️请点击[确定]以同意安装ssl证书，否则将无法使用本程序！")

    if is_macos():
        stdout = bash(
            f'security add-trusted-cert -d -r trustRoot -k ~/Library/Keychains/login.keychain-db "{file_name}"'
        )
        if check_cert():
            return
        open_path_or_url(file_name)
        detail = stdout.strip()
        if detail:
            raise RuntimeError(f"macOS 自动安装证书失败，已打开证书文件，请手动信任 mitmproxy 证书后重试: {detail}")
        raise RuntimeError("macOS 自动安装证书失败，已打开证书文件，请手动信任 mitmproxy 证书后重试")

    raise RuntimeError("当前系统暂不支持自动安装 mitmproxy 证书")
