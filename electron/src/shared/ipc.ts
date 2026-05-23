import type {
  ApiResult,
  CaptureState,
  ImageItem,
  LogEntry,
  SignConfig,
  SignOption,
  SystemStatus,
  TaskState
} from "./types";

export interface SignSignInApi {
  config: {
    read: () => Promise<ApiResult<SignConfig>>;
    save: (config: SignConfig) => Promise<ApiResult<SignConfig>>;
  };
  task: {
    startSign: (option: SignOption) => Promise<ApiResult<TaskState>>;
    stopSign: () => Promise<ApiResult<TaskState>>;
    getState: () => Promise<ApiResult<TaskState>>;
  };
  code: {
    startCapture: () => Promise<ApiResult<CaptureState>>;
    stopCapture: () => Promise<ApiResult<CaptureState>>;
    getState: () => Promise<ApiResult<CaptureState>>;
    setManualCode: (code: string) => Promise<ApiResult<CaptureState>>;
    startFridaHook: () => Promise<ApiResult<CaptureState>>;
    stopFridaHook: () => Promise<ApiResult<CaptureState>>;
    onCaptured: (callback: (code: string) => void) => () => void;
  };
  system: {
    getStatus: () => Promise<ApiResult<SystemStatus>>;
    openProxySettings: () => Promise<ApiResult<boolean>>;
    openCertManager: () => Promise<ApiResult<boolean>>;
  };
  image: {
    list: () => Promise<ApiResult<ImageItem[]>>;
    import: () => Promise<ApiResult<ImageItem>>;
    delete: (path: string) => Promise<ApiResult<boolean>>;
  };
  log: {
    clear: () => Promise<ApiResult<boolean>>;
    subscribe: (callback: (entry: LogEntry) => void) => () => void;
  };
}

declare global {
  interface Window {
    signSignIn: SignSignInApi;
  }
}
