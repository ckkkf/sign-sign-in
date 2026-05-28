import axios from "axios";
import type { AuthCaptcha, AuthEmailCode, AuthUser, RegisterPayload } from "@shared/types";
import { AUTH_BASE_URL } from "@shared/constants";
import { authHttp } from "./httpClient";
import type { AjaxResult } from "./types/authTypes";

/** 校验 RuoYi 风格 AjaxResult 是否成功。 */
function requireSuccess<T>(result: AjaxResult<T>, fallback: string): T | undefined {
  if (String(result.code) !== "200") {
    throw new Error(result.msg || fallback);
  }

  return result.data;
}

/** 补全相对头像路径为后端绝对地址。 */
function normalizeUser(user: AuthUser): AuthUser {
  if (!user.avatar) {
    return user;
  }

  if (/^https?:\/\//i.test(user.avatar)) {
    return user;
  }

  const avatarPath = user.avatar.startsWith("/") ? user.avatar : `/${user.avatar}`;
  return { ...user, avatar: `${AUTH_BASE_URL}${avatarPath}` };
}

/** 登录桌面端账号并返回后端 token。 */
export async function login(username: string, password: string, code: string, uuid: string): Promise<string> {
  // 登录接口返回 token 字符串。
  const response = await authHttp.post<AjaxResult<string>>("/xyb/auth/login", { username, password, code, uuid });
  requireSuccess(response.data, "登录失败");
  const result = String(response.data.data || response.data.token || "").trim();

  if (!result) {
    throw new Error("登录失败：后端未返回 token");
  }

  return result;
}

/** 获取登录验证码。 */
export async function loginCaptcha(): Promise<AuthCaptcha> {
  // 后端返回 base64 图片和验证码 uuid。
  const response = await authHttp.get<AjaxResult<AuthCaptcha>>("/xyb/auth/login-captcha");
  const authCaptcha = requireSuccess(response.data, "获取验证码失败");

  if (!authCaptcha?.uuid || !authCaptcha.img) {
    throw new Error("获取验证码失败：后端返回为空");
  }

  return {
    uuid: authCaptcha.uuid,
    img: authCaptcha.img.startsWith("data:") ? authCaptcha.img : `data:image/png;base64,${authCaptcha.img}`
  };
}

/** 获取注册验证码。 */
export async function captcha(): Promise<AuthCaptcha> {
  // 后端返回 base64 图片和验证码 uuid。
  const response = await authHttp.get<AjaxResult<AuthCaptcha>>("/xyb/auth/captcha");
  const authCaptcha = requireSuccess(response.data, "获取验证码失败");

  if (!authCaptcha?.uuid || !authCaptcha.img) {
    throw new Error("获取验证码失败：后端返回为空");
  }

  return {
    uuid: authCaptcha.uuid,
    img: authCaptcha.img.startsWith("data:") ? authCaptcha.img : `data:image/png;base64,${authCaptcha.img}`
  };
}

/** 发送注册邮箱验证码。 */
export async function sendEmailCode(email: string): Promise<string> {
  const response = await authHttp.post<AjaxResult<AuthEmailCode>>("/xyb/auth/email-code", { email });
  const result = requireSuccess(response.data, "发送邮箱验证码失败");
  const emailUuid = String(result?.emailUuid || "").trim();

  if (!emailUuid) {
    throw new Error("发送邮箱验证码失败：后端未返回 emailUuid");
  }

  return emailUuid;
}

/** 注册桌面端账号。 */
export async function register(payload: RegisterPayload): Promise<void> {
  // 注册接口需要图片验证码和邮箱验证码。
  const response = await authHttp.post<AjaxResult<unknown>>("/xyb/auth/register", {
    username: payload.username,
    password: payload.password,
    email: payload.email,
    emailCode: payload.emailCode,
    emailUuid: payload.emailUuid,
    code: payload.code,
    uuid: payload.uuid
  });
  requireSuccess(response.data, "注册失败");
}

/** 获取当前登录用户信息。 */
export async function me(token: string, tokenName = "Xyb-Token"): Promise<AuthUser> {
  // Sa-Token 客户端接口使用后端返回的 tokenName 鉴权。
  const response = await authHttp.get<AjaxResult<AuthUser>>("/xyb/auth/me", {
    headers: {
      [tokenName]: token
    }
  });
  return normalizeUser(requireSuccess(response.data, "获取用户信息失败") || {});
}

/** 判断认证错误是否明确表示登录态已经失效。 */
export function isAuthExpiredError(error: unknown): boolean {
  if (axios.isAxiosError(error)) {
    const status = error.response?.status;
    if (status === 401 || status === 403) {
      return true;
    }

    const data = error.response?.data as AjaxResult<unknown> | undefined;
    const message = String(data?.msg || error.message || "");
    return /未登录|登录状态已失效|无效|过期|token/i.test(message);
  }

  const message = error instanceof Error ? error.message : String(error || "");
  return /未登录|登录状态已失效|无效|过期|token/i.test(message);
}

/** 将登录相关异常转换为 UI 可展示文案。 */
export function authErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as AjaxResult<unknown> | undefined;

    if (data?.msg) {
      return data.msg;
    }

    if (error.code === "ECONNABORTED") {
      return "登录服务连接超时";
    }

    if (error.message) {
      return error.message;
    }
  }

  return error instanceof Error ? error.message : fallback;
}
