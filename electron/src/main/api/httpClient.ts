import axios, { type AxiosInstance, type AxiosRequestConfig } from "axios";
import { AUTH_BASE_URL } from "@shared/constants";
import { logger } from "../services/logger";

type TimedRequestConfig = AxiosRequestConfig & {
  metadata?: {
    startedAt: number;
  };
};

const SENSITIVE_KEYS = ["token", "authorization", "password", "code", "captcha", "uuid", "encrypt", "session", "openid", "unionid", "key", "signature", "policy", "cookie"];
const SKIP_ANALYTICS_URLS = [
  "lp.open.weixin.qq.com/connect/l/qrconnect"
];

/** 通用第三方接口 HTTP 实例，保持抓包类接口不自动抛 HTTP 状态异常。 */
export const http = axios.create({
  timeout: 15000,
  maxRedirects: 0,
  validateStatus: () => true
});

/** 桌面账号后端接口 HTTP 实例。 */
export const authHttp = axios.create({
  baseURL: AUTH_BASE_URL,
  timeout: 8000,
  headers: {
    "Content-Type": "application/json"
  }
});

/** 生成日志里展示的请求地址。 */
function requestUrl(config: AxiosRequestConfig): string {
  const baseUrl = String(config.baseURL || "").replace(/\/+$/, "");
  const url = String(config.url || "");

  if (/^https?:\/\//i.test(url)) {
    return url;
  }

  return `${baseUrl}${url.startsWith("/") ? url : `/${url}`}`;
}

function shouldSkipAnalytics(url: string): boolean {
  return SKIP_ANALYTICS_URLS.some((item) => url.includes(item));
}

function sanitizeValue(value: unknown, key = ""): unknown {
  if (SENSITIVE_KEYS.some((item) => key.toLowerCase().includes(item))) {
    return value ? "***" : "";
  }
  if (typeof value === "string") {
    return value.length > 180 ? `${value.slice(0, 180)}...(${value.length})` : value;
  }
  if (Array.isArray(value)) {
    return { type: "array", length: value.length };
  }
  if (value && typeof value === "object") {
    const output: Record<string, unknown> = {};
    Object.entries(value as Record<string, unknown>).slice(0, 16).forEach(([childKey, childValue]) => {
      output[childKey] = sanitizeValue(childValue, childKey);
    });
    return output;
  }
  return value;
}

function summarizeRequest(config: AxiosRequestConfig): string {
  const payload: Record<string, unknown> = {
    method: String(config.method || "GET").toUpperCase(),
    params: sanitizeValue(config.params, "params")
  };
  if (config.data instanceof URLSearchParams) {
    payload.data = sanitizeValue(Object.fromEntries(config.data.entries()), "data");
  } else if (typeof config.data === "string") {
    payload.data = sanitizeValue(config.data, "data");
  } else if (config.data && typeof config.data === "object" && !("pipe" in config.data)) {
    payload.data = sanitizeValue(config.data, "data");
  }
  return JSON.stringify(payload);
}

function summarizeResponse(data: unknown, status?: number): string {
  const body = data && typeof data === "object" ? data as Record<string, unknown> : {};
  return JSON.stringify({
    http: status,
    code: body.code ?? body.Code ?? body.Type ?? "",
    msg: sanitizeValue(body.msg ?? body.message ?? body.Description ?? body.Msg ?? body.Message ?? "", "msg"),
    hasData: body.data !== undefined || body.Data !== undefined
  });
}

function operTypeForUrl(url: string): string {
  if (url.includes("xcx.xybsyw.com")) return "XYB_HTTP_REQUEST";
  if (url.includes("jielong.com")) return "JIELONG_HTTP_REQUEST";
  if (url.includes("restapi.amap.com")) return "AMAP_HTTP_REQUEST";
  if (url.includes("aliyuncs.com") || url.includes("myqcloud.com")) return "UPLOAD_HTTP_REQUEST";
  return "EXTERNAL_HTTP_REQUEST";
}

function titleForUrl(url: string): string {
  if (url.includes("student/clock/GetPlan.action")) return "请求校友邦实习计划";
  if (url.includes("common/getOpenId.action")) return "请求校友邦 OpenId";
  if (url.includes("login/login!wx.action")) return "请求校友邦微信登录";
  if (url.includes("student/clock/Post.action")) return "请求校友邦普通打卡";
  if (url.includes("student/clock/PostNew.action")) return "请求校友邦拍照打卡";
  if (url.includes("uploadfile/commonPostPolicy.action")) return "请求校友邦上传凭证";
  if (url.includes("student/blog/")) return "请求校友邦周记接口";
  if (url.includes("careerplanning/saveSession.action")) return "请求校友邦 AI 接口";
  if (url.includes("api.jielong.com")) return "请求接龙接口";
  if (url.includes("restapi.amap.com")) return "请求高德逆地理接口";
  if (url.includes("aliyuncs.com") || url.includes("myqcloud.com")) return "上传客户端图片";
  return "请求外部接口";
}

async function trackHttpEvent(config: TimedRequestConfig, status: "0" | "1", responseSummary: string, errorMsg?: string): Promise<void> {
  const url = requestUrl(config);
  if (shouldSkipAnalytics(url)) return;
  try {
    const { analyticsService } = await import("../services/analyticsService");
    await analyticsService.track({
      operType: operTypeForUrl(url),
      status,
      title: titleForUrl(url),
      requestUrl: url,
      requestParam: summarizeRequest(config),
      responseSummary,
      errorMsg,
      costTime: Date.now() - (config.metadata?.startedAt || Date.now())
    });
  } catch {
    // 埋点不能影响真实业务请求。
  }
}

/** 给主进程 axios 请求补充可观察日志。 */
function attachHttpLogger(instance: AxiosInstance, label: string): void {
  instance.interceptors.request.use((config) => {
    const timedConfig = config as TimedRequestConfig;
    timedConfig.metadata = { startedAt: Date.now() };
    logger.debug(`[${label}] ${String(config.method || "GET").toUpperCase()} ${requestUrl(config)}`);
    return config;
  });

  instance.interceptors.response.use(
    (response) => {
      const config = response.config as TimedRequestConfig;
      const elapsed = Date.now() - (config.metadata?.startedAt || Date.now());
      logger.info(`[${label}] ${response.status} ${String(config.method || "GET").toUpperCase()} ${requestUrl(config)} ${elapsed}ms`);
      if (label === "HTTP") {
        void trackHttpEvent(config, response.status >= 200 && response.status < 400 ? "0" : "1", summarizeResponse(response.data, response.status));
      }
      return response;
    },
    (error) => {
      if (axios.isAxiosError(error)) {
        const config = (error.config || {}) as TimedRequestConfig;
        const elapsed = Date.now() - (config.metadata?.startedAt || Date.now());
        const status = error.response?.status ? `${error.response.status} ` : "";
        logger.error(`[${label}] ${status}${String(config.method || "GET").toUpperCase()} ${requestUrl(config)} ${elapsed}ms ${error.message}`);
        if (label === "HTTP") {
          void trackHttpEvent(config, "1", summarizeResponse(error.response?.data, error.response?.status), error.message);
        }
      }

      return Promise.reject(error);
    }
  );
}

attachHttpLogger(http, "HTTP");
attachHttpLogger(authHttp, "AUTH");
