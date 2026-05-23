import type { CaptureState } from "@shared/types";
import { XYB_APP_ID } from "@shared/constants";
import { logger } from "./logger";
import { wakeApplet } from "./systemService";

type FridaModule = typeof import("frida");
type FridaSession = Awaited<ReturnType<Awaited<ReturnType<FridaModule["getLocalDevice"]>>["attach"]>>;
type FridaScript = Awaited<ReturnType<FridaSession["createScript"]>>;

type HookMessage = {
  type: string;
  payload?: unknown;
};

type FridaTarget = {
  pid: number;
  name: string;
};

const probeScript = `
const interesting = [
  "WeixinJSBridge",
  "wx.login",
  "login",
  "getOpenId.action",
  "xcx.xybsyw.com",
  "servicewechat.com"
];

function safeSend(type, payload) {
  send({ type, payload });
}

function scanLoadedModules() {
  const modules = Process.enumerateModules();
  safeSend("modules", modules
    .filter(m => /WeChat|Weixin|XWeb|v8|JavaScriptCore|Mini|App/i.test(m.name))
    .slice(0, 80)
    .map(m => ({ name: m.name, base: String(m.base), size: m.size })));
}

function scanReadableStrings() {
  for (const mod of Process.enumerateModules()) {
    if (!/WeChat|Weixin|XWeb|v8|JavaScriptCore|Mini|App/i.test(mod.name)) continue;
    for (const text of interesting) {
      try {
        const hits = Memory.scanSync(mod.base, mod.size, text);
        if (hits.length) safeSend("string-hit", { module: mod.name, text, count: hits.length, first: String(hits[0].address) });
      } catch (_) {
      }
    }
  }
}

function scanSymbols() {
  const patterns = [
    /WeixinJSBridge/i,
    /JSBridge/i,
    /invoke/i,
    /login/i,
    /getOpenId/i,
    /Network/i,
    /Request/i
  ];
  for (const mod of Process.enumerateModules()) {
    if (!/WeChat|Weixin|XWeb|v8|JavaScriptCore|Mini|App/i.test(mod.name)) continue;
    try {
      const symbols = Module.enumerateSymbols(mod.name)
        .filter(s => patterns.some(p => p.test(s.name)))
        .slice(0, 120)
        .map(s => ({ module: mod.name, name: s.name, address: String(s.address), type: s.type }));
      if (symbols.length) safeSend("symbol-hit", symbols);
    } catch (_) {
    }
    try {
      const exports = Module.enumerateExports(mod.name)
        .filter(e => patterns.some(p => p.test(e.name)))
        .slice(0, 80)
        .map(e => ({ module: mod.name, name: e.name, address: String(e.address), type: e.type }));
      if (exports.length) safeSend("export-hit", exports);
    } catch (_) {
    }
  }
}

function scanObjC() {
  if (typeof ObjC === "undefined" || !ObjC.available) return;
  const patterns = [/Bridge/i, /JS/i, /Login/i, /Network/i, /Request/i, /Mini/i, /AppEx/i];
  const hits = [];
  for (const className in ObjC.classes) {
    if (!patterns.some(p => p.test(className))) continue;
    try {
      const klass = ObjC.classes[className];
      const methods = klass.$ownMethods
        .filter(m => patterns.some(p => p.test(m)))
        .slice(0, 30);
      hits.push({ className, methods });
    } catch (_) {
      hits.push({ className, methods: [] });
    }
    if (hits.length >= 160) break;
  }
  if (hits.length) safeSend("objc-hit", hits);
}

scanLoadedModules();
scanReadableStrings();
scanSymbols();
scanObjC();
safeSend("ready", { appid: "${XYB_APP_ID}", pid: Process.id, arch: Process.arch, platform: Process.platform });
`;

export class FridaHookService {
  private frida: FridaModule | null = null;
  private session: FridaSession | null = null;
  private script: FridaScript | null = null;
  private running = false;
  private lastCode = "";
  private message = "未启动";

  getState(): CaptureState {
    return {
      running: this.running,
      host: "frida",
      port: 0,
      lastCode: this.lastCode,
      message: this.message
    };
  }

  async start(): Promise<CaptureState> {
    if (this.running) return this.getState();
    this.frida = await this.loadFrida();
    const targets = await this.findTargetProcesses(this.frida);
    const { target, session } = await this.attachFirstAvailable(this.frida, targets);
    this.session = session;
    this.session.detached.connect((reason) => {
      this.running = false;
      this.message = `Frida 已断开: ${reason}`;
      logger.warn(this.message);
    });
    this.script = await this.session.createScript(probeScript);
    this.script.message.connect((message: HookMessage, data: Buffer | null) => this.handleMessage(message, data));
    await this.script.load();
    this.running = true;
    this.message = `Frida Hook 已挂载: ${target.name}(${target.pid})`;
    logger.info(this.message);
    await wakeApplet(XYB_APP_ID).catch((error) => {
      logger.warn(`唤醒微信小程序失败：${error instanceof Error ? error.message : String(error)}`);
    });
    return this.getState();
  }

