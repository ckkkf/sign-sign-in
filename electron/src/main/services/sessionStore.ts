import { existsSync, readFileSync, unlinkSync, writeFileSync } from "node:fs";
import type { SessionCache } from "@shared/types";
import { ensureParent, getRuntimeSessionPath } from "./paths";

const SESSION_TTL_MS = 60 * 60 * 1000;

export class SessionStore {
  readonly path = getRuntimeSessionPath();

  read(): SessionCache | null {
    if (!existsSync(this.path)) return null;
    try {
      const cache = JSON.parse(readFileSync(this.path, "utf-8")) as SessionCache;
      if (!cache.sessionId || !cache.encryptValue || !cache.openId || !cache.unionId) {
        this.clear();
        return null;
      }
      if (cache.expiresAt <= Date.now()) {
        this.clear();
        return null;
      }
      return cache;
    } catch {
      this.clear();
      return null;
    }
  }

  save(input: Omit<SessionCache, "savedAt" | "expiresAt">): SessionCache {
    const cache: SessionCache = {
      ...input,
      savedAt: Date.now(),
      expiresAt: Date.now() + SESSION_TTL_MS
    };
    ensureParent(this.path);
    writeFileSync(this.path, JSON.stringify(cache, null, 2), "utf-8");
    return cache;
  }

  clear(): void {
    if (existsSync(this.path)) {
      unlinkSync(this.path);
    }
  }
}

export const sessionStore = new SessionStore();
