import { AUTH_BASE_URL } from "@shared/constants";
import type {
  AuthCaptcha,
  AuthEmailCode,
  AuthLoginResult,
  AuthUser,
  ClientEnvPayload,
  LoginPayload,
  RegisterPayload
} from "@shared/types";
import { trackClientEventAsync, stringifyParam } from "../utils/analytics";

interface AjaxResult<T> {
  code: string | number;
  msg?: string;
  data?: T;
  token?: string;
  tokenName?: string;
}

const responseMeta = new WeakMap<Response, {
  operType: string;
  title: string;
  requestUrl: string;
  requestParam?: unknown;
  startedAt: number;
}>();

async function trackedFetch(
  input: RequestInfo | URL,
  init: RequestInit | undefined,
  meta: { operType: string; title: string; requestParam?: unknown }
): Promise<Response> {
  const startedAt = Date.now();
  const requestUrl = typeof input === "string" ? input : input.toString();
  try {
    const response = await fetch(input, init);
    responseMeta.set(response, { ...meta, requestUrl, startedAt });
    await trackClientEventAsync({
      operType: meta.operType,
      status: response.ok ? "0" : "1",
      title: meta.title,
      requestUrl,
      requestParam: stringifyParam(meta.requestParam || {}),
      responseSummary: `http=${response.status}`,
      costTime: Date.now() - startedAt
    });
    return response;
  } catch (error) {
    await trackClientEventAsync({
      operType: meta.operType,
      status: "1",
      title: meta.title,
      requestUrl,
      requestParam: stringifyParam(meta.requestParam || {}),
      errorMsg: error instanceof Error ? error.message : String(error),
      costTime: Date.now() - startedAt
    });
    throw error;
  }
}

function maskEmail(email: string): string {
  const [name, domain] = String(email || "").split("@");
  if (!domain) return "";
  return `${name.slice(0, 2)}***@${domain}`;
}

export interface FeedbackPayload {
  title: string;
  feedbackType: string;
  priority: string;
  contact: string;
  content: string;
}

export interface ClientNotice {
  noticeId?: number | string;
  noticeTitle?: string;
  noticeContent?: string;
  title?: string;
  content?: string;
}

function clientEnvHeaders(clientEnv?: ClientEnvPayload): Record<string, string> {
  if (!clientEnv) {
    return {};
  }

  const headers: Record<string, string> = {};
  const assign = (key: string, value?: string) => {
    const text = String(value || "").trim();
    if (text) {
      headers[key] = encodeURIComponent(text);
    }
  };

  assign("X-Xyb-User-Agent", clientEnv.userAgent);
  assign("X-Xyb-Device-Brand", clientEnv.deviceBrand);
  assign("X-Xyb-Device-Model", clientEnv.deviceModel);
  assign("X-Xyb-Device-System", clientEnv.deviceSystem);
  assign("X-Xyb-Device-Platform", clientEnv.devicePlatform);
  assign("X-Xyb-Risk-Params", clientEnv.riskParams);
  return headers;
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
  if (String(body.code) !== "200") {
    const meta = responseMeta.get(response);
    if (meta) {
      await trackClientEventAsync({
        operType: meta.operType,
        status: "1",
        title: `${meta.title}业务失败`,
        requestUrl: meta.requestUrl,
        requestParam: stringifyParam(meta.requestParam || {}),
        responseSummary: `code=${body.code}`,
        errorMsg: body.msg || fallback,
        costTime: Date.now() - meta.startedAt
      });
    }
  }
  return requireSuccess(body, fallback) as T;
}

