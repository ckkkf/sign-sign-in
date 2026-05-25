import axios, { type AxiosResponse } from "axios";
import FormData from "form-data";
import { createReadStream } from "node:fs";
import type { JieLongQrLogin, JieLongQrState, JieLongSubmitPayload } from "@shared/types";
import { parseQrPoll, parseQrUuid } from "@shared/jielongCore";
import { logger } from "../services/logger";
import { http } from "./httpClient";
import type { JieLongApiData } from "./types/jielongTypes";

/** 将任意响应字段转成可读文本。 */
function firstText(value: unknown): string {
  if (value === null || value === undefined) {
    return "";
  }

  if (typeof value === "string") {
    return value.trim();
  }

  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }

  if (Array.isArray(value)) {
    return value.map((item) => String(item).trim()).filter(Boolean).join(" / ");
  }

  return String(value).trim();
}

/** 从接龙接口响应中提取可读错误信息。 */
export function extractApiMessage(data: unknown): string {
  if (!data || typeof data !== "object") {
    return String(data || "").trim();
  }

  const body = data as Record<string, any>;

  // 优先读取顶层错误字段。
  for (const key of ["Description", "description", "Msg", "msg", "Message", "message", "error"]) {
    const message = firstText(body[key]);
    if (message) {
      return message;
    }
  }

  const nested = body.Data ?? body.data;

  // 部分接口会把错误信息放在 Data 内。
  if (nested && typeof nested === "object") {
    for (const key of ["Description", "description", "Msg", "msg", "Message", "message", "error"]) {
      const message = firstText((nested as Record<string, any>)[key]);
      if (message) {
        return message;
      }
    }
  }

  return firstText(nested);
}

/** 判断错误是否像接龙 Token 失效。 */
export function looksLikeInvalidJieLongToken(message: string): boolean {
  const text = String(message || "");
  const lower = text.toLowerCase();
  return (
    ["未登录", "请先登录", "登录", "授权验证失败"].some((item) => text.includes(item)) ||
    ["token", "authorization", "bearer"].some((item) => lower.includes(item))
  );
}

/** 规范化接龙接口返回的错误文案。 */
function normalizeApiError(message: string): string {
  const text = String(message || "").trim();

  if (looksLikeInvalidJieLongToken(text)) {
    return `${text}；当前 Token 可能无效、已过期，或不是该接龙可用的 Token`;
  }

  return text;
}

/** 规范化接龙 Bearer Token。 */
function normalizeAuthorization(token: string): string {
  const value = String(token || "").trim();

  if (!value) {
    throw new Error("请先填写接龙 Bearer Token");
  }

  return value.toLowerCase().startsWith("bearer ") ? value : `Bearer ${value}`;
}

/** 组装接龙小程序接口通用请求头。 */
function requestHeaders(
  token: string,
  requestPayload: string,
  referer: string,
  requestReferer: string,
  userAgent: string
): Record<string, string> {
  return {
    accept: "*/*",
    "accept-language": "zh-CN,zh;q=0.9",
    authorization: normalizeAuthorization(token),
    "cache-control": "no-cache",
    "content-type": "application/json",
    platform: "wx_bak",
    pragma: "no-cache",
    referer,
    "user-agent": userAgent,
    "x-api-request-mode": "cors",
    "x-api-request-payload": requestPayload,
    "x-api-request-referer": requestReferer,
    xweb_xhr: "1"
  };
}

/** 校验接龙业务响应是否成功。 */
function expectSuccess(response: AxiosResponse, fallback: string): JieLongApiData {
  const data = response.data as JieLongApiData;

  if (data?.Type !== "000001") {
    throw new Error(normalizeApiError(extractApiMessage(data) || fallback));
  }

  return data;
}

/** 下载二维码图片并转为 renderer 可直接展示的 data URL。 */
async function downloadQrImage(qrcodeUrl: string): Promise<string> {
  // 二维码图片走二进制下载。
  const response = await http.get<ArrayBuffer>(qrcodeUrl, {
    responseType: "arraybuffer",
    validateStatus: () => true
  });

  const contentType = String(response.headers["content-type"] || "image/jpeg");
  return `data:${contentType};base64,${Buffer.from(response.data).toString("base64")}`;
}

