import { Notification } from "electron";
import axios from "axios";
import type { AutoClockNotificationConfig, AutoClockState, SignConfig, SignOption } from "@shared/types";
import { codeCaptureService } from "./codeCaptureService";
import { configStore } from "./configStore";
import { logger } from "./logger";
import { sessionStore } from "./sessionStore";
import { signTaskService } from "./signTaskService";

const MIN_POLL_SECONDS = 10;
const DEFAULT_WAIT_CODE_MS = 5 * 60 * 1000;

type AutoClockTask = {
  time: string;
  mode: string;
  image_path?: string;
  imagePath?: string;
};

function isSessionExpiredMessage(message: string): boolean {
  return /JSESSIONID|Code为空|code为空|code已失效|重新获取|未登录|登录状态/i.test(message);
}

function isValidTask(task: unknown): task is AutoClockTask {
  if (!task || typeof task !== "object") return false;
  const item = task as Partial<AutoClockTask>;
  return /^\d{1,2}:\d{2}$/.test(String(item.time || "")) && Boolean(String(item.mode || "").trim());
}

function normalizeTasks(config: SignConfig): AutoClockTask[] {
  const rawTasks = config.settings?.auto_clock?.tasks || [];
  if (!Array.isArray(rawTasks)) return [];
  return rawTasks.filter(isValidTask).map((task) => ({
    time: task.time,
    mode: String(task.mode).trim().toLowerCase(),
    image_path: task.image_path || task.imagePath
  }));
}

function modeToOption(task: AutoClockTask): SignOption {
  const map: Record<string, SignOption> = {
    in: { action: "普通签到", code: "2" },
    out: { action: "普通签退", code: "1" },
    photo_in: { action: "拍照签到", code: "2" },
    photo_out: { action: "拍照签退", code: "1" }
  };
  const option = map[task.mode];
  if (!option) {
    throw new Error(`不支持的定时打卡模式: ${task.mode}`);
  }
  if (task.mode === "photo_in" || task.mode === "photo_out") {
    const imagePath = task.image_path || task.imagePath || "";
    if (!imagePath) {
      throw new Error(`${task.mode} 需要 image_path`);
    }
    return { ...option, imagePath };
  }
  return { ...option };
}

function taskKey(index: number, task: AutoClockTask): string {
  return `${index}:${task.mode}:${task.time}`;
}

function clampRandomMinutes(value: unknown): number {
  const minutes = Number(value || 0);
  if (!Number.isFinite(minutes)) return 0;
  return Math.max(0, Math.min(120, Math.floor(minutes)));
}

function addDays(day: Date, days: number): Date {
  return new Date(day.getFullYear(), day.getMonth(), day.getDate() + days, day.getHours(), day.getMinutes(), 0, 0);
}

function computeRandomizedTaskDate(day: Date, taskTime: string, randomMinutes: number): Date {
  const [hourText, minuteText] = taskTime.split(":");
  const baseMinutes = Number(hourText) * 60 + Number(minuteText);
  const offset = randomMinutes > 0 ? Math.floor(Math.random() * (randomMinutes * 2 + 1)) - randomMinutes : 0;
  const finalMinutes = Math.max(0, Math.min(23 * 60 + 59, baseMinutes + offset));
  return new Date(day.getFullYear(), day.getMonth(), day.getDate(), Math.floor(finalMinutes / 60), finalMinutes % 60, 0, 0);
}

function computeNextTrigger(now: Date, task: AutoClockTask, randomMinutes: number): Date {
  const todayRun = computeRandomizedTaskDate(now, task.time, randomMinutes);
  if (todayRun > now) return todayRun;
  return computeRandomizedTaskDate(addDays(now, 1), task.time, randomMinutes);
}

export class AutoClockService {
  private timer: NodeJS.Timeout | null = null;
  private nextTriggerByTask = new Map<string, Date>();
  private tasks: AutoClockTask[] = [];
  private randomMinutes = 0;
  private pollSeconds = 30;
  private state: AutoClockState = {
    enabled: false,
    running: false,
    message: "未启动"
  };

  getState(): AutoClockState {
    const config = configStore.read();
    return {
      ...this.state,
      enabled: Boolean(config.settings?.auto_clock?.enabled),
      taskCount: normalizeTasks(config).length
    };
  }

  start(): AutoClockState {
    const config = configStore.read();
    config.settings = {
      ...config.settings,
      auto_clock: {
        ...config.settings?.auto_clock,
        enabled: true
      }
    };
    configStore.write(config);
    this.reloadFromConfig();
    logger.info("定时打卡已启动");
    return this.getState();
  }

