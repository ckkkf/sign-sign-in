import axios, { type AxiosInstance } from "axios";
import type { AuthCaptcha, AuthUser, RegisterPayload } from "@shared/types";

const AUTH_BASE_URL = "http://localhost:18080";

interface AjaxResult<T> {
  code?: number | string;
  msg?: string;
  data?: T;
}

class AuthClient {
  private readonly http: AxiosInstance;
  readonly baseUrl = AUTH_BASE_URL;

  constructor() {
    this.http = axios.create({
      baseURL: this.baseUrl,
      timeout: 8000,
      headers: {
        "Content-Type": "application/json"
      }
    });
  }

  async login(username: string, password: string): Promise<string> {
    const response = await this.http.post<AjaxResult<string>>("/api/auth/login", { username, password });
    const result = this.requireSuccess(response.data, "登录失败");
    if (!result) throw new Error("登录失败：后端未返回 token");
    return result;
  }

  async captcha(): Promise<AuthCaptcha> {
    const response = await this.http.get<AjaxResult<AuthCaptcha>>("/api/auth/captcha");
    const captcha = this.requireSuccess(response.data, "获取验证码失败");
    if (!captcha?.uuid || !captcha.img) throw new Error("获取验证码失败：后端返回为空");
    return {
      uuid: captcha.uuid,
      img: captcha.img.startsWith("data:") ? captcha.img : `data:image/png;base64,${captcha.img}`
    };
  }

  async register(payload: RegisterPayload): Promise<void> {
    const response = await this.http.post<AjaxResult<unknown>>("/api/auth/register", {
      username: payload.username,
      password: payload.password,
      code: payload.code,
      uuid: payload.uuid
    });
    this.requireSuccess(response.data, "注册失败");
  }

  async me(token: string): Promise<AuthUser> {
    const response = await this.http.get<AjaxResult<AuthUser>>("/api/auth/me", {
      headers: {
        Authorization: `Bearer ${token}`
      }
    });
    return this.normalizeUser(this.requireSuccess(response.data, "获取用户信息失败") || {});
  }

  private requireSuccess<T>(result: AjaxResult<T>, fallback: string): T | undefined {
    if (String(result.code) !== "200") {
      throw new Error(result.msg || fallback);
    }
    return result.data;
  }

  private normalizeUser(user: AuthUser): AuthUser {
    if (!user.avatar) return user;
    if (/^https?:\/\//i.test(user.avatar)) return user;
    const avatarPath = user.avatar.startsWith("/") ? user.avatar : `/${user.avatar}`;
    return { ...user, avatar: `${this.baseUrl}${avatarPath}` };
  }
}

export function authErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as AjaxResult<unknown> | undefined;
    if (data?.msg) return data.msg;
    if (error.code === "ECONNABORTED") return "登录服务连接超时";
    if (error.message) return error.message;
  }
  return error instanceof Error ? error.message : fallback;
}

export const authClient = new AuthClient();
