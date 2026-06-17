import { contextBridge, ipcRenderer } from "electron";
import type {
  AuthSessionPayload,
  AutoClockNotificationConfig,
  ClientOperLogPayload,
  JieLongFieldAnswer,
  JieLongFormBundle,
  JieLongSettings,
  JieLongSubmitPayload,
  LogEntry,
  SignConfig,
  SignOption,
  UpdateSettings,
  WeeklyJournalSubmitPayload
} from "@shared/types";
import type { SignSignInApi } from "@shared/ipc";

const api: SignSignInApi = {
  auth: {
    getState: () => ipcRenderer.invoke("auth:getState"),
    saveLogin: (payload: AuthSessionPayload) => ipcRenderer.invoke("auth:saveLogin", payload),
    logout: () => ipcRenderer.invoke("auth:logout"),
    offline: () => ipcRenderer.invoke("auth:offline")
  },
  config: {
    read: () => ipcRenderer.invoke("config:read"),
    save: (config: SignConfig) => ipcRenderer.invoke("config:save", config)
  },
  task: {
    startSign: (option: SignOption) => ipcRenderer.invoke("task:startSign", option),
    stopSign: () => ipcRenderer.invoke("task:stopSign"),
    getState: () => ipcRenderer.invoke("task:getState"),
    refreshSessionFromCode: () => ipcRenderer.invoke("task:refreshSessionFromCode")
  },
  autoClock: {
    getState: () => ipcRenderer.invoke("autoClock:getState"),
    start: () => ipcRenderer.invoke("autoClock:start"),
    stop: () => ipcRenderer.invoke("autoClock:stop"),
    reload: () => ipcRenderer.invoke("autoClock:reload"),
    testNotification: (channel: AutoClockNotificationConfig) => ipcRenderer.invoke("autoClock:testNotification", channel)
  },
  update: {
    check: () => ipcRenderer.invoke("update:check"),
    loadMoreHistory: (cursor: { start: number }, excludeTag?: string) => ipcRenderer.invoke("update:loadMoreHistory", cursor, excludeTag),
    getSettings: () => ipcRenderer.invoke("update:getSettings"),
    saveSettings: (settings: Partial<UpdateSettings>) => ipcRenderer.invoke("update:saveSettings", settings),
    browseDownloadDir: () => ipcRenderer.invoke("update:browseDownloadDir"),
    download: (tag: string) => ipcRenderer.invoke("update:download", tag),
    getDownloadState: () => ipcRenderer.invoke("update:getDownloadState"),
    pause: () => ipcRenderer.invoke("update:pause"),
    resume: () => ipcRenderer.invoke("update:resume"),
    stop: () => ipcRenderer.invoke("update:stop"),
    openDownloadDir: () => ipcRenderer.invoke("update:openDownloadDir"),
    openRelease: (tag: string) => ipcRenderer.invoke("update:openRelease", tag),
    openCompare: (tag: string) => ipcRenderer.invoke("update:openCompare", tag),
    install: (tag: string) => ipcRenderer.invoke("update:install", tag),
    deletePackage: (tag: string) => ipcRenderer.invoke("update:deletePackage", tag)
  },
  weeklyJournal: {
    init: () => ipcRenderer.invoke("weeklyJournal:init"),
    loadYears: () => ipcRenderer.invoke("weeklyJournal:loadYears"),
    loadWeeks: (year: string, month: string) => ipcRenderer.invoke("weeklyJournal:loadWeeks", year, month),
    loadBlogs: (page: number) => ipcRenderer.invoke("weeklyJournal:loadBlogs", page),
    generate: (prompt: string) => ipcRenderer.invoke("weeklyJournal:generate", prompt),
    submit: (payload: WeeklyJournalSubmitPayload) => ipcRenderer.invoke("weeklyJournal:submit", payload)
  },
  code: {
    startCapture: () => ipcRenderer.invoke("code:startCapture"),
    stopCapture: () => ipcRenderer.invoke("code:stopCapture"),
    getState: () => ipcRenderer.invoke("code:getState"),
    setManualCode: (code: string) => ipcRenderer.invoke("code:setManualCode", code),
    onCaptured: (callback: (code: string) => void) => {
      const listener = (_event: Electron.IpcRendererEvent, code: string) => callback(code);
      ipcRenderer.on("code:captured", listener);
      return () => ipcRenderer.off("code:captured", listener);
    }
  },
  system: {
    getStatus: () => ipcRenderer.invoke("system:getStatus"),
    openProxySettings: () => ipcRenderer.invoke("system:openProxySettings"),
    openCertManager: () => ipcRenderer.invoke("system:openCertManager"),
    openUserDataDir: () => ipcRenderer.invoke("system:openUserDataDir"),
    openConfigFile: () => ipcRenderer.invoke("system:openConfigFile"),
    openTerminal: () => ipcRenderer.invoke("system:openTerminal"),
    flushDns: () => ipcRenderer.invoke("system:flushDns"),
    openExternal: (url: string) => ipcRenderer.invoke("system:openExternal", url)
  },
  image: {
    list: () => ipcRenderer.invoke("image:list"),
    import: () => ipcRenderer.invoke("image:import"),
    rename: (path: string, name: string) => ipcRenderer.invoke("image:rename", path, name),
    replace: (path: string) => ipcRenderer.invoke("image:replace", path),
    delete: (path: string) => ipcRenderer.invoke("image:delete", path),
    openDir: () => ipcRenderer.invoke("image:openDir")
  },
  jielong: {
    getSettings: () => ipcRenderer.invoke("jielong:getSettings"),
    saveSettings: (settings: Partial<JieLongSettings>) => ipcRenderer.invoke("jielong:saveSettings", settings),
    createQrLogin: () => ipcRenderer.invoke("jielong:createQrLogin"),
    pollQrLogin: (uuid: string) => ipcRenderer.invoke("jielong:pollQrLogin", uuid),
    exchangeQrToken: (code: string) => ipcRenderer.invoke("jielong:exchangeQrToken", code),
    parseShareUrl: (shareUrl: string) => ipcRenderer.invoke("jielong:parseShareUrl", shareUrl),
    loadForm: (token: string, threadId: string) => ipcRenderer.invoke("jielong:loadForm", token, threadId),
    getDraft: (threadId: string) => ipcRenderer.invoke("jielong:getDraft", threadId),
    saveDraft: (threadId: string, answers: Record<string, JieLongFieldAnswer>) => ipcRenderer.invoke("jielong:saveDraft", threadId, answers),
    buildLocalMediaFiles: (paths: string[]) => ipcRenderer.invoke("jielong:buildLocalMediaFiles", paths),
    buildSubmitPayload: (bundle: JieLongFormBundle, answers: Record<string, JieLongFieldAnswer>, signature: string, number: string) =>
      ipcRenderer.invoke("jielong:buildSubmitPayload", bundle, answers, signature, number),
    submit: (token: string, payload: JieLongSubmitPayload) => ipcRenderer.invoke("jielong:submit", token, payload)
  },
  log: {
    clear: () => ipcRenderer.invoke("log:clear"),
    subscribe: (callback: (entry: LogEntry) => void) => {
      const listener = (_event: Electron.IpcRendererEvent, entry: LogEntry) => callback(entry);
      ipcRenderer.on("log:entry", listener);
      return () => ipcRenderer.off("log:entry", listener);
    }
  },
  analytics: {
    track: (payload: ClientOperLogPayload) => ipcRenderer.invoke("analytics:track", payload)
  }
};

contextBridge.exposeInMainWorld("signSignIn", api);
