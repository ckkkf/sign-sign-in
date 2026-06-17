import { EventEmitter } from "node:events";
import type { BrowserWindow } from "electron";
import type { LogEntry } from "@shared/types";

export class AppLogger {
  private readonly emitter = new EventEmitter();
  private readonly entries: LogEntry[] = [];
  private windows = new Set<BrowserWindow>();
  private readonly suppressedPatterns = [
    /^\[AUTH\]/,
    /^\[Analytics\]/,
    /\/xyb\/auth\/client-log/,
    /上报客户端日志/,
    /上报失败/
  ];

  attachWindow(window: BrowserWindow): void {
    this.windows.add(window);
    window.on("closed", () => this.windows.delete(window));
  }

  subscribe(listener: (entry: LogEntry) => void): () => void {
    this.emitter.on("entry", listener);
    return () => this.emitter.off("entry", listener);
  }

  list(): LogEntry[] {
    return [...this.entries];
  }

  clear(): void {
    this.entries.length = 0;
  }

  debug(message: string): void {
    this.push("debug", message);
  }

  info(message: string): void {
    this.push("info", message);
  }

  warn(message: string): void {
    this.push("warn", message);
  }

  error(message: string): void {
    this.push("error", message);
  }

  private push(level: LogEntry["level"], message: string): void {
    if (this.shouldSuppress(message)) {
      return;
    }
    const entry: LogEntry = {
      level,
      message,
      time: new Date().toLocaleString("zh-CN", { hour12: false })
    };
    this.entries.push(entry);
    if (this.entries.length > 1000) {
      this.entries.shift();
    }
    this.emitter.emit("entry", entry);
    for (const window of this.windows) {
      if (!window.isDestroyed()) {
        window.webContents.send("log:entry", entry);
      }
    }
  }

  private shouldSuppress(message: string): boolean {
    return this.suppressedPatterns.some((pattern) => pattern.test(message));
  }
}

export const logger = new AppLogger();
