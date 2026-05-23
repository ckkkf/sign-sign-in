import { execFile, exec } from "node:child_process";
import { promisify } from "node:util";
import { networkInterfaces } from "node:os";
import { shell } from "electron";

const execFileAsync = promisify(execFile);
const execAsync = promisify(exec);

export function isWindows(): boolean {
  return process.platform === "win32";
}

export function isMacos(): boolean {
  return process.platform === "darwin";
}

export async function openSystemProxySettings(): Promise<boolean> {
  if (isWindows()) {
    await execAsync("rundll32.exe shell32.dll,Control_RunDLL inetcpl.cpl,,4");
    return true;
  }
  if (isMacos()) {
    await shell.openExternal("x-apple.systempreferences:com.apple.Network-Settings.extension");
    return true;
  }
  return false;
}

export async function openCertManager(): Promise<boolean> {
  if (isWindows()) {
    await execAsync("certmgr.msc");
    return true;
  }
  if (isMacos()) {
    await shell.openPath("/System/Applications/Utilities/Keychain Access.app");
    return true;
  }
  return false;
}

export function getLocalIp(): string {
  const nets = networkInterfaces();
  for (const addresses of Object.values(nets)) {
    for (const addr of addresses || []) {
      if (addr.family === "IPv4" && !addr.internal) return addr.address;
    }
  }
  return "127.0.0.1";
}

function classifyNetworkName(name: string): string {
  const lower = name.toLowerCase();
  if (/wi-?fi|wlan|wireless|airport|无线/.test(lower)) return "Wi-Fi";
  if (/ethernet|以太网|有线|thunderbolt|usb.*lan/.test(lower)) return "有线";
  if (/ppp|pppoe|dial|拨号/.test(lower)) return "拨号";
  if (/^wl/.test(lower)) return "Wi-Fi";
  if (/^(en|eth)/.test(lower)) return "有线";
  return "";
}

function getNetworkTypeFromInterfaces(): string {
  const nets = networkInterfaces();
  for (const [name, addresses] of Object.entries(nets)) {
    if (!addresses?.some((addr) => addr.family === "IPv4" && !addr.internal)) continue;
    const type = classifyNetworkName(name);
    if (type) return type;
  }
  return "未知";
}

async function getMacosDefaultInterface(): Promise<string> {
  const { stdout } = await execFileAsync("route", ["-n", "get", "default"]);
  return stdout.match(/interface:\s*(\S+)/)?.[1]?.trim() || "";
}

async function getMacosHardwarePort(device: string): Promise<string> {
  if (!device) return "";
  const { stdout } = await execFileAsync("networksetup", ["-listallhardwareports"]);
  const blocks = stdout.split(/\n\n+/);
  for (const block of blocks) {
    const port = block.match(/Hardware Port:\s*(.+)/)?.[1]?.trim();
    const foundDevice = block.match(/Device:\s*(.+)/)?.[1]?.trim();
    if (foundDevice === device) return port || "";
  }
  return "";
}

export async function getNetworkType(): Promise<string> {
  if (isMacos()) {
    const device = await getMacosDefaultInterface();
    const port = await getMacosHardwarePort(device);
    return classifyNetworkName(port || device) || port || device || "未知";
  }
  if (isWindows()) {
    const { stdout } = await execAsync(
      "powershell -NoProfile -Command \"Get-NetAdapter | Where-Object {$_.Status -eq 'Up'} | Select-Object -First 1 -ExpandProperty InterfaceDescription\""
    );
    return classifyNetworkName(stdout.trim()) || stdout.trim() || "未知";
  }
  return getNetworkTypeFromInterfaces();
}

async function macosNetworkServices(): Promise<string[]> {
  const { stdout } = await execFileAsync("networksetup", ["-listallnetworkservices"]);
  return stdout
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith("An asterisk"))
    .map((line) => line.replace(/^\*/, "").trim());
}

