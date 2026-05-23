import { ipcMain } from "electron";
import type { ApiResult } from "@shared/types";
import { configStore } from "../services/configStore";
import { imageStore } from "../services/imageStore";
import { codeCaptureService } from "../services/codeCaptureService";
import { fridaHookService } from "../services/fridaHookService";
import { openCertManager, openSystemProxySettings } from "../services/systemService";
import { getSystemStatus } from "../services/statusService";
import { signTaskService } from "../services/signTaskService";
import { logger } from "../services/logger";

async function wrap<T>(fn: () => T | Promise<T>): Promise<ApiResult<T>> {
  try {
    return { ok: true, data: await fn() };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    logger.error(message);
    return { ok: false, error: message };
  }
}

export function registerIpc(): void {
  ipcMain.handle("config:read", () => wrap(() => configStore.read()));
  ipcMain.handle("config:save", (_event, config) => wrap(() => configStore.write(config)));

  ipcMain.handle("task:startSign", (_event, option) => wrap(() => signTaskService.start(option)));
  ipcMain.handle("task:stopSign", () => wrap(() => signTaskService.stop()));
  ipcMain.handle("task:getState", () => wrap(() => signTaskService.getState()));

  ipcMain.handle("code:startCapture", () => wrap(() => codeCaptureService.start()));
  ipcMain.handle("code:stopCapture", () => wrap(() => codeCaptureService.stop()));
  ipcMain.handle("code:getState", () => wrap(() => codeCaptureService.getState()));
  ipcMain.handle("code:setManualCode", (_event, code) => wrap(() => codeCaptureService.setManualCode(code)));
  ipcMain.handle("code:startFridaHook", () => wrap(() => fridaHookService.start()));
  ipcMain.handle("code:stopFridaHook", () => wrap(() => fridaHookService.stop()));

  ipcMain.handle("system:getStatus", () => wrap(() => getSystemStatus()));
  ipcMain.handle("system:openProxySettings", () => wrap(() => openSystemProxySettings()));
  ipcMain.handle("system:openCertManager", () => wrap(() => openCertManager()));

  ipcMain.handle("image:list", () => wrap(() => imageStore.list()));
  ipcMain.handle("image:import", () => wrap(() => imageStore.import()));
  ipcMain.handle("image:delete", (_event, path) => wrap(() => imageStore.delete(path)));

  ipcMain.handle("log:clear", () =>
    wrap(() => {
      logger.clear();
      return true;
    })
  );
}
