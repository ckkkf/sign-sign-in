import { ipcMain } from "electron";
import type { ApiResult } from "@shared/types";
import { configStore } from "../services/configStore";
import { imageStore } from "../services/imageStore";
import { codeCaptureService } from "../services/codeCaptureService";
import {
  flushDnsCache,
  openCertManager,
  openConfigFile,
  openExternalUrl,
  openSystemProxySettings,
  openTerminal,
  openUserDataDir
} from "../services/systemService";
import { getSystemStatus } from "../services/statusService";
import { signTaskService } from "../services/signTaskService";
import { autoClockService } from "../services/autoClockService";
import { updateService } from "../services/updateService";
import { weeklyJournalService } from "../services/weeklyJournalService";
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

  ipcMain.handle("autoClock:getState", () => wrap(() => autoClockService.getState()));
  ipcMain.handle("autoClock:start", () => wrap(() => autoClockService.start()));
  ipcMain.handle("autoClock:stop", () => wrap(() => autoClockService.stop()));
  ipcMain.handle("autoClock:reload", () => wrap(() => autoClockService.reload()));
  ipcMain.handle("autoClock:testNotification", (_event, channel) => wrap(() => autoClockService.testNotification(channel)));

  ipcMain.handle("update:check", () => wrap(() => updateService.check()));
  ipcMain.handle("update:loadMoreHistory", (_event, cursor, excludeTag) => wrap(() => updateService.loadMoreHistory(cursor, excludeTag)));
  ipcMain.handle("update:getSettings", () => wrap(() => updateService.getSettings()));
  ipcMain.handle("update:saveSettings", (_event, settings) => wrap(() => updateService.saveSettings(settings)));
  ipcMain.handle("update:browseDownloadDir", () => wrap(() => updateService.browseDownloadDir()));
  ipcMain.handle("update:download", (_event, tag) => wrap(() => updateService.download(tag)));
  ipcMain.handle("update:getDownloadState", () => wrap(() => updateService.getDownloadState()));
  ipcMain.handle("update:pause", () => wrap(() => updateService.pause()));
  ipcMain.handle("update:resume", () => wrap(() => updateService.resume()));
  ipcMain.handle("update:stop", () => wrap(() => updateService.stop()));
  ipcMain.handle("update:openDownloadDir", () => wrap(() => updateService.openDownloadDir()));
  ipcMain.handle("update:openRelease", (_event, tag) => wrap(() => updateService.openRelease(tag)));
  ipcMain.handle("update:openCompare", (_event, tag) => wrap(() => updateService.openCompare(tag)));
  ipcMain.handle("update:install", (_event, tag) => wrap(() => updateService.install(tag)));
  ipcMain.handle("update:deletePackage", (_event, tag) => wrap(() => updateService.deletePackage(tag)));

  ipcMain.handle("weeklyJournal:init", () => wrap(() => weeklyJournalService.init()));
  ipcMain.handle("weeklyJournal:loadYears", () => wrap(() => weeklyJournalService.loadYears()));
  ipcMain.handle("weeklyJournal:loadWeeks", (_event, year, month) => wrap(() => weeklyJournalService.loadWeeks(year, month)));
  ipcMain.handle("weeklyJournal:loadBlogs", (_event, page) => wrap(() => weeklyJournalService.loadBlogs(page)));
  ipcMain.handle("weeklyJournal:generate", (_event, prompt) => wrap(() => weeklyJournalService.generate(prompt)));
  ipcMain.handle("weeklyJournal:submit", (_event, payload) => wrap(() => weeklyJournalService.submit(payload)));

  ipcMain.handle("code:startCapture", () => wrap(() => codeCaptureService.start()));
  ipcMain.handle("code:stopCapture", () => wrap(() => codeCaptureService.stop()));
  ipcMain.handle("code:getState", () => wrap(() => codeCaptureService.getState()));
  ipcMain.handle("code:setManualCode", (_event, code) => wrap(() => codeCaptureService.setManualCode(code)));

  ipcMain.handle("system:getStatus", () => wrap(() => getSystemStatus()));
  ipcMain.handle("system:openProxySettings", () => wrap(() => openSystemProxySettings()));
  ipcMain.handle("system:openCertManager", () => wrap(() => openCertManager()));
  ipcMain.handle("system:openUserDataDir", () => wrap(() => openUserDataDir()));
  ipcMain.handle("system:openConfigFile", () => wrap(() => openConfigFile()));
  ipcMain.handle("system:openTerminal", () => wrap(() => openTerminal()));
  ipcMain.handle("system:flushDns", () => wrap(() => flushDnsCache()));
  ipcMain.handle("system:openExternal", (_event, url) => wrap(() => openExternalUrl(url)));

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
