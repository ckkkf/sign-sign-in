import type { AuthSessionPayload, AuthState } from "@shared/types";
import { isAuthExpiredError, me } from "../api/authClient";
import { authStore } from "./authStore";
import { logger } from "./logger";

class AuthService {
  async getState(): Promise<AuthState> {
    if (authStore.isOffline()) {
      return { loggedIn: false, offline: true };
    }

    const cache = authStore.read();
    if (!cache?.token) {
      return { loggedIn: false, offline: false };
    }

    try {
      const user = await me(cache.token, cache.tokenName);
      return authStore.save(cache.token, user, cache.tokenName);
    } catch (error) {
      if (isAuthExpiredError(error)) {
        authStore.clear();
        return { loggedIn: false, offline: false };
      }

      logger.warn(`登录态校验失败，保留本地登录缓存：${error instanceof Error ? error.message : String(error)}`);
      return authStore.toState(cache);
    }
  }

  saveLogin(payload: AuthSessionPayload): AuthState {
    const token = payload.token.trim();
    if (!token) {
      throw new Error("登录成功但 token 为空");
    }

    return authStore.save(token, payload.user || {}, payload.tokenName);
  }

  logout(): AuthState {
    authStore.clear();
    return { loggedIn: false, offline: false };
  }

  offline(): AuthState {
    return authStore.enterOffline();
  }
}

export const authService = new AuthService();
