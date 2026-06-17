import { ipcMain } from "electron";
import type { ApiResult, ClientOperLogPayload } from "@shared/types";
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
import { analyticsService } from "../services/analyticsService";
import { buildSubmitPayload } from "@shared/jielongCore";
import { buildLocalMediaFiles } from "../services/jielongMedia";
import { jielongService, looksLikeInvalidJieLongToken } from "../services/jielongService";

const SKIP_ANALYTICS_CHANNELS = new Set([
  "analytics:track",
  "auth:getState",
  "config:read",
  "task:getState",
  "autoClock:getState",
  "update:getDownloadState",
  "code:getState",
  "system:getStatus",
  "image:list",
  "log:clear",
  "jielong:getSettings",
  "jielong:pollQrLogin",
  "jielong:getDraft",
  "jielong:buildSubmitPayload",
  "jielong:buildLocalMediaFiles"
]);

const SENSITIVE_KEYS = ["token", "authorization", "password", "code", "captcha", "uuid", "encrypt", "session", "openid", "unionid", "apikey", "apiKey"];

function safeString(value: unknown): string {
  if (typeof value === "string") {
    if (value.length <= 12) return value;
    return `${value.slice(0, 6)}...${value.slice(-4)}`;
  }
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (value === null || value === undefined) return "";
  return Object.prototype.toString.call(value);
}

function sanitizeValue(value: unknown, key = ""): unknown {
  if (SENSITIVE_KEYS.some((item) => key.toLowerCase().includes(item.toLowerCase()))) {
    return value ? "***" : "";
  }
  if (typeof value === "string") {
    return value.length > 160 ? `${value.slice(0, 160)}...(${value.length})` : value;
  }
  if (Array.isArray(value)) {
    return { type: "array", length: value.length };
  }
  if (value && typeof value === "object") {
    const output: Record<string, unknown> = {};
    Object.entries(value as Record<string, unknown>)
      .slice(0, 12)
      .forEach(([childKey, childValue]) => {
        output[childKey] = sanitizeValue(childValue, childKey);
      });
    return output;
  }
  return value;
}

