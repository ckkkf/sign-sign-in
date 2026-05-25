import { ipcMain } from "electron";
import type { ApiResult } from "@shared/types";
import { configStore } from "../services/configStore";
import { imageStore } from "../services/imageStore";
import { codeCaptureService } from "../services/codeCaptureService";
import { openCertManager, openSystemProxySettings } from "../services/systemService";
import { getSystemStatus } from "../services/statusService";
import { signTaskService } from "../services/signTaskService";
import { logger } from "../services/logger";
import { authService } from "../services/authService";
import { buildSubmitPayload } from "@shared/jielongCore";
import { buildLocalMediaFiles } from "../services/jielongMedia";
import { jielongService, looksLikeInvalidJieLongToken } from "../services/jielongService";

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
  ipcMain.handle("auth:getState", () => wrap(() => authService.getState()));
  ipcMain.handle("auth:saveLogin", (_event, payload) => wrap(() => authService.saveLogin(payload)));
  ipcMain.handle("auth:logout", () => wrap(() => authService.logout()));
  ipcMain.handle("auth:offline", () => wrap(() => authService.offline()));

  ipcMain.handle("config:read", () => wrap(() => configStore.read()));
  ipcMain.handle("config:save", (_event, config) => wrap(() => configStore.write(config)));

  ipcMain.handle("task:startSign", (_event, option) => wrap(() => signTaskService.start(option)));
  ipcMain.handle("task:stopSign", () => wrap(() => signTaskService.stop()));
  ipcMain.handle("task:getState", () => wrap(() => signTaskService.getState()));
  ipcMain.handle("task:refreshSessionFromCode", () => wrap(() => signTaskService.refreshSessionFromCapturedCode()));

  ipcMain.handle("code:startCapture", () => wrap(() => codeCaptureService.start()));
  ipcMain.handle("code:stopCapture", () => wrap(() => codeCaptureService.stop()));
  ipcMain.handle("code:getState", () => wrap(() => codeCaptureService.getState()));
  ipcMain.handle("code:setManualCode", (_event, code) => wrap(() => codeCaptureService.setManualCode(code)));

  ipcMain.handle("system:getStatus", () => wrap(() => getSystemStatus()));
  ipcMain.handle("system:openProxySettings", () => wrap(() => openSystemProxySettings()));
  ipcMain.handle("system:openCertManager", () => wrap(() => openCertManager()));

  ipcMain.handle("image:list", () => wrap(() => imageStore.list()));
  ipcMain.handle("image:import", () => wrap(() => imageStore.import()));
  ipcMain.handle("image:rename", (_event, path, name) => wrap(() => imageStore.rename(path, name)));
  ipcMain.handle("image:replace", (_event, path) => wrap(() => imageStore.replace(path)));
  ipcMain.handle("image:delete", (_event, path) => wrap(() => imageStore.delete(path)));
  ipcMain.handle("image:openDir", () => wrap(() => imageStore.openDir()));

  ipcMain.handle("jielong:getSettings", () => wrap(() => jielongService.getSettings()));
  ipcMain.handle("jielong:saveSettings", (_event, settings) => wrap(() => jielongService.saveSettings(settings)));
  ipcMain.handle("jielong:createQrLogin", () => wrap(() => jielongService.createQrLogin()));
  ipcMain.handle("jielong:pollQrLogin", (_event, uuid) => wrap(() => jielongService.pollQrLogin(uuid)));
  ipcMain.handle("jielong:exchangeQrToken", (_event, code) => wrap(() => jielongService.exchangeQrToken(code)));
  ipcMain.handle("jielong:parseShareUrl", (_event, shareUrl) => wrap(() => jielongService.parseShareUrl(shareUrl)));
  ipcMain.handle("jielong:loadForm", (_event, token, threadId) => wrap(() => jielongService.loadForm(token, threadId)));
  ipcMain.handle("jielong:getDraft", (_event, threadId) => wrap(() => jielongService.getDraft(threadId)));
  ipcMain.handle("jielong:saveDraft", (_event, threadId, answers) => wrap(() => jielongService.saveDraft(threadId, answers)));
  ipcMain.handle("jielong:buildLocalMediaFiles", (_event, paths) => wrap(() => buildLocalMediaFiles(paths)));
  ipcMain.handle("jielong:buildSubmitPayload", (_event, bundle, answers, signature, number) =>
    wrap(() => buildSubmitPayload(bundle, answers, signature, number))
  );
  ipcMain.handle("jielong:submit", (_event, token, payload) =>
    wrap(async () => {
      try {
        return await jielongService.submit(token, payload);
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        if ((error as Error & { code?: string }).code === "SIGNATURE_MISMATCH") {
          return { signatureMismatch: true, message };
        }
        if (looksLikeInvalidJieLongToken(message)) {
          jielongService.saveSettings({ authorization: "" });
        }
        throw error;
      }
    })
  );

  ipcMain.handle("log:clear", () =>
    wrap(() => {
      logger.clear();
      return true;
    })
  );
}
