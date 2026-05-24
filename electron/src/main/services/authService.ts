import type { AuthCaptcha, AuthState, LoginPayload, RegisterPayload } from "@shared/types";
import { authClient, authErrorMessage } from "./authClient";
import { authStore } from "./authStore";

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
      const user = await authClient.me(cache.token);
      authStore.save(cache.token, user);
      return { loggedIn: true, offline: false, user };
    } catch {
      authStore.clear();
      return { loggedIn: false, offline: false };
    }
  }

  async login(payload: LoginPayload): Promise<AuthState> {
    const username = payload.username.trim();
    const password = payload.password;
    if (!username || !password) {
      throw new Error("请输入账号和密码");
    }

    try {
      const token = await authClient.login(username, password);
      const user = await authClient.me(token);
      return authStore.save(token, user);
    } catch (error) {
      throw new Error(authErrorMessage(error, "登录失败"));
    }
  }

  async captcha(): Promise<AuthCaptcha> {
    try {
      return await authClient.captcha();
    } catch (error) {
      throw new Error(authErrorMessage(error, "获取验证码失败"));
    }
  }

  async register(payload: RegisterPayload): Promise<boolean> {
    const username = payload.username.trim();
    const password = payload.password;
    const confirmPassword = payload.confirmPassword;
    const code = payload.code.trim();
    if (!username || !password || !confirmPassword || !code || !payload.uuid) {
      throw new Error("请完整填写注册信息");
    }
    if (password !== confirmPassword) {
      throw new Error("两次输入的密码不一致");
    }

    try {
      await authClient.register({ ...payload, username, code });
      return true;
    } catch (error) {
      throw new Error(authErrorMessage(error, "注册失败"));
    }
  }

  offline(): AuthState {
    return authStore.enterOffline();
  }
}

export const authService = new AuthService();
