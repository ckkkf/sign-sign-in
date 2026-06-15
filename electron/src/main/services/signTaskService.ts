import type { SignConfig, SignOption, TaskState } from "@shared/types";
import { configStore } from "./configStore";
import { logger } from "./logger";
import { codeCaptureService } from "./codeCaptureService";
import { authStore } from "./authStore";
import { submitClientLog } from "../api/authClient";
import * as xybApi from "../api/xybClient";
import { getDeviceCode } from "./xybToken";

function jitterLocation(input: SignConfig["input"]): void {
  const lon = Number(input.location.longitude);
  const lat = Number(input.location.latitude);
  if (!Number.isFinite(lon) || !Number.isFinite(lat)) {
    return;
  }

  let radius = Number(input.locationJitterMeters ?? 100);
  if (!Number.isFinite(radius)) {
    radius = 100;
  }

  radius = Math.max(0, Math.min(radius, 500));
  if (radius <= 0) {
    logger.info("位置抖动已禁用，使用原始坐标提交签到");
    return;
  }
  const distance = radius * Math.sqrt(Math.random());
  const bearing = Math.random() * 2 * Math.PI;
  const earthRadius = 6378137.0;
  const lat1 = (lat * Math.PI) / 180;
  const lon1 = (lon * Math.PI) / 180;
  const angularDistance = distance / earthRadius;
  const lat2 = Math.asin(
    Math.sin(lat1) * Math.cos(angularDistance) +
      Math.cos(lat1) * Math.sin(angularDistance) * Math.cos(bearing)
  );
  const lon2 =
    lon1 +
    Math.atan2(
      Math.sin(bearing) * Math.sin(angularDistance) * Math.cos(lat1),
      Math.cos(angularDistance) - Math.sin(lat1) * Math.sin(lat2)
    );
  input.location.latitude = ((lat2 * 180) / Math.PI).toFixed(6);
  input.location.longitude = ((lon2 * 180) / Math.PI).toFixed(6);
  logger.info(`已应用位置抖动，半径约 ${Math.round(radius)}m，坐标更新为 ${input.location.longitude}, ${input.location.latitude}`);
}

function buildSafeClientRequestParam(input: SignConfig["input"], option: SignOption | { action: string; code?: string }): string {
  const device = input.device;
  const rawDeviceCode = getDeviceCode(String(input.openId || ""), device);
  const deviceCodeFingerprint = rawDeviceCode
    ? `${rawDeviceCode.slice(0, 10)}...${rawDeviceCode.slice(-8)}`
    : "";

  return JSON.stringify({
    action: option.action,
    code: "code" in option ? option.code || "" : "",
    location: {
      longitude: input.location.longitude,
      latitude: input.location.latitude,
      jitterMeters: input.locationJitterMeters ?? 100
    },
    device: {
      brand: device.brand,
      model: device.model,
      system: device.system,
      platform: device.platform
    },
    risk: {
      deviceName: device.model,
      deviceCodeFingerprint,
      userAgent: input.userAgent,
      hasCode: Boolean(input.code),
      hasOpenId: Boolean(input.openId),
      hasUnionId: Boolean(input.unionId),
      hasImage: Boolean("imagePath" in option && option.imagePath)
    }
  });
}

export class SignTaskService {
  private abortController: AbortController | null = null;
  private activeTask: Promise<void> | null = null;
  private state: TaskState = {
    running: false,
    source: "",
    action: "",
    message: "空闲"
  };

  getState(): TaskState {
    return { ...this.state };
  }

  async start(option: SignOption): Promise<TaskState> {
    if (this.state.running) {
      throw new Error("已有任务正在执行");
    }

    this.abortController = new AbortController();
    this.state = {
      running: true,
      source: "manual",
      action: option.action,
      message: "任务启动",
      startedAt: Date.now()
    };
    this.activeTask = this.run(option, this.abortController.signal).finally(() => {
      this.activeTask = null;
    });
    return this.getState();
  }

  async stop(): Promise<TaskState> {
    this.abortController?.abort();
    this.state.message = "正在停止任务";
    logger.warn("正在停止任务");
    return this.getState();
  }

  async startAuto(option: SignOption): Promise<TaskState> {
    await this.start(option);
    this.state = { ...this.state, source: "auto" };
    await this.waitForIdle();
    return this.getState();
  }

  async waitForIdle(): Promise<TaskState> {
    await this.activeTask?.catch(() => undefined);
    return this.getState();
  }

  async refreshSessionFromCapturedCode(): Promise<TaskState> {
    if (this.state.running) {
      throw new Error("已有任务正在执行");
    }

    this.abortController = new AbortController();
    this.state = {
      running: true,
      source: "manual",
      action: "获取code",
      message: "正在刷新 JSESSIONID",
      startedAt: Date.now()
    };
    this.activeTask = this.runRefreshSession(this.abortController.signal).finally(() => {
      this.activeTask = null;
    });
    return this.getState();
  }

  private checkStop(signal: AbortSignal): void {
    if (signal.aborted) {
      throw new Error("用户停止执行");
    }
  }

