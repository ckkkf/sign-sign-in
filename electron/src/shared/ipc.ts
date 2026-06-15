import type {
  ApiResult,
  AutoClockNotificationConfig,
  AutoClockState,
  AuthState,
  AuthSessionPayload,
  CaptureState,
  ImageItem,
  JieLongFieldAnswer,
  JieLongFileInfo,
  JieLongFormBundle,
  JieLongQrLogin,
  JieLongQrState,
  JieLongSettings,
  JieLongSubmitPayload,
  LogEntry,
  SignConfig,
  SignOption,
  SystemStatus,
  TaskState,
  UpdateCheckResult,
  UpdateDownloadState,
  UpdateRelease,
  UpdateSettings,
  WeeklyJournalBlogList,
  WeeklyJournalHistoryItem,
  WeeklyJournalInit,
  WeeklyJournalSubmitPayload,
  WeeklyJournalWeek,
  WeeklyJournalYear
} from "./types";

export interface SignSignInApi {
  auth: {
    getState: () => Promise<ApiResult<AuthState>>;
    saveLogin: (payload: AuthSessionPayload) => Promise<ApiResult<AuthState>>;
    logout: () => Promise<ApiResult<AuthState>>;
    offline: () => Promise<ApiResult<AuthState>>;
  };
  config: {
    read: () => Promise<ApiResult<SignConfig>>;
    save: (config: SignConfig) => Promise<ApiResult<SignConfig>>;
  };
  task: {
    startSign: (option: SignOption) => Promise<ApiResult<TaskState>>;
    stopSign: () => Promise<ApiResult<TaskState>>;
    getState: () => Promise<ApiResult<TaskState>>;
    refreshSessionFromCode: () => Promise<ApiResult<TaskState>>;
  };
  autoClock: {
    getState: () => Promise<ApiResult<AutoClockState>>;
    start: () => Promise<ApiResult<AutoClockState>>;
    stop: () => Promise<ApiResult<AutoClockState>>;
    reload: () => Promise<ApiResult<AutoClockState>>;
    testNotification: (channel: AutoClockNotificationConfig) => Promise<ApiResult<boolean>>;
  };
  update: {
    check: () => Promise<ApiResult<UpdateCheckResult>>;
    loadMoreHistory: (cursor: { start: number }, excludeTag?: string) => Promise<ApiResult<{ releases: UpdateRelease[]; historyCursor: { start: number } | null }>>;
    getSettings: () => Promise<ApiResult<UpdateSettings>>;
    saveSettings: (settings: Partial<UpdateSettings>) => Promise<ApiResult<UpdateSettings>>;
    browseDownloadDir: () => Promise<ApiResult<UpdateSettings>>;
    download: (tag: string) => Promise<ApiResult<UpdateDownloadState>>;
    getDownloadState: () => Promise<ApiResult<UpdateDownloadState>>;
    pause: () => Promise<ApiResult<UpdateDownloadState>>;
    resume: () => Promise<ApiResult<UpdateDownloadState>>;
    stop: () => Promise<ApiResult<UpdateDownloadState>>;
    openDownloadDir: () => Promise<ApiResult<boolean>>;
    openRelease: (tag: string) => Promise<ApiResult<boolean>>;
    openCompare: (tag: string) => Promise<ApiResult<boolean>>;
    install: (tag: string) => Promise<ApiResult<boolean>>;
    deletePackage: (tag: string) => Promise<ApiResult<boolean>>;
  };
  weeklyJournal: {
    init: () => Promise<ApiResult<WeeklyJournalInit>>;
    loadYears: () => Promise<ApiResult<WeeklyJournalYear[]>>;
    loadWeeks: (year: string, month: string) => Promise<ApiResult<WeeklyJournalWeek[]>>;
    loadBlogs: (page: number) => Promise<ApiResult<WeeklyJournalBlogList>>;
    generate: (prompt: string) => Promise<ApiResult<WeeklyJournalHistoryItem>>;
    submit: (payload: WeeklyJournalSubmitPayload) => Promise<ApiResult<Record<string, any>>>;
  };
  code: {
    startCapture: () => Promise<ApiResult<CaptureState>>;
    stopCapture: () => Promise<ApiResult<CaptureState>>;
    getState: () => Promise<ApiResult<CaptureState>>;
    setManualCode: (code: string) => Promise<ApiResult<CaptureState>>;
    onCaptured: (callback: (code: string) => void) => () => void;
  };
  system: {
    getStatus: () => Promise<ApiResult<SystemStatus>>;
    openProxySettings: () => Promise<ApiResult<boolean>>;
    openCertManager: () => Promise<ApiResult<boolean>>;
    openUserDataDir: () => Promise<ApiResult<boolean>>;
    openConfigFile: () => Promise<ApiResult<boolean>>;
    openTerminal: () => Promise<ApiResult<boolean>>;
    flushDns: () => Promise<ApiResult<boolean>>;
    openExternal: (url: string) => Promise<ApiResult<boolean>>;
  };
  image: {
    list: () => Promise<ApiResult<ImageItem[]>>;
    import: () => Promise<ApiResult<ImageItem>>;
    rename: (path: string, name: string) => Promise<ApiResult<ImageItem>>;
    replace: (path: string) => Promise<ApiResult<ImageItem>>;
    delete: (path: string) => Promise<ApiResult<boolean>>;
    openDir: () => Promise<ApiResult<boolean>>;
  };
  jielong: {
    getSettings: () => Promise<ApiResult<JieLongSettings>>;
    saveSettings: (settings: Partial<JieLongSettings>) => Promise<ApiResult<JieLongSettings>>;
    createQrLogin: () => Promise<ApiResult<JieLongQrLogin>>;
    pollQrLogin: (uuid: string) => Promise<ApiResult<JieLongQrState>>;
    exchangeQrToken: (code: string) => Promise<ApiResult<JieLongSettings>>;
    parseShareUrl: (shareUrl: string) => Promise<ApiResult<string>>;
    loadForm: (token: string, threadId: string) => Promise<ApiResult<JieLongFormBundle>>;
    getDraft: (threadId: string) => Promise<ApiResult<Record<string, JieLongFieldAnswer>>>;
    saveDraft: (threadId: string, answers: Record<string, JieLongFieldAnswer>) => Promise<ApiResult<boolean>>;
    buildLocalMediaFiles: (paths: string[]) => Promise<ApiResult<JieLongFileInfo[]>>;
    buildSubmitPayload: (
      bundle: JieLongFormBundle,
      answers: Record<string, JieLongFieldAnswer>,
      signature: string,
      number: string
    ) => Promise<ApiResult<JieLongSubmitPayload>>;
    submit: (token: string, payload: JieLongSubmitPayload) => Promise<ApiResult<Record<string, any>>>;
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
