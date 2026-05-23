import { UA_TEMPLATE } from "./constants";
import type { SignConfig } from "./types";

export function buildUserAgent(device: SignConfig["input"]["device"]): string {
  return UA_TEMPLATE.replace("{system}", device.system)
    .replace("{model}", device.model)
    .replace("{platform}", String(device.platform || "android").toLowerCase());
}

export function validateConfig(config: SignConfig): string | null {
  if (!config.input || typeof config.input !== "object") return "配置格式不完整：缺少 input";
  const { location, device, userAgent } = config.input;
  if (!location) return "缺少位置信息";
  const lng = Number(location.longitude);
  const lat = Number(location.latitude);
  if (!Number.isFinite(lng) || !Number.isFinite(lat)) return "经纬度格式错误：只能填写数字";
  if (lng < -180 || lng > 180) return "经度超出范围：应在 -180 到 180 之间";
  if (lat < -90 || lat > 90) return "纬度超出范围：应在 -90 到 90 之间";

  const jitter = config.input.locationJitterMeters;
  if (jitter !== undefined && jitter !== "") {
    const value = Number(jitter);
    if (!Number.isFinite(value)) return "位置抖动半径格式错误：只能填写数字";
    if (value < 0 || value > 500) return "位置抖动半径超出范围：应在 0 到 500 米之间";
  }

  if (!device?.brand || !device?.model || !device?.system || !device?.platform) {
    return "设备信息不完整：请填写品牌、型号、系统、平台";
  }
  if (!userAgent) return "User-Agent 为空，请生成后保存";
  if (!userAgent.includes(device.model)) return `设备型号与UA不一致：UA中缺少“${device.model}”`;
  if (!userAgent.includes(`MiniProgramEnv/${String(device.platform).toLowerCase()}`)) {
    return `设备平台与UA不一致：UA中缺少“MiniProgramEnv/${String(device.platform).toLowerCase()}”`;
  }
  return null;
}