  private async run(option: SignOption, signal: AbortSignal): Promise<void> {
    const startTime = Date.now();
    let logInput: SignConfig["input"] | null = null;
    let status = "1";
    let summary = "";
    let errorMsg = "";
    try {
      const config = configStore.read();
      const input = structuredClone(config.input);
      logInput = input;
      jitterLocation(input);
      this.checkStop(signal);

      const capturedCode = codeCaptureService.consumeCode();
      if (capturedCode) {
        input.code = capturedCode;
      }

      const args = await xybApi.login(input, true);
      input.openId = args.openId;
      input.unionId = args.unionId;
      this.checkStop(signal);
      const plan = await xybApi.getPlan(input, args);
      this.checkStop(signal);
      const geo = await xybApi.regeo(input);
      this.checkStop(signal);

      const traineeId = String(plan?.[0]?.dateList?.[0]?.traineeId || args.traineeId || "");
      if (!traineeId) {
        throw new Error("未获取到 traineeId");
      }

      if (option.action === "普通签到签退") {
        const steps = option.steps?.length
          ? option.steps
          : [
              { action: "普通签到", code: "2" },
              { action: "普通签退", code: "1" }
          ];
        for (const step of steps) {
          this.checkStop(signal);
          await xybApi.simpleSignInOrOut(args, input, geo, traineeId, step as SignOption);
        }
      } else if (option.action === "拍照签到" || option.action === "拍照签退") {
        await xybApi.photoSignInOrOut(args, input, geo, traineeId, option);
      } else {
        await xybApi.simpleSignInOrOut(args, input, geo, traineeId, option);
      }

      this.state = {
        running: false,
        source: "",
        action: option.action,
        message: "执行完毕"
      };
      status = "0";
      summary = "执行完毕";
      logger.info("执行完毕");
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      errorMsg = message;
      this.state = {
        running: false,
        source: "",
        action: option.action,
        message
      };
      if (message === "用户停止执行") {
        logger.warn("任务已停止");
      } else {
        logger.error(`任务失败：${message}`);
      }
    } finally {
      if (logInput) {
        await this.reportClientOperLog({
          input: logInput,
          option,
          status,
          title: status === "0" ? `${option.action}成功` : `${option.action}失败`,
          responseSummary: summary || this.state.message,
          errorMsg,
          costTime: Date.now() - startTime
        });
      }
      this.abortController = null;
    }
  }

  private async runRefreshSession(signal: AbortSignal): Promise<void> {
    const startTime = Date.now();
    let logInput: SignConfig["input"] | null = null;
    let status = "1";
    let summary = "";
    let errorMsg = "";
    try {
      const config = configStore.read();
      const input = structuredClone(config.input);
      logInput = input;
      const capturedCode = codeCaptureService.consumeCode();
      if (capturedCode) {
        input.code = capturedCode;
      }
      this.checkStop(signal);
      const args = await xybApi.login(input, false);
      input.openId = args.openId;
      input.unionId = args.unionId;
      this.state = {
        running: false,
        source: "",
        action: "获取code",
        message: "JSESSIONID 已更新"
      };
      status = "0";
      summary = "JSESSIONID 已更新";
      logger.info("JSESSIONID 已更新");
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      errorMsg = message;
      this.state = {
        running: false,
        source: "",
        action: "获取code",
        message
      };
      if (message === "用户停止执行") {
        logger.warn("任务已停止");
      } else {
        logger.error(`获取code失败：${message}`);
      }
    } finally {
      if (logInput) {
        await this.reportClientOperLog({
          input: logInput,
          option: { action: "刷新JSESSIONID" },
          status,
          title: status === "0" ? "刷新JSESSIONID成功" : "刷新JSESSIONID失败",
          responseSummary: summary || this.state.message,
          errorMsg,
          costTime: Date.now() - startTime
        });
      }
      this.abortController = null;
    }
  }

  private async reportClientOperLog(args: {
    input: SignConfig["input"];
    option: SignOption | { action: string; code?: string };
    status: string;
    title: string;
    responseSummary: string;
    errorMsg: string;
    costTime: number;
  }): Promise<void> {
    const cache = authStore.read();
    if (!cache?.token) {
      return;
    }

    const { input, option } = args;
    try {
      const safeParam = buildSafeClientRequestParam(input, option);
      await submitClientLog(
        {
          operType: "XYB_SIGN",
          status: args.status,
          title: args.title,
          requestUrl: "xyb://student/clock",
          requestParam: safeParam,
          responseSummary: args.responseSummary,
          errorMsg: args.errorMsg,
          costTime: args.costTime,
          userAgent: input.userAgent,
          deviceBrand: input.device.brand,
          deviceModel: input.device.model,
          deviceSystem: input.device.system,
          devicePlatform: input.device.platform,
          riskParams: safeParam
        },
        cache.token,
        cache.tokenName
      );
    } catch (error) {
      logger.warn(`上报客户端日志失败：${error instanceof Error ? error.message : String(error)}`);
    }
  }
}

export const signTaskService = new SignTaskService();
