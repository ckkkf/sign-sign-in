import { existsSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import type { AuthState, AuthUser } from "@shared/types";
import { ensureParent, getRuntimeAuthPath } from "./paths";

interface AuthCache {
  token: string;
  user: AuthUser;
  savedAt: number;
}

class AuthStore {
  private offline = false;
  readonly path = getRuntimeAuthPath();

  read(): AuthCache | null {
    if (!existsSync(this.path)) return null;
    try {
      const raw = JSON.parse(readFileSync(this.path, "utf-8")) as AuthCache;
      if (!raw.token) return null;
      return raw;
    } catch {
      this.clear();
      return null;
    }
  }

  save(token: string, user: AuthUser): AuthState {
    ensureParent(this.path);
    writeFileSync(this.path, JSON.stringify({ token, user, savedAt: Date.now() }, null, 2), "utf-8");
    this.offline = false;
    return { loggedIn: true, offline: false, user };
  }

  clear(): void {
    if (existsSync(this.path)) {
      rmSync(this.path, { force: true });
    }
  }

  enterOffline(): AuthState {
    this.offline = true;
    return { loggedIn: false, offline: true };
  }

  isOffline(): boolean {
    return this.offline;
  }
}

export const authStore = new AuthStore();