  stop(): AutoClockState {
    const config = configStore.read();
    config.settings = {
      ...config.settings,
      auto_clock: {
        ...config.settings?.auto_clock,
        enabled: false
      }
    };
    configStore.write(config);
    this.clearTimer();
    this.nextTriggerByTask.clear();
    this.tasks = [];
    this.state = {
      enabled: false,
      running: false,
      message: "已停止"
    };
    logger.warn("定时打卡已停止");
    return this.getState();
  }

  reload(): AutoClockState {
    this.reloadFromConfig();
    return this.getState();
  }

  async testNotification(channel: AutoClockNotificationConfig): Promise<boolean> {
    const type = String(channel.type || "").trim().toLowerCase();
    if (type === "tray") {
      this.notifyTray("定时打卡测试", "系统通知渠道可用");
      return true;
    }
    if (type === "pushplus") {
      const token = String(channel.token || "").trim();
      if (!token) throw new Error("PushPlus 通知必须填写 Token");
      await this.notifyPushPlus(token, "定时打卡测试", `测试时间: ${formatDateTime(new Date())}\n消息: PushPlus 通知渠道可用`);
      return true;
    }
    throw new Error(`不支持的通知方式: ${type || "空"}`);
  }

  shutdown(): void {
    this.clearTimer();
    this.state = { ...this.state, running: false };
  }

  private reloadFromConfig(): void {
    this.clearTimer();
    const config = configStore.read();
    const autoClock = config.settings?.auto_clock;
    if (!autoClock?.enabled) {
      this.state = { ...this.state, enabled: false, running: false, message: "未启动", nextRunAt: undefined };
      return;
    }

    this.tasks = normalizeTasks(config);
    this.pollSeconds = Math.max(MIN_POLL_SECONDS, Number(autoClock.poll_seconds || 30));
    this.randomMinutes = clampRandomMinutes(autoClock.random_minutes);
    this.nextTriggerByTask.clear();

    if (!this.tasks.length) {
      this.state = {
        enabled: true,
        running: false,
        message: "没有定时任务，请先在配置中添加任务",
        taskCount: 0
      };
      logger.warn("定时打卡已启用，但 settings.auto_clock.tasks 为空");
      return;
    }

    const now = new Date();
    for (const [index, task] of this.tasks.entries()) {
      const next = computeNextTrigger(now, task, this.randomMinutes);
      this.nextTriggerByTask.set(taskKey(index, task), next);
      logger.info(
        `Auto-clock task[${index + 1}] mode=${task.mode} base=${task.time} random=+/-${this.randomMinutes}m next=${formatDateTime(next)}`
      );
    }
    this.scheduleTick();
  }

  private scheduleTick(): void {
    this.clearTimer();
    const nextRunAt = this.findNearestTrigger()?.getTime();
    this.state = {
      ...this.state,
      enabled: true,
      running: false,
      message: nextRunAt ? `下次执行 ${formatDateTime(new Date(nextRunAt))}` : "没有可执行任务",
      nextRunAt,
      taskCount: this.tasks.length
    };
    this.timer = setTimeout(() => void this.tick(), this.pollSeconds * 1000);
  }

  private async tick(): Promise<void> {
    const config = configStore.read();
    if (!config.settings?.auto_clock?.enabled) {
      this.state = { ...this.state, enabled: false, running: false, message: "未启动", nextRunAt: undefined };
      return;
    }
    if (!this.tasks.length) {
      this.reloadFromConfig();
      return;
    }
    if (this.state.running) {
      this.scheduleTick();
      return;
    }

    const now = new Date();
    for (const [index, task] of this.tasks.entries()) {
      const key = taskKey(index, task);
      let next = this.nextTriggerByTask.get(key);
      if (!next) {
        next = computeNextTrigger(now, task, this.randomMinutes);
        this.nextTriggerByTask.set(key, next);
      }
      if (now < next) continue;

      await this.runTask(index, task, now);
      break;
    }
    this.scheduleTick();
  }

  private async runTask(index: number, task: AutoClockTask, now: Date): Promise<void> {
    let option: SignOption;
    try {
      option = modeToOption(task);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      logger.warn(`Auto-clock config error, skipped this task: ${message}`);
      this.rescheduleTask(index, task, now);
      return;
    }

    this.state = {
      ...this.state,
      enabled: true,
      running: true,
      message: `正在执行定时打卡: ${option.action}`,
      lastRunAt: Date.now()
    };

    try {
      if (!sessionStore.read()) {
        logger.info("定时打卡: session 已过期，自动触发获取 code 流程...");
        await this.refreshSessionFromCapturedCode();
      }
      await this.runSignWithRecovery(option);
      this.state = { ...this.state, running: false, message: "定时打卡执行完成" };
      await this.notifyResult(true, "定时打卡执行完成", option.action);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      this.state = { ...this.state, running: false, message };
      logger.error(`定时打卡失败：${message}`);
      await this.notifyResult(false, message, option.action);
    } finally {
      this.rescheduleTask(index, task, now);
    }
  }

