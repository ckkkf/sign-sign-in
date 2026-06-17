import type { LogEntry } from "@shared/types";

export type PageKey = "dashboard" | "jielong" | "config";

export interface StatusItem {
  key: string;
  value: string;
  tone: "info" | "success" | "warning" | "danger" | "muted";
}

export type DraftConfigKey =
  | "longitude"
  | "latitude"
  | "locationJitterMeters"
  | "brand"
  | "model"
  | "systemVersion"
  | "platform"
  | "mapProvider"
  | "userAgent"
  | "pushplusToken"
  | "autoClockEnabled"
  | "autoClockPollSeconds"
  | "autoClockRandomMinutes"
  | "notificationsEnabled";

export type LocalLogLevel = LogEntry["level"];