/** 发起桌面账号登录请求，Network 面板可直接看到。 */
export async function login(payload: LoginPayload, clientEnv?: ClientEnvPayload): Promise<AuthLoginResult> {
  const response = await trackedFetch(`${AUTH_BASE_URL}/xyb/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...clientEnvHeaders(clientEnv)
    },
    body: JSON.stringify({
      username: payload.username,
      password: payload.password,
      code: payload.code,
      uuid: payload.uuid,
      ...clientEnv
    })
  }, {
    operType: "AUTH_LOGIN_REQUEST",
    title: "请求客户端登录接口",
    requestParam: { username: payload.username, hasCode: Boolean(payload.code), hasUuid: Boolean(payload.uuid) }
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
  const response = await trackedFetch(`${AUTH_BASE_URL}/xyb/auth/me`, {
    headers: {
      [tokenName]: token
    }
  }, {
    operType: "AUTH_ME_REQUEST",
    title: "请求当前登录用户",
    requestParam: { tokenName, hasToken: Boolean(token) }
  });
  return normalizeUser(await readJson<AuthUser>(response, "获取用户信息失败"));
}

/** 退出桌面账号登录。 */
export async function logout(token: string, tokenName = "Xyb-Token", clientEnv?: ClientEnvPayload): Promise<void> {
  const response = await trackedFetch(`${AUTH_BASE_URL}/xyb/auth/logout`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...clientEnvHeaders(clientEnv),
      [tokenName]: token
    },
    body: JSON.stringify(clientEnv || {})
  }, {
    operType: "AUTH_LOGOUT_REQUEST",
    title: "请求客户端退出登录接口",
    requestParam: { tokenName, hasToken: Boolean(token) }
  });
  await readJson<unknown>(response, "退出登录失败");
}

/** 获取登录验证码。 */
export async function loginCaptcha(): Promise<AuthCaptcha> {
  const response = await trackedFetch(`${AUTH_BASE_URL}/xyb/auth/login-captcha`, undefined, {
    operType: "AUTH_LOGIN_CAPTCHA",
    title: "获取登录验证码"
  });
  const authCaptcha = await readJson<AuthCaptcha>(response, "获取验证码失败");

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
  const response = await trackedFetch(`${AUTH_BASE_URL}/xyb/auth/captcha`, undefined, {
    operType: "AUTH_REGISTER_CAPTCHA",
    title: "获取注册验证码"
  });
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
  const response = await trackedFetch(`${AUTH_BASE_URL}/xyb/auth/email-code`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ email })
  }, {
    operType: "AUTH_EMAIL_CODE_SEND",
    title: "发送注册邮箱验证码",
    requestParam: { email: maskEmail(email) }
  });
  const result = await readJson<AuthEmailCode>(response, "发送邮箱验证码失败");
  const emailUuid = String(result?.emailUuid || "").trim();

  if (!emailUuid) {
    throw new Error("发送邮箱验证码失败：后端未返回 emailUuid");
  }

  return emailUuid;
}

/** 注册桌面账号。 */
export async function register(payload: RegisterPayload, clientEnv?: ClientEnvPayload): Promise<void> {
  const response = await trackedFetch(`${AUTH_BASE_URL}/xyb/auth/register`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...clientEnvHeaders(clientEnv)
    },
    body: JSON.stringify({
      username: payload.username,
      password: payload.password,
      email: payload.email,
      emailCode: payload.emailCode,
      emailUuid: payload.emailUuid,
      code: payload.code,
      uuid: payload.uuid,
      ...clientEnv
    })
  }, {
    operType: "AUTH_REGISTER_REQUEST",
    title: "请求客户端注册接口",
    requestParam: { username: payload.username, email: maskEmail(payload.email), hasEmailUuid: Boolean(payload.emailUuid), hasUuid: Boolean(payload.uuid) }
  });
  await readJson<unknown>(response, "注册失败");
}

/** 提交校友邦客户端反馈。 */
export async function submitFeedback(payload: FeedbackPayload, token: string, tokenName = "Xyb-Token"): Promise<void> {
  const response = await trackedFetch(`${AUTH_BASE_URL}/xyb/auth/feedback`, {
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
  }, {
    operType: "FEEDBACK_SUBMIT_REQUEST",
    title: "请求提交问题反馈接口",
    requestParam: { title: payload.title, feedbackType: payload.feedbackType, priority: payload.priority, contentLength: payload.content.length }
  });
  await readJson<unknown>(response, "反馈提交失败");
}

/** 获取客户端公告；接口不可用时由调用方使用本地兜底公告。 */
export async function listClientNotices(): Promise<string[]> {
  const response = await trackedFetch(`${AUTH_BASE_URL}/xyb/notice/client-list`, undefined, {
    operType: "NOTICE_LOAD",
    title: "加载客户端公告"
  });
  const notices = await readJson<ClientNotice[]>(response, "获取公告失败");
  return (notices || [])
    .map((notice) => String(notice.noticeContent || notice.content || notice.noticeTitle || notice.title || "").trim())
    .filter(Boolean);
}
