import { contextBridge, ipcRenderer } from "electron";
import type { LogEntry, LoginPayload, RegisterPayload, SignConfig, SignOption } from "@shared/types";
import type { SignSignInApi } from "@shared/ipc";

const api: SignSignInApi = {
  auth: {
    getState: () => ipcRenderer.invoke("auth:getState"),
    login: (payload: LoginPayload) => ipcRenderer.invoke("auth:login", payload),
    captcha: () => ipcRenderer.invoke("auth:captcha"),
    register: (payload: RegisterPayload) => ipcRenderer.invoke("auth:register", payload),
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
    openCertManager: () => ipcRenderer.invoke("system:openCertManager")
  },
  image: {
    list: () => ipcRenderer.invoke("image:list"),
    import: () => ipcRenderer.invoke("image:import"),
    delete: (path: string) => ipcRenderer.invoke("image:delete", path)
  },
  log: {
    clear: () => ipcRenderer.invoke("log:clear"),
    subscribe: (callback: (entry: LogEntry) => void) => {
      const listener = (_event: Electron.IpcRendererEvent, entry: LogEntry) => callback(entry);
      ipcRenderer.on("log:entry", listener);
      return () => ipcRenderer.off("log:entry", listener);
    }
  }
};

contextBridge.exposeInMainWorld("signSignIn", api);
