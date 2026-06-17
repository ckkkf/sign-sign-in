import type { ClientOperLogPayload } from "@shared/types";

export function trackClientEvent(payload: ClientOperLogPayload): void {
  window.signSignIn.analytics.track(payload).catch(() => undefined);
}

export async function trackClientEventAsync(payload: ClientOperLogPayload): Promise<void> {
  await window.signSignIn.analytics.track(payload).catch(() => undefined);
}

export function stringifyParam(value: unknown): string {
  if (value === undefined || value === null) return "";
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}
