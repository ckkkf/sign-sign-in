import { app, BrowserWindow, nativeImage, Tray, Menu } from "electron";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { registerIpc } from "./ipc/registerIpc";
import { logger } from "./services/logger";
import { codeCaptureService } from "./services/codeCaptureService";

let mainWindow: BrowserWindow | null = null;
let tray: Tray | null = null;
let isQuitting = false;

function createWindow(): void {
  const preloadPath = join(__dirname, "../preload/index.mjs");
  if (!existsSync(preloadPath)) {
    logger.error(`preload 文件不存在: ${preloadPath}`);
  }

  mainWindow = new BrowserWindow({
    width: 1040,
    height: 680,
    minWidth: 960,
    minHeight: 620,
    title: "SignSignIn",
    backgroundColor: "#020617",
    webPreferences: {
      preload: preloadPath,
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false
    }
  });
  logger.attachWindow(mainWindow);
  mainWindow.webContents.on("did-fail-load", (_event, errorCode, errorDescription, validatedURL) => {
    logger.error(`渲染页面加载失败: ${errorCode} ${errorDescription} ${validatedURL}`);
  });
  mainWindow.webContents.on("render-process-gone", (_event, details) => {
    logger.error(`渲染进程退出: ${details.reason}`);
  });
  mainWindow.webContents.on("console-message", (_event, level, message, line, sourceId) => {
    if (message.includes("Electron Security Warning")) return;
    if (message.includes("ResizeObserver loop completed with undelivered notifications")) return;
    if (level >= 2) logger.error(`渲染控制台: ${message} (${sourceId}:${line})`);
  });
  mainWindow.webContents.on("context-menu", (_event, params) => {
    const targetWindow = mainWindow;
    Menu.buildFromTemplate([
      {
        label: "复制",
        enabled: Boolean(params.selectionText),
        click: () => targetWindow?.webContents.copy()
      },
      {
        label: "粘贴",
        click: () => targetWindow?.webContents.paste()
      },
      { type: "separator" },
      {
        label: "检查",
        click: () => {
          targetWindow?.webContents.openDevTools({ mode: "detach" });
          targetWindow?.webContents.inspectElement(params.x, params.y);
        }
      }
    ]).popup({ window: targetWindow || undefined });
  });

  if (process.env.ELECTRON_RENDERER_URL) {
    void mainWindow.loadURL(process.env.ELECTRON_RENDERER_URL);
  } else {
    void mainWindow.loadFile(join(__dirname, "../renderer/index.html"));
  }

  mainWindow.on("close", (event) => {
    if (!isQuitting) {
      event.preventDefault();
      mainWindow?.hide();
    }
  });
}

function createTray(): void {
  const image = nativeImage.createEmpty();
  tray = new Tray(image);
  tray.setToolTip("SignSignIn");
  tray.setContextMenu(
    Menu.buildFromTemplate([
      {
        label: "显示窗口",
        click: () => mainWindow?.show()
      },
      {
        label: "退出",
        click: () => {
          isQuitting = true;
          app.quit();
        }
      }
    ])
  );
}

app.whenReady().then(() => {
  registerIpc();
  createWindow();
  createTray();
  codeCaptureService.on("code", (code: string) => {
    for (const win of BrowserWindow.getAllWindows()) {
      if (!win.isDestroyed()) win.webContents.send("code:captured", code);
    }
  });
  logger.info("Electron 主进程已启动");
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
  mainWindow?.show();
});

app.on("before-quit", async () => {
  isQuitting = true;
  await codeCaptureService.stop().catch(() => undefined);
});