/** 创建微信扫码登录二维码。 */
export async function createQrLogin(): Promise<JieLongQrLogin> {
  const url = "https://open.weixin.qq.com/connect/qrconnect";
  const qrcodeUrlTemplate = "https://open.weixin.qq.com/connect/qrcode/{uuid}";
  const appId = "wx4a23ae4b8f291087";
  const redirectUri = "https://i.jielong.com/login-callback";
  const styleHref =
    "data:text/css;base64,Ci5pbXBvd2VyQm94IC5xcmNvZGUgewogIHdpZHRoOiAzMDBweDsKICBib3JkZXI6IG5vbmU7Cn0K" +
    "LmltcG93ZXJCb3ggLnRpdGxlIHsKICBkaXNwbGF5OiBub25lOwp9Ci5pbXBvd2VyQm94IC5pbmZvIHsKICBkaXNwbGF5" +
    "OiBub25lOwp9Ci5pbXBvd2VyQm94IC5xcmNvZGUgewogIG1hcmdpbi10b3A6IDBweCAhaW1wb3J0YW50Owp9Ci5zdGF0" +
    "dXNfaWNvbiB7CiAgZGlzcGxheTogbm9uZTsKfQouanNfcXVpY2tfbG9naW4gewogIG1hcmdpbi10b3A6IDUwcHg7Cn0=";
  const userAgent =
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
    "(KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36";
  const nowMs = Date.now();

  // 请求微信二维码登录页，响应中包含 uuid。
  const response = await http.get(url, {
    headers: {
      accept: "application/xml, text/xml, */*; q=0.01",
      referer: `${url}?appid=${appId}&scope=snsapi_login&redirect_uri=${redirectUri}`,
      "user-agent": userAgent,
      "x-requested-with": "XMLHttpRequest"
    },
    params: {
      appid: appId,
      scope: "snsapi_login",
      redirect_uri: redirectUri,
      state: "",
      login_type: "jssdk",
      self_redirect: "true",
      style: "black",
      href: styleHref,
      f: "xml",
      _: nowMs,
      ts: nowMs
    }
  });

  // 根据 uuid 再下载二维码图片。
  const uuid = parseQrUuid(String(response.data || ""));
  const qrcodeUrl = qrcodeUrlTemplate.replace("{uuid}", uuid);
  const image = await downloadQrImage(qrcodeUrl);
  return { uuid, qrcodeUrl, image };
}

/** 轮询微信扫码登录状态。 */
export async function pollQrLogin(uuid: string): Promise<JieLongQrState> {
  try {
    const url = "https://lp.open.weixin.qq.com/connect/l/qrconnect";
    const userAgent =
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
      "(KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36";

    // 微信长轮询接口会返回 window.wx_errcode。
    const response = await http.get(url, {
      timeout: 12000,
      headers: {
        accept: "*/*",
        referer: "https://open.weixin.qq.com/",
        "user-agent": userAgent
      },
      params: {
        uuid: String(uuid || "").trim(),
        _: Date.now()
      }
    });
    return parseQrPoll(String(response.data || ""));
  } catch (error) {
    if (axios.isAxiosError(error) && error.code === "ECONNABORTED") {
      return { status: "timeout", wxErrcode: "", code: "", message: "微信轮询超时", raw: "" };
    }

    throw error;
  }
}

/** 使用微信扫码确认后的 code 换取接龙 Token。 */
export async function exchangeQrToken(code: string): Promise<JieLongApiData> {
  const loginCode = String(code || "").trim();

  if (!loginCode) {
    throw new Error("未获取到接龙登录 code");
  }

  const url = "https://i-api.jielong.com/api/User/OpenAuth";
  const requestPayload =
    "par0NCtm+oBuEkBOI+w465ziSpJ1q2mHTwrJUpSxsfAX1QxuVPVW2/9V4YvOWp6AQlKmpxnUrPCFYO0fx0CgXQ4Z" +
    "EIEYYAPCsJhmBtt7bkXykLpl6C2P/mlQmYWuYhs6JwqmgnsXGYfJGorQSmikaKm6Bz5zAhwLgxbKzVz8gWO887Hh" +
    "dLmrG1GoYU1uBil8oBCAaUviVwIY5orn4jkb6aKE/En/cwBqyfeZMCF3BcBTzMLzfWeoi1JfOL7GNHeTp/DcIPrqr0x" +
    "9vs1bY0KMiA==";
  const userAgent =
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
    "(KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36";

  logger.info(`[JieLong] POST ${url}`);

  // 使用微信确认后的 code 换取接龙 Token。
  const response = await http.post(url, undefined, {
    headers: {
      accept: "application/json, text/plain, */*",
      authorization: "undefined",
      "content-length": "0",
      "content-type": "application/x-www-form-urlencoded",
      origin: "https://i.jielong.com",
      platform: "pc",
      referer: "https://i.jielong.com/",
      "user-agent": userAgent,
      "x-api-request-mode": "cors",
      "x-api-request-payload": requestPayload
    },
    params: { code: loginCode }
  });
  return expectSuccess(response, "接龙登录失败").Data || {};
}

