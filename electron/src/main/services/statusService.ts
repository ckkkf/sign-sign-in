import { MITM_HOST, MITM_PORT } from "@shared/constants";
import type { SystemStatus } from "@shared/types";
import { codeCaptureService } from "./codeCaptureService";
import { certService } from "./certService";
import { getLocalIp, getSystemProxy } from "./systemService";
import { sessionStore } from "./sessionStore";

export async function getSystemStatus(): Promise<SystemStatus> {
  return {
    time: new Date().toLocaleString("zh-CN", { hour12: false }),
    proxy: (await getSystemProxy().catch(() => "")) || "直连",
    proxyServerRunning: codeCaptureService.getState().running,
    certInstalled: await certService.isTrusted().catch(() => false),
    ip: getLocalIp(),
    sessionValid: Boolean(sessionStore.read())
  };
}

export const targetProxy = `${MITM_HOST}:${MITM_PORT}`;
