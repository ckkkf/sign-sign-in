import { AUTH_BASE_URL } from "@shared/constants";
import type { AuthCaptcha, AuthEmailCode, AuthLoginResult, AuthUser, LoginPayload, RegisterPayload } from "@shared/types";

interface AjaxResult<T> {
  code: string | number;
  msg?: string;
  data?: T;
  token?: string;
  tokenName?: string;
}

export interface FeedbackPayload {
  title: string;
  feedbackType: string;
  priority: string;
  contact: string;
  content: string;
}

/** 校验后端 AjaxResult 是否成功。 */
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

/** 读取 JSON 响应并转换后端错误文案。 */
async function readJson<T>(response: Response, fallback: string): Promise<T> {
  const body = (await response.json()) as AjaxResult<T>;
  return requireSuccess(body, fallback) as T;
}

/** 发起桌面账号登录请求，Network 面板可直接看到。 */
export async function login(payload: LoginPayload): Promise<AuthLoginResult> {
  const response = await fetch(`${AUTH_BASE_URL}/xyb/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      username: payload.username,
      password: payload.password
    })
  });
  const body = (await response.json()) as AjaxResult<string>;
  requireSuccess(body, "登录失败");
  const token = String(body.data || body.token || "").trim();
  const tokenName = String(body.tokenName || "Xyb-Token").trim();

  if (!token) {
    throw new Error("登录失败：后端未返回 token");
  }

  return { token, tokenName };
}

/** 获取当前登录用户信息。 */
export async function me(token: string, tokenName = "Xyb-Token"): Promise<AuthUser> {
  const response = await fetch(`${AUTH_BASE_URL}/xyb/auth/me`, {
    headers: {
      [tokenName]: token
    }
  });
  return normalizeUser(await readJson<AuthUser>(response, "获取用户信息失败"));
}

/** 退出桌面账号登录。 */
export async function logout(token: string, tokenName = "Xyb-Token"): Promise<void> {
  const response = await fetch(`${AUTH_BASE_URL}/xyb/auth/logout`, {
    method: "POST",
    headers: {
      [tokenName]: token
    }
  });
  await readJson<unknown>(response, "退出登录失败");
}

/** 获取注册验证码。 */
export async function captcha(): Promise<AuthCaptcha> {
  const response = await fetch(`${AUTH_BASE_URL}/xyb/auth/captcha`);
  const authCaptcha = await readJson<AuthCaptcha>(response, "获取验证码失败");

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
  const response = await fetch(`${AUTH_BASE_URL}/xyb/auth/email-code`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ email })
  });
  const result = await readJson<AuthEmailCode>(response, "发送邮箱验证码失败");
  const emailUuid = String(result?.emailUuid || "").trim();

  if (!emailUuid) {
    throw new Error("发送邮箱验证码失败：后端未返回 emailUuid");
  }

  return emailUuid;
}

/** 注册桌面账号。 */
export async function register(payload: RegisterPayload): Promise<void> {
  const response = await fetch(`${AUTH_BASE_URL}/xyb/auth/register`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      username: payload.username,
      password: payload.password,
      email: payload.email,
      emailCode: payload.emailCode,
      emailUuid: payload.emailUuid,
      code: payload.code,
      uuid: payload.uuid
    })
  });
  await readJson<unknown>(response, "注册失败");
}

/** 提交校友邦客户端反馈。 */
export async function submitFeedback(payload: FeedbackPayload, token: string, tokenName = "Xyb-Token"): Promise<void> {
  const response = await fetch(`${AUTH_BASE_URL}/xyb/auth/feedback`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      [tokenName]: token
    },
    body: JSON.stringify({
      title: payload.title,
      feedbackType: payload.feedbackType,
      priority: payload.priority,
      status: "0",
      contact: payload.contact,
      content: payload.content
    })
  });
  await readJson<unknown>(response, "反馈提交失败");
}