/** 解析接龙分享链接中的 threadId。 */
export async function parseShareUrl(shareUrl: string): Promise<string> {
  const url = String(shareUrl || "").trim();

  if (!url) {
    throw new Error("请先粘贴接龙分享链接");
  }

  if (!url.toLowerCase().startsWith("http://") && !url.toLowerCase().startsWith("https://")) {
    throw new Error("请先粘贴有效的接龙分享链接");
  }

  logger.info(`[JieLong] GET ${url}`);

  // 接龙分享链接通过 302 跳转暴露 threadId。
  const response = await http.get(url, { maxRedirects: 0, validateStatus: () => true });
  const location = String(response.headers.location || "").trim();

  if (!location) {
    throw new Error("分享链接解析失败：未拿到跳转地址");
  }

  const threadId = location.replace(/\/+$/, "").split("/").pop()?.split("?")[0]?.trim() || "";

  if (!threadId) {
    throw new Error("分享链接解析失败：未拿到 thread_id");
  }

  return threadId;
}

/** 获取接龙详情，返回 Thread 和 CheckIn 基础信息。 */
export async function fetchDetail(token: string, threadId: string): Promise<JieLongApiData> {
  const url = "https://api.jielong.com/api/CheckIn/Detail";
  const requestPayload =
    "par0NCtm+oBuEkBOI+w464RegjsQ/qtwdXVV59qer75djTR6N2ImzP+0o0k9HhhQAAGiVmy9pb6iRb6XwvCi1f/ogbSz1XGrZvZ3RntW9rfGpQ5fNPzKU2TY1k3f+Gfc7R8PtqkDQfAI+NorxafDCs400l35i7y2ABvUjZ0RA4fOqVK9BTq1AS8CqkOyQpji50o46SrH+xt0D9y8VnXEJFMay0LOWtyYSiKyQiVI/UkRIn8WWE0xNIXzaTW3EKzH";
  const referer = "https://servicewechat.com/wx8027adefde914aa3/463/page-frame.html";
  const requestReferer = "https://servicewechat.com/wx8027adefde914aa3";
  const userAgent =
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
    "(KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 " +
    "MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI " +
    "MiniProgramEnv/Windows WindowsWechat/WMPF WindowsWechat(0x63090a13) " +
    "UnifiedPCWindowsWechat(0xf254181d) XWEB/19201";

  logger.info(`[JieLong] GET ${url}`);

  // 按分享 threadId 拉取接龙详情。
  const response = await http.get(url, {
    headers: requestHeaders(token, requestPayload, referer, requestReferer, userAgent),
    params: { threadId }
  });
  return expectSuccess(response, "接龙详情接口返回异常");
}

/** 获取接龙用户表单资料。 */
export async function fetchFormInfo(token: string): Promise<JieLongApiData> {
  const url = "https://api.jielong.com/api/User/Forminfo";
  const requestPayload =
    "par0NCtm+oBuEkBOI+w469O3sv7VkPQdbSZ/b146+eR59OABQtitF7jAqrza2ox4D4RUAVssL7FhoL1xIV03g90epOmj7/zKW23Ao+J5BAEGYocngDSjVMXZUnbfFG7Ka21uQjcid9Iv4VRj0yyX4qeQZRZ58wFUsW13wCd1BhHqMkS3WmJxnSq51iAEzmtIywg1nPDwc1WM4+a3Gs2ubdCQG4imuCrQbGjz0jbl7yWcPNmOGy1vHpMP7yVoRowO";
  const referer = "https://servicewechat.com/wx8027adefde914aa3/463/page-frame.html";
  const requestReferer = "https://servicewechat.com/wx8027adefde914aa3";
  const userAgent =
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
    "(KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 " +
    "MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI " +
    "MiniProgramEnv/Windows WindowsWechat/WMPF WindowsWechat(0x63090a13) " +
    "UnifiedPCWindowsWechat(0xf254181d) XWEB/19201";

  logger.info(`[JieLong] GET ${url}`);

  // 接龙用该接口返回姓名、手机号等默认表单值。
  const response = await http.get(url, {
    headers: requestHeaders(token, requestPayload, referer, requestReferer, userAgent),
    params: {}
  });
  return expectSuccess(response, "接龙用户表单接口返回异常");
}

