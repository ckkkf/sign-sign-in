export interface SignConfig {
  input: {
    location: {
      longitude: string;
      latitude: string;
    };
    device: {
      brand: string;
      model: string;
      system: string;
      platform: "android" | "ios" | string;
    };
    userAgent: string;
    locationJitterMeters?: string | number;
    code?: string;
    openId?: string;
    unionId?: string;
    encryptValue?: string;
    sessionId?: string;
  };
  model?: {
    baseUrl?: string;
    apiKey?: string;
    model?: string;
  };
  settings?: {
    dont_show_sponsor?: boolean;
    auto_clock?: {
      enabled?: boolean;
      poll_seconds?: number;
      random_minutes?: number;
      tasks?: unknown[];
    };
    pushplus?: {
      token?: string;
    };
    jielong?: Record<string, string>;
  };
}

export interface SessionCache {
  sessionId: string;
  encryptValue: string;
  openId: string;
  unionId: string;
  traineeId?: string;
  savedAt: number;
  expiresAt: number;
}

export interface HeaderToken {
  m: string;
  t: string;
  s: string;
  n: string;
}

export interface SignOption {
  action: "普通签到" | "普通签退" | "普通签到签退" | "拍照签到" | "拍照签退";
  code: "1" | "2";
  imagePath?: string;
  steps?: Array<Omit<SignOption, "steps">>;
}

export interface TaskState {
  running: boolean;
  source: "manual" | "auto" | "";
  action: string;
  message: string;
  startedAt?: number;
}

export interface CaptureState {
  running: boolean;
  host: string;
  port: number;
  lastCode: string;
  message: string;
}

export interface SystemStatus {
  time: string;
  pid: number;
  networkType: string;
  proxy: string;
  speed: string;
  proxyServerRunning: boolean;
  certInstalled: boolean;
  ip: string;
  sessionValid: boolean;
}

export interface AuthUser {
  userId?: number;
  username?: string;
  nickName?: string;
  avatar?: string;
  xybUserId?: number;
  xybUserName?: string;
  phone?: string;
  schoolName?: string;
  companyName?: string;
  wxid?: string;
  openId?: string;
  unionId?: string;
  status?: string;
}

export interface AuthState {
  loggedIn: boolean;
  offline: boolean;
  user?: AuthUser;
}

export interface LoginPayload {
  username: string;
  password: string;
}

export interface RegisterPayload extends LoginPayload {
  confirmPassword: string;
  code: string;
  uuid: string;
}

export interface AuthCaptcha {
  uuid: string;
  img: string;
}

export interface ImageItem {
  name: string;
  path: string;
}

export interface LogEntry {
  level: "debug" | "info" | "warn" | "error";
  message: string;
  time: string;
}

export interface ApiResult<T = unknown> {
  ok: boolean;
  data?: T;
  error?: string;
}
