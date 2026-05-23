import crypto from "node:crypto";
import { sm2 } from "sm-crypto";
import {
  XYB_APP_ID,
  XYB_EXCLUDED_KEYS,
  XYB_KEY,
  XYB_N_HEADER,
  XYB_SM2_MODE,
  XYB_SM2_PUBLIC_KEY
} from "@shared/constants";
import type { HeaderToken, SignConfig } from "@shared/types";

const specialCharRegex = /[`~!@#$%^&*()+=|{}':;',[\].<>/?~！@#￥%……&*（）——+|{}【】‘；：”“’。，、？]/;

function normalizeValue(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  if (Array.isArray(value) || typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

function randStr(length = 16): string {
  const chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
  let out = "";
  for (let i = 0; i < length; i += 1) {
    out += chars[Math.floor(Math.random() * chars.length)];
  }
  return out;
}

export function getHeaderToken(data: Record<string, unknown>): HeaderToken {
  const indexes = Array.from({ length: 62 }, (_, index) => String(index));
  const shuffled = [...indexes].sort(() => Math.random() - 0.5).slice(0, 20);
  const randomKey = shuffled.map((index) => XYB_KEY[Number(index)]).join("");
  const timestamp = Math.floor(Date.now() / 1000);
  const sorted = Object.keys(data).sort();

  let raw = "";
  for (const key of sorted) {
    const valueText = normalizeValue(data[key]);
    if (!XYB_EXCLUDED_KEYS.includes(key) && !specialCharRegex.test(valueText)) {
      raw += valueText;
    }
  }

  raw = `${raw}${timestamp}${randomKey}`
    .replace(/\s+/g, "")
    .replace(/\n+/g, "")
    .replace(/\r+/g, "")
    .replace(/</g, "")
    .replace(/>/g, "")
    .replace(/&/g, "")
    .replace(/-/g, "")
    .replace(/[\uD83C][\uDF00-\uDFFF]|[\uD83D][\uDC00-\uDE4F]/g, "");

  return {
    m: crypto.createHash("md5").update(encodeURIComponent(raw), "utf-8").digest("hex"),
    t: String(timestamp),
    s: shuffled.join("_"),
    n: XYB_N_HEADER
  };
}

export function getDeviceCode(openId: string, device: SignConfig["input"]["device"]): string {
  const payload =
    `b|_${device.brand},${device.model},${device.system},${device.platform}` +
    `aid|_${XYB_APP_ID}` +
    `t|_${Date.now()}` +
    `uid|_${randStr()}` +
    `oid|_${openId || ""}`;
  return sm2.doEncrypt(payload, XYB_SM2_PUBLIC_KEY, XYB_SM2_MODE);
}