/** 获取接龙编辑记录详情，包含可填写字段配置。 */
export async function fetchEditRecordDetail(token: string, numericThreadId: string | number): Promise<JieLongApiData> {
  const url = "https://api.jielong.com/api/CheckIn/EditRecordDetail";
  const requestPayload =
    "par0NCtm+oBuEkBOI+w46xC2JxFsUHr7SyrC3zgfsFRdL3quyfUfhuyIRBhO9FmaAHCkxrmR+Y8KV+pSK3WhZTAl1nZ8aRtzx661t3uyOpKGc+BcbvLB2PJv30vser4F6CzcBP5PF+CXH8dO7iQaZPU+mmL8+Ci5nCSws2n0vzDdkI3oRoLp868ykBb0MWaz053J0Of4UV7H9mlCHgaxeN2LYxa0ljj4Pw5OX1eXSl5BfnE8uC2drThjiNfqduTy";
  const referer = "https://servicewechat.com/wx8027adefde914aa3/463/page-frame.html";
  const requestReferer = "https://servicewechat.com/wx8027adefde914aa3";
  const userAgent =
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
    "(KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 " +
    "MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI " +
    "MiniProgramEnv/Windows WindowsWechat/WMPF WindowsWechat(0x63090a13) " +
    "UnifiedPCWindowsWechat(0xf254181d) XWEB/19201";

  logger.info(`[JieLong] GET ${url}`);

  // recordId 为 0 表示准备新提交一条记录。
  const response = await http.get(url, {
    headers: requestHeaders(token, requestPayload, referer, requestReferer, userAgent),
    params: {
      threadId: String(numericThreadId),
      recordId: "0",
      isFillCheckIn: "false",
      fillSignature: "",
      fillNumber: "0"
    }
  });
  return expectSuccess(response, "接龙编辑记录详情接口返回异常");
}

/** 获取接龙服务端草稿。 */
export async function fetchRecordDraft(token: string, numericThreadId: string | number): Promise<JieLongApiData> {
  const url = "https://api.jielong.com/api/Thread/RecordDraft";
  const requestPayload =
    "par0NCtm+oBuEkBOI+w466ekfU0HwI5JL1d8CmzerE+Yyoq84vMN0LThT6W4RqPFl8vrmFFhE+M2ceXZoj2aFFXKgAL+N3UNqwzEhy1Xam6Oik/AVQvHtVJ72U4BvWaHuSXv5QdX2zFgFrF4q7dZINK7Dbvx5fmnn78ba7yDrizlAEgeSUUtEGe1QRRHPvj/Mx5RR8Ww3HTpZgLyTIsIPdlZyO5xdUhYWnINW81BQ+ueYA/BMXsFSBwL4qL3WhiWcDgwQRub0VF3LIGM6gbZKA==";
  const referer = "https://servicewechat.com/wx8027adefde914aa3/463/page-frame.html";
  const requestReferer = "https://servicewechat.com/wx8027adefde914aa3";
  const userAgent =
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
    "(KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 " +
    "MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI " +
    "MiniProgramEnv/Windows WindowsWechat/WMPF WindowsWechat(0x63090a13) " +
    "UnifiedPCWindowsWechat(0xf254181d) XWEB/19201";

  logger.info(`[JieLong] GET ${url}`);

  // 服务端草稿用于恢复上次填写过的字段。
  const response = await http.get(url, {
    headers: requestHeaders(token, requestPayload, referer, requestReferer, userAgent),
    params: { ThreadId: String(numericThreadId) }
  });
  return expectSuccess(response, "接龙草稿接口返回异常");
}