  private rescheduleTask(index: number, task: AutoClockTask, now: Date): void {
    const tomorrow = addDays(now, 1);
    const next = computeRandomizedTaskDate(tomorrow, task.time, this.randomMinutes);
    this.nextTriggerByTask.set(taskKey(index, task), next);
    logger.info(
      `Auto-clock task[${index + 1}] mode=${task.mode} base=${task.time} random=+/-${this.randomMinutes}m next=${formatDateTime(next)}`
    );
  }

  private async runSignWithRecovery(option: SignOption): Promise<void> {
    let result = await signTaskService.startAuto(option);
    if (!isSessionExpiredMessage(result.message)) {
      return;
    }
    logger.warn("定时打卡检测到登录态失效，准备自动抓包续期");
    sessionStore.clear();
    await this.refreshSessionFromCapturedCode();
    result = await signTaskService.startAuto(option);
    if (isSessionExpiredMessage(result.message)) {
      throw new Error(result.message);
    }
  }

  private async refreshSessionFromCapturedCode(): Promise<void> {
    codeCaptureService.setManualCode("");
    const codePromise = this.waitForCapturedCode(DEFAULT_WAIT_CODE_MS);
    await codeCaptureService.start();
    const code = await codePromise;
    codeCaptureService.setManualCode(code);
    await signTaskService.refreshSessionFromCapturedCode();
    const result = await signTaskService.waitForIdle();
    if (isSessionExpiredMessage(result.message)) {
      throw new Error(result.message);
    }
  }

  private async notifyResult(success: boolean, message: string, action: string): Promise<void> {
    const config = configStore.read();
    const settings = config.settings || {};
    if (!settings.notifications_enabled) return;

    const title = `打卡${success ? "成功" : "失败"}`;
    const content = `定时任务: ${action}\n时间: ${formatDateTime(new Date())}\n消息: ${message || title}`;
    const channels = normalizeNotificationChannels(settings.notifications, settings.pushplus?.token);

    for (const channel of channels) {
      if (channel.type === "tray") {
        this.notifyTray(title, message || title);
      } else if (channel.type === "pushplus" && channel.token) {
        await this.notifyPushPlus(channel.token, title, content);
      }
    }
  }

  private notifyTray(title: string, body: string): void {
    if (!Notification.isSupported()) return;
    new Notification({ title, body }).show();
  }

  private async notifyPushPlus(token: string, title: string, content: string): Promise<void> {
    try {
      await axios.post(
        "http://www.pushplus.plus/send",
        { token, title, content },
        { timeout: 15000, headers: { "Content-Type": "application/json" } }
      );
      logger.info("PushPlus 推送成功");
    } catch (error) {
      logger.warn(`PushPlus 推送失败：${error instanceof Error ? error.message : String(error)}`);
    }
  }

  private findNearestTrigger(): Date | undefined {
    return Array.from(this.nextTriggerByTask.values()).sort((a, b) => a.getTime() - b.getTime())[0];
  }

  private clearTimer(): void {
    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = null;
    }
  }

  private waitForCapturedCode(timeoutMs: number): Promise<string> {
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        cleanup();
        reject(new Error("自动抓包续期超时，请确认微信小程序已打开并重新触发登录"));
      }, timeoutMs);
      const onCode = (code: string) => {
        cleanup();
        resolve(code);
      };
      const cleanup = () => {
        clearTimeout(timer);
        codeCaptureService.off("code", onCode);
      };
      codeCaptureService.on("code", onCode);
    });
  }
}

function normalizeNotificationChannels(
  rawChannels: unknown,
  legacyPushPlusToken?: string
): Array<AutoClockNotificationConfig & { type: "pushplus" | "tray" }> {
  const channels: Array<AutoClockNotificationConfig & { type: "pushplus" | "tray" }> = [];
  const seen = new Set<string>();

  if (Array.isArray(rawChannels)) {
    for (const channel of rawChannels) {
      if (!channel || typeof channel !== "object") continue;
      const item = channel as AutoClockNotificationConfig;
      const type = String(item.type || "").trim().toLowerCase();
      const token = String(item.token || "").trim();
      if ((type !== "pushplus" && type !== "tray") || seen.has(type)) continue;
      if (type === "pushplus" && !token) continue;
      seen.add(type);
      channels.push({ type, token });
    }
  }

  const token = String(legacyPushPlusToken || "").trim();
  if (token && !seen.has("pushplus")) {
    channels.push({ type: "pushplus", token });
  }

  return channels;
}

function formatDateTime(date: Date): string {
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export const autoClockService = new AutoClockService();
