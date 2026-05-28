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
    jielong?: Record<string, any>;
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
  token?: string;
  tokenName?: string;
}

export interface AuthSessionPayload {
  token: string;
  tokenName?: string;
  user: AuthUser;
}

export interface AuthLoginResult {
  token: string;
  tokenName: string;
}

export interface LoginPayload {
  username: string;
  password: string;
  code: string;
  uuid: string;
}

export interface RegisterPayload extends LoginPayload {
  confirmPassword: string;
  email: string;
  emailCode: string;
  emailUuid: string;
  code: string;
  uuid: string;
}

export interface AuthCaptcha {
  uuid: string;
  img: string;
}

export interface AuthEmailCode {
  emailUuid: string;
}

export interface JieLongSettings {
  authorization: string;
  thread_id: string;
  share_url: string;
  openId?: string;
  sId?: string;
  expire?: string | number;
  termsAgreed?: boolean;
  isNew?: boolean;
}

export interface JieLongQrLogin {
  uuid: string;
  qrcodeUrl: string;
  image: string;
}

export interface JieLongQrState {
  status: "waiting" | "scanned" | "confirmed" | "expired" | "error" | "timeout";
  wxErrcode: string;
  code: string;
  message: string;
  raw: string;
}

export interface JieLongField {
  Id: number | string;
  FieldType?: number;
  Name?: string;
  IsRequired?: boolean;
  IsTextarea?: boolean;
  InitialValue?: string;
  InitialFiles?: JieLongFileInfo[];
  ControlOptions?: unknown;
  VisibilityCondition?: Array<{ OptionValue?: string | number; RelationIdList?: string[] }>;
  RelationId?: string;
  Tip?: string;
  Rows?: number;
  [key: string]: unknown;
}

export interface JieLongFileInfo {
  Name?: string;
  FileName?: string;
  ContentType?: string;
  Size?: number | string;
  LocalPath?: string;
  RelativePath?: string;
  Url?: string;
  IsNewUpload?: boolean;
  [key: string]: unknown;
}

export interface JieLongFormBundle {
  thread: Record<string, any>;
  check_in: Record<string, any>;
  edit_detail: Record<string, any>;
  fields: JieLongField[];
}

export interface JieLongFieldAnswer {
  value?: string;
  area?: string;
  place?: string;
  longitude?: string;
  latitude?: string;
  option_text?: string;
  option_value?: string;
  other_value?: string;
  files?: JieLongFileInfo[];
}

export interface JieLongSubmitPayload {
  Id: number;
  ThreadId: number;
  Number: string;
  Signature: string;
  RecordValues: Array<Record<string, any>>;
  DateTarget: string;
  IsNeedManualAudit: boolean;
  MinuteTarget: number;
  IsNameNumberComfirm: boolean;
}

export interface JieLongStatus {
  text: string;
  tone: "ready" | "working" | "success" | "error";
}

export interface ImageItem {
  name: string;
  path: string;
  previewUrl: string;
  size: number;
  updatedAt: number;
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