  async stop(): Promise<CaptureState> {
    const script = this.script;
    const session = this.session;
    this.script = null;
    this.session = null;
    this.running = false;
    if (script) await script.unload().catch(() => undefined);
    if (session) await session.detach().catch(() => undefined);
    this.message = "Frida Hook 已停止";
    logger.info(this.message);
    return this.getState();
  }

  setManualCode(code: string): CaptureState {
    this.lastCode = code.trim();
    this.message = this.lastCode ? "已手动写入 code" : "已清空 code";
    logger.info(this.message);
    return this.getState();
  }

  consumeCode(): string {
    return this.lastCode;
  }

  private async loadFrida(): Promise<FridaModule> {
    try {
      return await import("frida");
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      throw new Error(`frida-node 尚不可用：${message}`);
    }
  }

  private async findTargetProcesses(frida: FridaModule): Promise<FridaTarget[]> {
    const device = await frida.getLocalDevice();
    const processes = await device.enumerateProcesses();
    const candidates = processes.filter((process) => /WeChatAppEx|WeixinAppEx|WeChat|微信/i.test(process.name));
    if (candidates.length) {
      logger.info(`Frida 微信候选进程: ${candidates.map((process) => `${process.name}(${process.pid})`).join(", ")}`);
    }
    const ordered: FridaTarget[] = [];
    for (const pattern of [/WeChatAppEx Helper \(Renderer\)/i, /WeixinAppEx Helper \(Renderer\)/i]) {
      for (const process of candidates) {
        if (!pattern.test(process.name)) continue;
        if (ordered.some((target) => target.pid === process.pid)) continue;
        ordered.push({ pid: process.pid, name: process.name });
      }
    }
    if (ordered.length) return ordered;
    logger.info(`Frida 进程枚举: ${processes.slice(0, 40).map((process) => `${process.name}(${process.pid})`).join(", ")}`);
    throw new Error("未找到微信小程序 Renderer 进程，请先打开微信并进入校友邦小程序");
  }

  private async attachFirstAvailable(frida: FridaModule, targets: FridaTarget[]): Promise<{ target: FridaTarget; session: FridaSession }> {
    const errors: string[] = [];
    for (const target of targets) {
      try {
        logger.info(`Frida 尝试挂载: ${target.name}(${target.pid})`);
        const session = await frida.attach(target.pid);
        return { target, session };
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        errors.push(`${target.name}(${target.pid}): ${message}`);
        logger.warn(`Frida 挂载失败: ${target.name}(${target.pid}) ${message}`);
      }
    }
    throw new Error(
      `Frida 已找到微信小程序 Renderer，但当前 Electron 无法 attach。已尝试 ${targets.length} 个 Renderer 均失败。主进程不再作为兜底，因为 wx.login/WeixinJSBridge 不在主进程里。macOS 版微信启用了 Hardened Runtime/Renderer 沙箱，授权“开发者工具/辅助功能/完全磁盘访问”或 sudo 后仍可能被系统拒绝；只要这里还是 Unable to access process，就还没有进入 JS Hook 阶段。建议改用 mitmproxy/本地缓存/IPC 方向继续获取 code。失败详情：${errors.join(" | ")}`
    );
  }

  private handleMessage(message: HookMessage, _data: Buffer | null): void {
    if (message.type === "send") {
      const payload = message.payload as { type?: string; payload?: unknown };
      if (payload.type === "ready") {
        logger.info(`Frida 探测脚本已加载: ${JSON.stringify(payload.payload)}`);
      } else if (payload.type === "modules") {
        logger.info(`Frida 模块候选: ${JSON.stringify(payload.payload)}`);
      } else if (payload.type === "string-hit") {
        logger.info(`Frida 字符串命中: ${JSON.stringify(payload.payload)}`);
      } else if (payload.type === "symbol-hit") {
        logger.info(`Frida 符号命中: ${JSON.stringify(payload.payload)}`);
      } else if (payload.type === "export-hit") {
        logger.info(`Frida 导出命中: ${JSON.stringify(payload.payload)}`);
      } else if (payload.type === "objc-hit") {
        logger.info(`Frida ObjC 命中: ${JSON.stringify(payload.payload)}`);
      } else if (payload.type === "code") {
        const code = String((payload.payload as { code?: string })?.code || "").trim();
        if (code) {
          this.lastCode = code;
          this.message = "Frida 已捕获小程序 code";
          logger.info(`Frida 已捕获小程序 code: ${code}`);
        }
      } else {
        logger.debug(`Frida 消息: ${JSON.stringify(payload)}`);
      }
      return;
    }
    if (message.type === "error") {
      logger.error(`Frida 脚本错误: ${JSON.stringify(message)}`);
    }
  }
}

export const fridaHookService = new FridaHookService();
