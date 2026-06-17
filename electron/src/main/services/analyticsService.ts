import type { ClientOperLogPayload } from "@shared/types";
import { submitClientLog } from "../api/authClient";
import { authStore } from "./authStore";
import { configStore } from "./configStore";
import { logger } from "./logger";

class AnalyticsService {
  private formatOperTime(date = new Date()): string {
    const pad = (value: number) => String(value).padStart(2, "0");
    return [
      date.getFullYear(),
      pad(date.getMonth() + 1),
      pad(date.getDate())
    ].join("-") + ` ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
  }

  private buildClientContext(): Partial<ClientOperLogPayload> {
    try {
      const input = configStore.read().input;
      return {
        userAgent: input.userAgent,
        deviceBrand: input.device.brand,
        deviceModel: input.device.model,
        deviceSystem: input.device.system,
        devicePlatform: input.device.platform,
        riskParams: JSON.stringify({
          device: {
            brand: input.device.brand,
            model: input.device.model,
            system: input.device.system,
            platform: input.device.platform
          },
          location: {
            longitude: input.location.longitude,
            latitude: input.location.latitude,
            jitterMeters: input.locationJitterMeters || ""
          },
          userAgentPresent: Boolean(input.userAgent)
        })
      };
    } catch (error) {
      logger.debug(`[Analytics] read client context failed: ${error instanceof Error ? error.message : String(error)}`);
      return {};
    }
  }

  async track(payload: ClientOperLogPayload): Promise<boolean> {
    const cache = authStore.read();
    if (!cache?.token) {
      logger.debug(`[Analytics] skipped ${payload.operType || payload.title || "event"}: no auth token`);
      return false;
    }

    const startedAt = Date.now();
    const clientContext = this.buildClientContext();
    const next: ClientOperLogPayload = {
      ...clientContext,
      ...payload,
      status: payload.status || "0",
      operTime: payload.operTime || this.formatOperTime(),
      riskParams: payload.riskParams || clientContext.riskParams,
      costTime: payload.costTime ?? Date.now() - startedAt
    };

    try {
      await submitClientLog(next, cache.token, cache.tokenName || "Xyb-Token");
      return true;
    } catch (error) {
      logger.warn(`[Analytics] 上报失败：${error instanceof Error ? error.message : String(error)}`);
      return false;
    }
  }
}

export const analyticsService = new AnalyticsService();
