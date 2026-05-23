import { MITM_HOST, MITM_PORT } from "@shared/constants";
import type { SystemStatus } from "@shared/types";
import { codeCaptureService } from "./codeCaptureService";
import { certService } from "./certService";
import { getLocalIp, getNetworkType, getSystemProxy } from "./systemService";
import { sessionStore } from "./sessionStore";

export async function getSystemStatus(): Promise<SystemStatus> {
  const startedAt = Date.now();
  const proxy = (await getSystemProxy().catch(() => "")) || "直连";
  const networkType = await getNetworkType().catch(() => "未知");
  const certInstalled = await certService.isTrusted().catch(() => false);
  const elapsed = Math.max(0, Date.now() - startedAt);
  return {
    time: new Date().toLocaleString("zh-CN", { hour12: false }),
    pid: process.pid,
    networkType,
    proxy,
    speed: `${elapsed} ms`,
    proxyServerRunning: codeCaptureService.getState().running,
    certInstalled,
    ip: getLocalIp(),
    sessionValid: Boolean(sessionStore.read())
  };
}

export const targetProxy = `${MITM_HOST}:${MITM_PORT}`;
