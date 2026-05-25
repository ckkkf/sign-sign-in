import axios, { type AxiosInstance, type AxiosRequestConfig } from "axios";
import { AUTH_BASE_URL } from "@shared/constants";
import { logger } from "../services/logger";

type TimedRequestConfig = AxiosRequestConfig & {
  metadata?: {
    startedAt: number;
  };
};

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
      return response;
    },
    (error) => {
      if (axios.isAxiosError(error)) {
        const config = (error.config || {}) as TimedRequestConfig;
        const elapsed = Date.now() - (config.metadata?.startedAt || Date.now());
        const status = error.response?.status ? `${error.response.status} ` : "";
        logger.error(`[${label}] ${status}${String(config.method || "GET").toUpperCase()} ${requestUrl(config)} ${elapsed}ms ${error.message}`);
      }

      return Promise.reject(error);
    }
  );
}

attachHttpLogger(http, "HTTP");
attachHttpLogger(authHttp, "AUTH");