function stringifySafe(value: unknown): string {
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function summarizeArgs(args: unknown[]): string {
  if (!args.length) return "";
  return stringifySafe(args.map((arg, index) => sanitizeValue(arg, `arg${index}`)));
}

function summarizeData(data: unknown): string {
  if (Array.isArray(data)) return `array length=${data.length}`;
  if (!data || typeof data !== "object") return safeString(data);
  const value = data as Record<string, unknown>;
  const summary: Record<string, unknown> = { type: data.constructor?.name || "Object" };
  for (const key of ["message", "running", "paused", "enabled", "tag", "currentVersion", "latestVersion", "hasUpdate", "fileName", "taskCount"]) {
    if (key in value) summary[key] = sanitizeValue(value[key], key);
  }
  for (const key of ["items", "history", "blogs", "weeks", "years", "fields", "historyReleases"]) {
    const item = value[key];
    if (Array.isArray(item)) summary[`${key}Length`] = item.length;
  }
  return stringifySafe(summary);
}

function titleForChannel(channel: string): string {
  const map: Record<string, string> = {
    "auth:saveLogin": "客户端保存登录态",
    "auth:logout": "客户端清理登录态",
    "auth:offline": "进入离线模式",
    "config:save": "保存客户端配置",
    "task:startSign": "执行签到任务",
    "task:stopSign": "停止签到任务",
    "task:refreshSessionFromCode": "使用抓包 code 续期",
    "autoClock:start": "启动定时打卡",
    "autoClock:stop": "停止定时打卡",
    "autoClock:reload": "重载定时打卡",
    "autoClock:testNotification": "测试通知渠道",
    "update:check": "检查更新",
    "update:loadMoreHistory": "加载历史版本",
    "update:saveSettings": "保存更新设置",
    "update:browseDownloadDir": "选择下载目录",
    "update:download": "下载更新包",
    "update:pause": "暂停下载",
    "update:resume": "继续下载",
    "update:stop": "停止下载",
    "update:openDownloadDir": "打开下载目录",
    "update:openRelease": "打开版本页面",
    "update:openCompare": "打开版本对比",
    "update:install": "安装更新包",
    "update:deletePackage": "删除安装包",
    "weeklyJournal:init": "打开 AI 与周记",
    "weeklyJournal:loadYears": "加载周记年份",
    "weeklyJournal:loadWeeks": "加载周记周次",
    "weeklyJournal:loadBlogs": "加载周记列表",
    "weeklyJournal:generate": "AI 生成周记",
    "weeklyJournal:submit": "提交周记",
    "code:startCapture": "启动抓包",
    "code:stopCapture": "停止抓包",
    "code:setManualCode": "手动设置 code",
    "system:openProxySettings": "打开系统代理设置",
    "system:openCertManager": "打开证书管理",
    "system:openUserDataDir": "打开用户数据目录",
    "system:openConfigFile": "打开配置文件",
    "system:openTerminal": "打开终端",
    "system:flushDns": "刷新 DNS 缓存",
    "system:openExternal": "打开外部链接",
    "image:import": "导入照片",
    "image:rename": "重命名照片",
    "image:replace": "替换照片",
    "image:delete": "删除照片",
    "image:openDir": "打开照片目录",
    "jielong:saveSettings": "保存接龙配置",
    "jielong:createQrLogin": "创建接龙扫码登录",
    "jielong:pollQrLogin": "轮询接龙扫码状态",
    "jielong:exchangeQrToken": "交换接龙登录凭据",
    "jielong:parseShareUrl": "解析接龙分享链接",
    "jielong:loadForm": "加载接龙表单",
    "jielong:saveDraft": "保存接龙草稿",
    "jielong:submit": "提交接龙打卡"
  };
  return map[channel] || `客户端操作 ${channel}`;
}

async function reportIpc(channel: string, payload: Omit<ClientOperLogPayload, "operType" | "title"> & { title?: string }): Promise<void> {
  if (SKIP_ANALYTICS_CHANNELS.has(channel)) return;
  await analyticsService.track({
    operType: "IPC_OPERATION",
    title: payload.title || titleForChannel(channel),
    requestUrl: `ipc://${channel}`,
    ...payload
  });
}

async function wrap<T>(channel: string, args: unknown[], fn: () => T | Promise<T>): Promise<ApiResult<T>> {
  const startedAt = Date.now();
  try {
    const data = await fn();
    await reportIpc(channel, {
      status: "0",
      requestParam: summarizeArgs(args),
      responseSummary: summarizeData(data),
      costTime: Date.now() - startedAt
    }).catch(() => undefined);
    return { ok: true, data };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    logger.error(message);
    await reportIpc(channel, {
      status: "1",
      requestParam: summarizeArgs(args),
      errorMsg: message,
      costTime: Date.now() - startedAt
    }).catch(() => undefined);
    return { ok: false, error: message };
  }
}

export function registerIpc(): void {
  ipcMain.handle("auth:getState", () => wrap("auth:getState", [], () => authService.getState()));
  ipcMain.handle("auth:saveLogin", (_event, payload) => wrap("auth:saveLogin", [payload], () => authService.saveLogin(payload)));
  ipcMain.handle("auth:logout", () => wrap("auth:logout", [], () => authService.logout()));
  ipcMain.handle("auth:offline", () => wrap("auth:offline", [], () => authService.offline()));

  ipcMain.handle("config:read", () => wrap("config:read", [], () => configStore.read()));
  ipcMain.handle("config:save", (_event, config) => wrap("config:save", [config], () => configStore.write(config)));

  ipcMain.handle("task:startSign", (_event, option) => wrap("task:startSign", [option], () => signTaskService.start(option)));
  ipcMain.handle("task:stopSign", () => wrap("task:stopSign", [], () => signTaskService.stop()));
  ipcMain.handle("task:getState", () => wrap("task:getState", [], () => signTaskService.getState()));
  ipcMain.handle("task:refreshSessionFromCode", () => wrap("task:refreshSessionFromCode", [], () => signTaskService.refreshSessionFromCapturedCode()));

  ipcMain.handle("autoClock:getState", () => wrap("autoClock:getState", [], () => autoClockService.getState()));
  ipcMain.handle("autoClock:start", () => wrap("autoClock:start", [], () => autoClockService.start()));
  ipcMain.handle("autoClock:stop", () => wrap("autoClock:stop", [], () => autoClockService.stop()));
  ipcMain.handle("autoClock:reload", () => wrap("autoClock:reload", [], () => autoClockService.reload()));
  ipcMain.handle("autoClock:testNotification", (_event, channel) => wrap("autoClock:testNotification", [channel], () => autoClockService.testNotification(channel)));

  ipcMain.handle("update:check", () => wrap("update:check", [], () => updateService.check()));
  ipcMain.handle("update:loadMoreHistory", (_event, cursor, excludeTag) => wrap("update:loadMoreHistory", [cursor, excludeTag], () => updateService.loadMoreHistory(cursor, excludeTag)));
  ipcMain.handle("update:getSettings", () => wrap("update:getSettings", [], () => updateService.getSettings()));
  ipcMain.handle("update:saveSettings", (_event, settings) => wrap("update:saveSettings", [settings], () => updateService.saveSettings(settings)));
  ipcMain.handle("update:browseDownloadDir", () => wrap("update:browseDownloadDir", [], () => updateService.browseDownloadDir()));
  ipcMain.handle("update:download", (_event, tag) => wrap("update:download", [tag], () => updateService.download(tag)));
  ipcMain.handle("update:getDownloadState", () => wrap("update:getDownloadState", [], () => updateService.getDownloadState()));
  ipcMain.handle("update:pause", () => wrap("update:pause", [], () => updateService.pause()));
  ipcMain.handle("update:resume", () => wrap("update:resume", [], () => updateService.resume()));
  ipcMain.handle("update:stop", () => wrap("update:stop", [], () => updateService.stop()));
  ipcMain.handle("update:openDownloadDir", () => wrap("update:openDownloadDir", [], () => updateService.openDownloadDir()));
  ipcMain.handle("update:openRelease", (_event, tag) => wrap("update:openRelease", [tag], () => updateService.openRelease(tag)));
  ipcMain.handle("update:openCompare", (_event, tag) => wrap("update:openCompare", [tag], () => updateService.openCompare(tag)));
  ipcMain.handle("update:install", (_event, tag) => wrap("update:install", [tag], () => updateService.install(tag)));
  ipcMain.handle("update:deletePackage", (_event, tag) => wrap("update:deletePackage", [tag], () => updateService.deletePackage(tag)));

  ipcMain.handle("weeklyJournal:init", () => wrap("weeklyJournal:init", [], () => weeklyJournalService.init()));
  ipcMain.handle("weeklyJournal:loadYears", () => wrap("weeklyJournal:loadYears", [], () => weeklyJournalService.loadYears()));
  ipcMain.handle("weeklyJournal:loadWeeks", (_event, year, month) => wrap("weeklyJournal:loadWeeks", [year, month], () => weeklyJournalService.loadWeeks(year, month)));
  ipcMain.handle("weeklyJournal:loadBlogs", (_event, page) => wrap("weeklyJournal:loadBlogs", [page], () => weeklyJournalService.loadBlogs(page)));
  ipcMain.handle("weeklyJournal:generate", (_event, prompt) => wrap("weeklyJournal:generate", [{ promptLength: String(prompt || "").length }], () => weeklyJournalService.generate(prompt)));
  ipcMain.handle("weeklyJournal:submit", (_event, payload) => wrap("weeklyJournal:submit", [payload], () => weeklyJournalService.submit(payload)));

  ipcMain.handle("code:startCapture", () => wrap("code:startCapture", [], () => codeCaptureService.start()));
  ipcMain.handle("code:stopCapture", () => wrap("code:stopCapture", [], () => codeCaptureService.stop()));
  ipcMain.handle("code:getState", () => wrap("code:getState", [], () => codeCaptureService.getState()));
  ipcMain.handle("code:setManualCode", (_event, code) => wrap("code:setManualCode", [{ codeLength: String(code || "").length }], () => codeCaptureService.setManualCode(code)));

  ipcMain.handle("system:getStatus", () => wrap("system:getStatus", [], () => getSystemStatus()));
  ipcMain.handle("system:openProxySettings", () => wrap("system:openProxySettings", [], () => openSystemProxySettings()));
  ipcMain.handle("system:openCertManager", () => wrap("system:openCertManager", [], () => openCertManager()));
  ipcMain.handle("system:openUserDataDir", () => wrap("system:openUserDataDir", [], () => openUserDataDir()));
  ipcMain.handle("system:openConfigFile", () => wrap("system:openConfigFile", [], () => openConfigFile()));
  ipcMain.handle("system:openTerminal", () => wrap("system:openTerminal", [], () => openTerminal()));
  ipcMain.handle("system:flushDns", () => wrap("system:flushDns", [], () => flushDnsCache()));
  ipcMain.handle("system:openExternal", (_event, url) => wrap("system:openExternal", [url], () => openExternalUrl(url)));

  ipcMain.handle("image:list", () => wrap("image:list", [], () => imageStore.list()));
  ipcMain.handle("image:import", () => wrap("image:import", [], () => imageStore.import()));
  ipcMain.handle("image:rename", (_event, path, name) => wrap("image:rename", [path, name], () => imageStore.rename(path, name)));
  ipcMain.handle("image:replace", (_event, path) => wrap("image:replace", [path], () => imageStore.replace(path)));
  ipcMain.handle("image:delete", (_event, path) => wrap("image:delete", [path], () => imageStore.delete(path)));
  ipcMain.handle("image:openDir", () => wrap("image:openDir", [], () => imageStore.openDir()));

  ipcMain.handle("jielong:getSettings", () => wrap("jielong:getSettings", [], () => jielongService.getSettings()));
  ipcMain.handle("jielong:saveSettings", (_event, settings) => wrap("jielong:saveSettings", [settings], () => jielongService.saveSettings(settings)));
  ipcMain.handle("jielong:createQrLogin", () => wrap("jielong:createQrLogin", [], () => jielongService.createQrLogin()));
  ipcMain.handle("jielong:pollQrLogin", (_event, uuid) => wrap("jielong:pollQrLogin", [uuid], () => jielongService.pollQrLogin(uuid)));
  ipcMain.handle("jielong:exchangeQrToken", (_event, code) => wrap("jielong:exchangeQrToken", [{ codeLength: String(code || "").length }], () => jielongService.exchangeQrToken(code)));
  ipcMain.handle("jielong:parseShareUrl", (_event, shareUrl) => wrap("jielong:parseShareUrl", [shareUrl], () => jielongService.parseShareUrl(shareUrl)));
  ipcMain.handle("jielong:loadForm", (_event, token, threadId) => wrap("jielong:loadForm", [{ hasToken: Boolean(token), threadId }], () => jielongService.loadForm(token, threadId)));
  ipcMain.handle("jielong:getDraft", (_event, threadId) => wrap("jielong:getDraft", [threadId], () => jielongService.getDraft(threadId)));
  ipcMain.handle("jielong:saveDraft", (_event, threadId, answers) => wrap("jielong:saveDraft", [threadId, answers], () => jielongService.saveDraft(threadId, answers)));
  ipcMain.handle("jielong:buildLocalMediaFiles", (_event, paths) => wrap("jielong:buildLocalMediaFiles", [paths], () => buildLocalMediaFiles(paths)));
  ipcMain.handle("jielong:buildSubmitPayload", (_event, bundle, answers, signature, number) =>
    wrap("jielong:buildSubmitPayload", [bundle, answers, { hasSignature: Boolean(signature), number }], () => buildSubmitPayload(bundle, answers, signature, number))
  );
  ipcMain.handle("jielong:submit", (_event, token, payload) =>
    wrap("jielong:submit", [{ hasToken: Boolean(token), payload }], async () => {
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
    wrap("log:clear", [], () => { logger.clear(); return true; })
  );

  ipcMain.handle("analytics:track", (_event, payload) => wrap("analytics:track", [payload], () => analyticsService.track(payload)));
}