export async function getSystemProxy(): Promise<string> {
  if (isMacos()) {
    const services = await macosNetworkServices();
    for (const service of services) {
      const { stdout } = await execFileAsync("networksetup", ["-getwebproxy", service]);
      if (!stdout.includes("Enabled: Yes")) continue;
      const server = stdout.match(/Server:\s*(.+)/)?.[1]?.trim();
      const port = stdout.match(/Port:\s*(\d+)/)?.[1]?.trim();
      if (server && port) return `${server}:${port}`;
    }
    return "";
  }
  if (isWindows()) {
    const enable = await execAsync(
      'reg query "HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings" /v ProxyEnable'
    ).catch(() => ({ stdout: "" }));
    if (!/ProxyEnable\s+REG_DWORD\s+0x1/.test(enable.stdout)) return "";
    const server = await execAsync(
      'reg query "HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings" /v ProxyServer'
    ).catch(() => ({ stdout: "" }));
    return server.stdout.match(/ProxyServer\s+REG_SZ\s+(.+)/)?.[1]?.trim() || "";
  }
  return "";
}

export async function setSystemProxy(proxy: string): Promise<string> {
  const origin = await getSystemProxy();
  if (origin === proxy) return "";
  const [host, port] = proxy.split(":");
  if (isMacos()) {
    const services = await macosNetworkServices();
    if (!services.length) throw new Error("macOS 获取网络服务失败，无法自动设置系统代理");
    for (const service of services) {
      await execFileAsync("networksetup", ["-setwebproxy", service, host, port]);
      await execFileAsync("networksetup", ["-setsecurewebproxy", service, host, port]);
    }
    return origin;
  }
  if (isWindows()) {
    await execAsync(
      'reg add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings" /v ProxyEnable /t REG_DWORD /d 1 /f'
    );
    await execAsync(
      `reg add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings" /v ProxyServer /d "${proxy}" /f`
    );
    await refreshWindowsProxy();
    return origin;
  }
  return origin;
}

export async function resetSystemProxy(origin: string, targetProxy: string): Promise<void> {
  if (isMacos()) {
    const services = await macosNetworkServices();
    if (origin && origin !== targetProxy) {
      await setSystemProxy(origin);
      return;
    }
    for (const service of services) {
      await execFileAsync("networksetup", ["-setwebproxystate", service, "off"]);
      await execFileAsync("networksetup", ["-setsecurewebproxystate", service, "off"]);
    }
    return;
  }
  if (isWindows()) {
    if (origin && origin !== targetProxy) {
      await setSystemProxy(origin);
      return;
    }
    await execAsync(
      'reg add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings" /v ProxyEnable /t REG_DWORD /d 0 /f'
    );
    await execAsync('reg add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings" /v ProxyServer /d "" /f');
    await refreshWindowsProxy();
  }
}

async function refreshWindowsProxy(): Promise<void> {
  if (!isWindows()) return;
  await execAsync(
    'powershell -NoProfile -Command "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Application]::DoEvents()"'
  ).catch(() => undefined);
}

/**
 * 杀掉微信小程序渲染进程，但保留微信主进程（避免影响 weixin:// URI 唤起）。
 * 必须在唤起小程序之前 / 登录成功之后调用。
 *
 * Windows: WeChatAppEx.exe / WeixinAppEx.exe
 * macOS:   WeChatAppEx (进程名匹配)
 *
 * @returns 实际尝试 kill 的次数（不一定都命中）
 */
export async function killWeChatAppEx(): Promise<number> {
  let attempted = 0;
  if (isWindows()) {
    for (const name of ["WeChatAppEx.exe", "WeixinAppEx.exe"]) {
      attempted++;
      await execFileAsync("taskkill", ["/F", "/IM", name]).catch(() => undefined);
    }
  } else if (isMacos()) {
    attempted++;
    await execFileAsync("pkill", ["-9", "-f", "WeChatAppEx"]).catch(() => undefined);
  }
  // 给系统一点时间清理
  await new Promise((r) => setTimeout(r, 300));
  return attempted;
}

/**
 * 通过 weixin:// URI Scheme 唤起指定 appid 的小程序。
 * 失败时会重试。
 */
export async function wakeApplet(appId: string, retries = 3): Promise<void> {
  const urls = [
    `weixin://launchapplet/?appid=${appId}`,
    `weixin://launchapplet?appid=${appId}`
  ];
  let lastError: unknown = null;
  for (let i = 0; i < retries; i++) {
    for (const url of urls) {
      try {
        await shell.openExternal(url);
        await new Promise((r) => setTimeout(r, 800));
        return;
      } catch (error) {
        lastError = error;
        await new Promise((r) => setTimeout(r, 800));
      }
    }
  }
  throw lastError instanceof Error ? lastError : new Error(String(lastError));
}