/** 获取图片上传到 COS 需要的临时凭证。 */
export async function fetchAttachmentCosUploadPolicy(
  token: string,
  threadId: number,
  fileName: string
): Promise<JieLongApiData> {
  const url = "https://api.jielong.com/api/Attachment/CosUploadPolicy";
  const requestPayload =
    "par0NCtm+oBuEkBOI+w4657/Rp+uOyL1eVJwWmjKJP8JE18OvIuCRlAPTb0jXlPBm6E9VDx7BY4L2pQpNwZmgma1Be7gqP7v095SoUlcbQX2dcMzvifV/RWmwg5g/xw8NZ0bvxzthj35C+mDtjT7TbW7E0KRSxhkVP30PsXnIBKqCTTHMgIBjoUKP3ZEP3dh+ECW2pY+H4mYLMbDqp7NUEsdoMxmgO6T07srpzelu5y9Ou7IDXBNrMAGQH93vq7HhG+BYqR4tktlPMTSsBk9Yw==";
  const referer = "https://servicewechat.com/wx8027adefde914aa3/463/page-frame.html";
  const requestReferer = "https://servicewechat.com/wx8027adefde914aa3";
  const userAgent =
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
    "(KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 " +
    "MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI " +
    "MiniProgramEnv/Windows WindowsWechat/WMPF WindowsWechat(0x63090a13) " +
    "UnifiedPCWindowsWechat(0xf254181d) XWEB/19201";

  logger.info(`[JieLong] POST ${url}`);

  // 先向接龙接口申请 COS 上传 policy。
  const response = await http.post(
    url,
    JSON.stringify({
      tenantTypeId: "300221",
      fileName,
      associateId: Number(threadId),
      yunStore: 2
    }),
    {
      headers: requestHeaders(token, requestPayload, referer, requestReferer, userAgent)
    }
  );
  return expectSuccess(response, "接龙图片上传凭证接口返回异常");
}

/** 上传本地图片到接龙返回的 COS 地址。 */
export async function uploadToCos(
  uploadHost: string,
  policy: JieLongApiData,
  localPath: string,
  sourceName: string,
  mime: string
): Promise<JieLongApiData> {
  const referer = "https://servicewechat.com/wx8027adefde914aa3/463/page-frame.html";
  const userAgent =
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
    "(KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 " +
    "MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI " +
    "MiniProgramEnv/Windows WindowsWechat/WMPF WindowsWechat(0x63090a13) " +
    "UnifiedPCWindowsWechat(0xf254181d) XWEB/19201";
  const form = new FormData();

  // COS 表单字段必须按接龙接口返回的 policy 组装。
  form.append("key", policy.Key || "");
  form.append("success_action_status", "200");
  form.append("policy", policy.Policy || "");
  form.append("Content-Type", policy.ContentType || mime);
  form.append("q-sign-algorithm", policy.Algorithm || "");
  form.append("q-ak", policy.Ak || "");
  form.append("q-key-time", policy.KeyTime || "");
  form.append("q-signature", policy.Signature || "");
  form.append("x-cos-callback", policy.Callback || "");
  form.append("file", createReadStream(localPath), { filename: sourceName, contentType: mime });

  logger.info(`[JieLong] POST ${uploadHost}`);

  // 上传成功后 COS 回调会返回接龙可提交的文件信息。
  const response = await http.post(uploadHost, form, {
    headers: {
      ...form.getHeaders(),
      referer,
      "user-agent": userAgent
    },
    maxRedirects: 0
  });
  return expectSuccess(response, "接龙图片上传失败").Data || {};
}

/** 提交接龙打卡记录。 */
export async function submitRecord(token: string, payload: JieLongSubmitPayload): Promise<JieLongApiData> {
  const url = "https://api.jielong.com/api/CheckIn/EditRecord";
  const requestPayload =
    "par0NCtm+oBuEkBOI+w461REzcksEiTE3hYAk2qfDuRAORiAFZFU7iBYoEM7RQf68ggrRgHuyBaQYOQX/Bvsj4Tfe4v/NXbmh0NRDWr+C61L+mYkFKfSm3KdWIfsgZeHDoYZbM5ZZxa5lXSpJps8l4EDpJDZ7RRuQ0bH8yNkoV5/5K5+GRsesQmNSCB873E3qpT3GLmuYdZ7jlI1n1FRwQ2/zHiPpu3sJ8XpzH82+IUFG6pu9n+2sIOZ1tUaouq4";
  const referer = "https://servicewechat.com/wx8027adefde914aa3/463/page-frame.html";
  const requestReferer = "https://servicewechat.com/wx8027adefde914aa3";
  const userAgent =
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
    "(KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 " +
    "MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI " +
    "MiniProgramEnv/Windows WindowsWechat/WMPF WindowsWechat(0x63090a13) " +
    "UnifiedPCWindowsWechat(0xf254181d) XWEB/19201";

  logger.info(`[JieLong] POST ${url}`);

  // 提交最终的字段值、签名和图片信息。
  const response = await http.post(url, JSON.stringify(payload), {
    headers: requestHeaders(token, requestPayload, referer, requestReferer, userAgent)
  });
  return expectSuccess(response, "接龙提交接口返回异常");
}
