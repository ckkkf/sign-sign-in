import { existsSync, readFileSync, writeFileSync, copyFileSync } from "node:fs";
import { dirname } from "node:path";
import type { SignConfig } from "@shared/types";
import { buildUserAgent, validateConfig } from "@shared/configHelpers";
import { ensureDir, ensureParent, getDefaultConfigPath, getRuntimeConfigPath } from "./paths";

const fallbackConfig: SignConfig = {
  input: {
    location: {
      longitude: "116.397128",
      latitude: "39.916527"
    },
    mapProvider: "amap",
    device: {
      brand: "OnePlus",
      model: "PHP110",
      system: "Android 15",
      platform: "android"
    },
    userAgent: ""
  },
  model: {
    baseUrl: "",
    apiKey: "",
    model: ""
  },
  settings: {
    dont_show_sponsor: false,
    auto_clock: {
      enabled: false,
      poll_seconds: 30,
      random_minutes: 0,
      tasks: [
        { time: "08:55", mode: "in" },
        { time: "18:05", mode: "out" }
      ]
    },
    notifications_enabled: false,
    notifications: [],
    pushplus: {
      token: ""
    },
    jielong: {
      authorization: "",
      thread_id: "",
      share_url: ""
    }
  }
};

export class ConfigStore {
  readonly path = getRuntimeConfigPath();

  ensure(): void {
    ensureParent(this.path);
    if (existsSync(this.path)) return;

    const defaultPath = getDefaultConfigPath();
    if (existsSync(defaultPath)) {
      copyFileSync(defaultPath, this.path);
      return;
    }
    this.write(this.normalize(fallbackConfig));
  }

  read(): SignConfig {
    this.ensure();
    const raw = JSON.parse(readFileSync(this.path, "utf-8")) as SignConfig;
    return this.normalize(raw);
  }

  write(config: SignConfig): SignConfig {
    const normalized = this.normalize(config);
    const err = validateConfig(normalized);
    if (err) {
      throw new Error(err);
    }
    ensureDir(dirname(this.path));
    writeFileSync(this.path, JSON.stringify(normalized, null, 4), "utf-8");
    return normalized;
  }

  normalize(config: SignConfig): SignConfig {
    const merged = structuredClone(fallbackConfig);
    const input = config.input || merged.input;
    merged.input = {
      ...merged.input,
      ...input,
      location: { ...merged.input.location, ...(input.location || {}) },
      device: { ...merged.input.device, ...(input.device || {}) }
    };
    merged.model = { ...merged.model, ...(config.model || {}) };
    merged.settings = {
      ...merged.settings,
      ...(config.settings || {}),
      auto_clock: {
        ...merged.settings?.auto_clock,
        ...(config.settings?.auto_clock || {})
      },
      pushplus: {
        ...merged.settings?.pushplus,
        ...(config.settings?.pushplus || {})
      },
      jielong: {
        ...merged.settings?.jielong,
        ...(config.settings?.jielong || {})
      }
    };
    if (!merged.input.userAgent) {
      merged.input.userAgent = buildUserAgent(merged.input.device);
    }
    return merged;
  }
}

export const configStore = new ConfigStore();
