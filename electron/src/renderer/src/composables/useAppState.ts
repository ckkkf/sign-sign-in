import Toast from "@kousum/semi-ui-vue/dist/toast";
import { computed, onMounted, onUnmounted, reactive, ref } from "vue";
import { QQ_GROUP } from "@shared/constants";
import type {
  AuthState,
  AuthCaptcha,
  AutoClockNotificationConfig,
  AutoClockState,
  AutoClockTaskConfig,
  ClientEnvPayload,
  CaptureState,
  ImageItem,
  LoginPayload,
  LogEntry,
  RegisterPayload,
  SignConfig,
  SignOption,
  SystemStatus,
  TaskState
} from "@shared/types";
import * as authApi from "../services/authApi";
import type { FeedbackPayload } from "../services/authApi";
import { buildUserAgent } from "../services/config";
import type { DraftConfigKey, PageKey } from "../types/app";
import { ensureOk } from "../utils/api";

export function useAppState() {
  const page = ref<PageKey>("dashboard");
  const loading = ref(false);
  const bootError = ref("");
  const selectedAction = ref<SignOption["action"]>("普通签到");
  const selectedImage = ref("");
  const logs = ref<LogEntry[]>([]);
  const packetLogs = ref<LogEntry[]>([]);
  const images = ref<ImageItem[]>([]);
  const config = ref<SignConfig | null>(null);
  const logPanelWidth = ref(420);
  const authState = ref<AuthState>({
    loggedIn: false,
    offline: false
  });
  const loginVisible = ref(false);
  const loginLoading = ref(false);
  const feedbackVisible = ref(false);
  const feedbackLoading = ref(false);
  const imageManagerVisible = ref(false);
  const updateCenterVisible = ref(false);
  const autoClockDialogVisible = ref(false);
  const weeklyJournalVisible = ref(false);
  const registerLoading = ref(false);
  const captchaLoading = ref(false);
  const loginCaptchaLoading = ref(false);
  const emailCodeLoading = ref(false);
  const registerEmailUuid = ref("");
  const registerSuccessTick = ref(0);
  const authCaptcha = ref<AuthCaptcha | null>(null);
  const loginAuthCaptcha = ref<AuthCaptcha | null>(null);
  const status = ref<SystemStatus>({
    time: "-",
    pid: 0,
    networkType: "未知",
    proxy: "未检测",
    speed: "-",
    proxyServerRunning: false,
    certInstalled: false,
    ip: "-",
    sessionValid: false
  });
  const task = ref<TaskState>({
    running: false,
    source: "",
    action: "",
    message: "空闲"
  });
  const autoClock = ref<AutoClockState>({
    enabled: false,
    running: false,
    message: "未启动"
  });
  const capture = ref<CaptureState>({
    running: false,
    host: "127.0.0.1",
    port: 13140,
    lastCode: "",
    message: "未启动"
  });

  const draft = reactive({
    longitude: "",
    latitude: "",
    locationJitterMeters: "100",
    brand: "",
    model: "",
    systemVersion: "",
    platform: "android",
    userAgent: "",
    pushplusToken: "",
    autoClockEnabled: "false",
    autoClockPollSeconds: "30",
    autoClockRandomMinutes: "0",
    notificationsEnabled: "false",
    autoClockTasks: [] as AutoClockTaskConfig[],
    notifications: [] as AutoClockNotificationConfig[]
  });

  const signActions = ["普通签到", "普通签退", "普通签到签退", "拍照签到", "拍照签退"] as const;
  const actionOptions: Array<{ label: SignOption["action"]; value: SignOption["action"] }> = signActions.map((action) => ({
    label: action,
    value: action
  }));
  const noticeText = "本软件完全免费，若您是付费获得，请及时退款并警惕倒卖。本项目仅支持个人学习，请勿用于商业活动。";
  const noticeContents = ref<string[]>([noticeText]);
  const noticeContent = computed(() => noticeContents.value.length ? noticeContents.value : [noticeText]);
  const isPhotoAction = computed(() => selectedAction.value === "拍照签到" || selectedAction.value === "拍照签退");
  const statusItems = computed(() => {
    const mitmRunning = capture.value.running || status.value.proxyServerRunning;
    return [
      { key: "时间", value: status.value.time, tone: "info" as const },
      { key: "PID", value: String(status.value.pid), tone: "muted" as const },
      { key: "网络", value: status.value.networkType || "未知", tone: status.value.networkType === "未知" ? "warning" as const : "success" as const },
      { key: "速度", value: status.value.speed || "-", tone: status.value.speed === "-" ? "muted" as const : "success" as const },
      { key: "代理", value: status.value.proxy, tone: status.value.proxy === "直连" ? "muted" as const : "warning" as const },
      { key: "证书", value: status.value.certInstalled ? "已就绪" : "未安装", tone: status.value.certInstalled ? "success" as const : "danger" as const },
      { key: "Mitm", value: capture.value.running ? "抓包中" : status.value.proxyServerRunning ? "代理运行" : "未启动", tone: mitmRunning ? "success" as const : "muted" as const },
      { key: "IP", value: status.value.ip, tone: "info" as const },
      { key: "Code", value: capture.value.lastCode || "未捕获", tone: capture.value.lastCode ? "success" as const : "muted" as const },
      { key: "Session", value: status.value.sessionValid ? "JSESSIONID 有效" : "未缓存", tone: status.value.sessionValid ? "success" as const : "warning" as const }
    ];
  });
  const offlineMode = computed(() => authState.value.offline);

  let unsubscribeLog: (() => void) | undefined;
  let unsubscribeCode: (() => void) | undefined;
  let timer: number | undefined;
  let stopResize: (() => void) | undefined;
  let refreshing = false;

  function isPacketLog(message: string) {
    if (message.startsWith("渲染控制台:")) {
      return false;
    }

    return [
      "MITM",
      "HTTPS",
      "TLS",
      "抓包",
      "代理",
      "小程序",
      "微信",
      "JSESSIONID",
      "上游连接"
    ].some((keyword) => message.includes(keyword)) || /(^|[^a-zA-Z])code([^a-zA-Z]|$)/.test(message);
  }

  function pushLog(entry: LogEntry) {
    if (isPacketLog(entry.message)) {
      packetLogs.value.unshift(entry);
      return;
    }
    logs.value.unshift(entry);
  }

  function pushLocalLog(message: string, level: LogEntry["level"] = "info") {
    pushLog({
      time: new Date().toLocaleTimeString(),
      level,
      message
    });
  }

  async function runAction<T>(action: () => Promise<T>, success?: string) {
    try {
      const result = await action();
      if (success) Toast.success(success);
      return result;
    } catch (error) {
      const message = error instanceof Error ? error.message : "操作失败";
      pushLocalLog(message, "error");
      Toast.error(message);
      return undefined;
    }
  }

  function buildClientEnv(action: string): ClientEnvPayload {
    const currentInput = config.value?.input;
    const device = currentInput?.device;
    const env: ClientEnvPayload = {
      userAgent: draft.userAgent || currentInput?.userAgent || "",
      deviceBrand: draft.brand || device?.brand || "",
      deviceModel: draft.model || device?.model || "",
      deviceSystem: draft.systemVersion ? `Android ${draft.systemVersion}` : device?.system || "",
      devicePlatform: draft.platform || device?.platform || ""
    };
    env.riskParams = JSON.stringify({
      action,
      device: {
        brand: env.deviceBrand,
        model: env.deviceModel,
        system: env.deviceSystem,
        platform: env.devicePlatform
      },
      location: {
        hasLongitude: Boolean(draft.longitude || currentInput?.location.longitude),
        hasLatitude: Boolean(draft.latitude || currentInput?.location.latitude),
        jitterMeters: draft.locationJitterMeters || currentInput?.locationJitterMeters || ""
      },
      userAgentPresent: Boolean(env.userAgent)
    });
    return env;
  }

  async function refreshAll() {
    if (refreshing) return;
    refreshing = true;
    try {
      await runAction(async () => {
        const [statusResult, taskResult, captureResult, autoClockResult, imageResult] = await Promise.all([
          window.signSignIn.system.getStatus(),
          window.signSignIn.task.getState(),
          window.signSignIn.code.getState(),
          window.signSignIn.autoClock.getState(),
          window.signSignIn.image.list()
        ]);
        status.value = ensureOk(statusResult);
        task.value = ensureOk(taskResult);
        capture.value = ensureOk(captureResult);
        autoClock.value = ensureOk(autoClockResult);
        images.value = ensureOk(imageResult);
      });
    } finally {
      refreshing = false;
    }
  }

  async function manualRefreshAll() {
    await refreshAll();
    Toast.success("状态已刷新");
  }

  async function toggleAutoClock() {
    const shouldStop = autoClock.value.enabled;
    await runAction(async () => {
      autoClock.value = ensureOk(
        shouldStop ? await window.signSignIn.autoClock.stop() : await window.signSignIn.autoClock.start()
      );
      await refreshAll();
    }, shouldStop ? "定时打卡已停止" : "定时打卡已启动");
  }

  async function loadAuthState() {
    await runAction(async () => {
      const state = ensureOk(await window.signSignIn.auth.getState());
      authState.value = state;
      loginVisible.value = !state.loggedIn && !state.offline;
      if (state.loggedIn) {
        Toast.success("登录成功");
      } else {
        await loadLoginCaptcha();
      }
    });
  }

  async function loadNoticeContent() {
    try {
      const notices = await authApi.listClientNotices();
      noticeContents.value = notices.length ? notices : [noticeText];
    } catch {
      noticeContents.value = [noticeText];
    }
  }

  function openLoginIfLoggedOut() {
    if (authState.value.loggedIn) {
      return;
    }

    loginVisible.value = true;
    void loadLoginCaptcha();
  }

  function openFeedback() {
    if (!authState.value.loggedIn || !authState.value.token) {
      loginVisible.value = true;
      Toast.warning("请先登录后再发送反馈");
      return;
    }

    feedbackVisible.value = true;
  }

  async function login(payload: LoginPayload) {
    loginLoading.value = true;
    try {
      await runAction(async () => {
        const session = await authApi.login(payload, buildClientEnv("AUTH_LOGIN"));
        const user = await authApi.me(session.token, session.tokenName);
        const state = ensureOk(await window.signSignIn.auth.saveLogin({ ...session, user }));
        authState.value = state;
        loginVisible.value = false;
      }, "登录成功");
    } finally {
      loginLoading.value = false;
      await loadLoginCaptcha();
    }
  }

  async function loadCaptcha() {
    captchaLoading.value = true;
    try {
      await runAction(async () => {
        authCaptcha.value = await authApi.captcha();
      });
    } finally {
      captchaLoading.value = false;
    }
  }

  async function loadLoginCaptcha() {
    loginCaptchaLoading.value = true;
    try {
      await runAction(async () => {
        loginAuthCaptcha.value = await authApi.loginCaptcha();
      });
    } finally {
      loginCaptchaLoading.value = false;
    }
  }

  async function sendEmailCode(email: string) {
    const trimmedEmail = email.trim();
    if (!trimmedEmail) {
      Toast.warning("请先填写邮箱");
      return;
    }

    emailCodeLoading.value = true;
    try {
      await runAction(async () => {
        registerEmailUuid.value = await authApi.sendEmailCode(trimmedEmail);
      }, "邮箱验证码已发送");
    } finally {
      emailCodeLoading.value = false;
    }
  }

  function clearRegisterEmailCode() {
    registerEmailUuid.value = "";
  }

  async function register(payload: RegisterPayload) {
    if (!payload.email.trim() || !payload.emailCode.trim() || !payload.emailUuid.trim()) {
      Toast.warning("请填写邮箱并完成邮箱验证码验证");
      return;
    }

    registerLoading.value = true;
    try {
      const success = await runAction(async () => {
        await authApi.register(payload, buildClientEnv("AUTH_REGISTER"));
        return true;
      }, "注册成功，请登录");

      if (success) {
        registerEmailUuid.value = "";
        registerSuccessTick.value += 1;
      }
      await loadCaptcha();
    } finally {
      registerLoading.value = false;
    }
  }

  async function enterOfflineMode() {
    await runAction(async () => {
      authState.value = ensureOk(await window.signSignIn.auth.offline());
      loginVisible.value = false;
    }, "已进入离线模式");
  }

  async function logout() {
    await runAction(async () => {
      const token = authState.value.token || "";
      if (token) {
        try {
          await authApi.logout(token, authState.value.tokenName || "Xyb-Token", buildClientEnv("AUTH_LOGOUT"));
        } catch (error) {
          const message = error instanceof Error ? error.message : String(error);
          pushLocalLog(`远程登出失败，已清理本地登录态：${message}`, "warn");
        }
      }
      authState.value = ensureOk(await window.signSignIn.auth.logout());
      loginVisible.value = true;
      await loadLoginCaptcha();
    }, "已退出登录");
  }

  async function submitFeedback(payload: FeedbackPayload) {
    if (!payload.title || !payload.content) {
      Toast.warning("请填写反馈标题和内容");
      return;
    }

    const token = authState.value.token || "";
    const tokenName = authState.value.tokenName || "Xyb-Token";
    if (!token) {
      loginVisible.value = true;
      Toast.warning("请先登录后再发送反馈");
      return;
    }

    feedbackLoading.value = true;
    try {
      await runAction(async () => {
        await authApi.submitFeedback(payload, token, tokenName);
        feedbackVisible.value = false;
      }, "反馈提交成功，感谢支持");
    } finally {
      feedbackLoading.value = false;
    }
  }

  async function loadConfig() {
    await runAction(async () => {
      const loaded = ensureOk(await window.signSignIn.config.read());
      config.value = loaded;
      draft.longitude = loaded.input.location.longitude;
      draft.latitude = loaded.input.location.latitude;
      draft.locationJitterMeters = String(loaded.input.locationJitterMeters ?? "100");
      draft.brand = loaded.input.device.brand;
      draft.model = loaded.input.device.model;
      draft.systemVersion = loaded.input.device.system.replace(/^Android\s*/i, "");
      draft.platform = String(loaded.input.device.platform || "android");
      draft.userAgent = loaded.input.userAgent;
      draft.pushplusToken = loaded.settings?.pushplus?.token || "";
      draft.autoClockEnabled = String(Boolean(loaded.settings?.auto_clock?.enabled));
      draft.autoClockPollSeconds = String(loaded.settings?.auto_clock?.poll_seconds ?? 30);
      draft.autoClockRandomMinutes = String(loaded.settings?.auto_clock?.random_minutes ?? 0);
      draft.autoClockTasks = [...(loaded.settings?.auto_clock?.tasks || [])];
      draft.notificationsEnabled = String(Boolean(loaded.settings?.notifications_enabled));
      draft.notifications = [...(loaded.settings?.notifications || [])];
    });
  }

  function currentOption(): SignOption {
    if (selectedAction.value === "普通签到签退") {
      return {
        action: "普通签到签退",
        code: "2",
        steps: [
          { action: "普通签到", code: "2" },
          { action: "普通签退", code: "1" }
        ]
      };
    }
    const code = selectedAction.value === "普通签退" || selectedAction.value === "拍照签退" ? "1" : "2";
    return {
      action: selectedAction.value,
      code,
      imagePath: selectedImage.value || undefined
    };
  }

  async function startTask() {
    loading.value = true;
    try {
      await runAction(async () => {
        task.value = ensureOk(await window.signSignIn.task.startSign(currentOption()));
        await refreshAll();
      }, "任务已开始");
    } finally {
      loading.value = false;
    }
  }

  async function stopTask() {
    await runAction(async () => {
      task.value = ensureOk(await window.signSignIn.task.stopSign());
    }, "任务已停止");
  }

  async function startCapture() {
    await runAction(async () => {
      capture.value = ensureOk(await window.signSignIn.code.startCapture());
      await refreshAll();
    }, "code 捕获已启动");
  }

  async function stopCapture() {
    await runAction(async () => {
      capture.value = ensureOk(await window.signSignIn.code.stopCapture());
      await refreshAll();
    }, "code 捕获已停止");
  }

  async function importImage() {
    return runAction(async () => {
      const item = ensureOk(await window.signSignIn.image.import());
      selectedImage.value = item.path;
      await refreshAll();
      return item;
    }, "图片已导入");
  }

  async function importImageForTask(index: number) {
    const item = await importImage();
    if (!item) return;
    const tasks = [...draft.autoClockTasks];
    if (!tasks[index]) return;
    tasks[index] = { ...tasks[index], image_path: item.path };
    draft.autoClockTasks = tasks;
  }

  async function testNotification(channel: AutoClockNotificationConfig) {
    await runAction(async () => ensureOk(await window.signSignIn.autoClock.testNotification(channel)), "测试通知已发送");
  }

  function openImageManager() {
    imageManagerVisible.value = true;
    void refreshAll();
  }

  async function renameImage(path: string, name: string) {
    return runAction(async () => {
      const item = ensureOk(await window.signSignIn.image.rename(path, name));
      if (selectedImage.value === path) selectedImage.value = item.path;
      await refreshAll();
      return item;
    }, "图片已重命名");
  }

  async function replaceImage(path: string) {
    return runAction(async () => {
      const item = ensureOk(await window.signSignIn.image.replace(path));
      if (selectedImage.value === path) selectedImage.value = item.path;
      await refreshAll();
      return item;
    }, "图片已替换");
  }

  async function deleteImage(path: string) {
    return runAction(async () => {
      ensureOk(await window.signSignIn.image.delete(path));
      if (selectedImage.value === path) selectedImage.value = "";
      await refreshAll();
      return true;
    }, "图片已删除");
  }

  async function deleteSelectedImage() {
    if (!selectedImage.value) return;
    await deleteImage(selectedImage.value);
  }

  async function openImageDir() {
    await runAction(async () => ensureOk(await window.signSignIn.image.openDir()));
  }

  function regenerateUserAgent() {
    draft.userAgent = buildUserAgent({
      brand: draft.brand,
      model: draft.model,
      system: `Android ${draft.systemVersion}`,
      platform: draft.platform
    });
  }

  async function saveConfig() {
    const current = config.value;
    if (!current) return;
    const autoClockTasks = draft.autoClockTasks;
    const notifications = draft.notifications;
    const next: SignConfig = {
      ...current,
      input: {
        ...current.input,
        location: {
          longitude: draft.longitude,
          latitude: draft.latitude
        },
        locationJitterMeters: draft.locationJitterMeters,
        device: {
          brand: draft.brand,
          model: draft.model,
          system: `Android ${draft.systemVersion}`,
          platform: draft.platform
        },
        userAgent: draft.userAgent
      },
      settings: {
        ...current.settings,
        auto_clock: {
          ...current.settings?.auto_clock,
          enabled: draft.autoClockEnabled === "true",
          poll_seconds: Math.max(10, Number(draft.autoClockPollSeconds || 30)),
          random_minutes: Math.max(0, Math.min(120, Number(draft.autoClockRandomMinutes || 0))),
          tasks: autoClockTasks
        },
        notifications_enabled: draft.notificationsEnabled === "true",
        notifications,
        pushplus: {
          token: draft.pushplusToken
        }
      }
    };
    await runAction(async () => {
      config.value = ensureOk(await window.signSignIn.config.save(next));
      autoClock.value = ensureOk(await window.signSignIn.autoClock.reload());
      await loadConfig();
      await refreshAll();
    }, "配置已保存");
  }

  async function clearLogs() {
    await runAction(async () => {
      ensureOk(await window.signSignIn.log.clear());
      logs.value = [];
    }, "日志已清空");
  }

  async function copyLogs() {
    if (!logs.value.length) {
      Toast.warning("暂无日志可复制");
      return;
    }
    await runAction(async () => {
      const text = logs.value
        .slice()
        .reverse()
        .map((entry) => `[${entry.time}] ${entry.level.toUpperCase()} ${entry.message}`)
        .join("\n");
      await navigator.clipboard.writeText(text);
    }, "日志已复制");
  }

  async function copyPacketSnapshot() {
    if (!packetLogs.value.length) {
      Toast.warning("暂无抓包日志可复制");
      return;
    }
    await runAction(async () => {
      const text = packetLogs.value
        .slice()
        .reverse()
        .map((entry) => `[${entry.time}] ${entry.level.toUpperCase()} ${entry.message}`)
        .join("\n");
      await navigator.clipboard.writeText(text);
    }, "抓包快照已复制");
  }

  async function clearPacketSnapshot() {
    packetLogs.value = [];
    Toast.success("抓包快照已清空");
  }

  async function openProxySettings() {
    await runAction(async () => ensureOk(await window.signSignIn.system.openProxySettings()));
  }

  async function openCertManager() {
    await runAction(async () => ensureOk(await window.signSignIn.system.openCertManager()));
  }

  async function openUserDataDir() {
    await runAction(async () => ensureOk(await window.signSignIn.system.openUserDataDir()));
  }

  async function openConfigFile() {
    await runAction(async () => ensureOk(await window.signSignIn.system.openConfigFile()));
  }

  async function openTerminal() {
    await runAction(async () => ensureOk(await window.signSignIn.system.openTerminal()));
  }

  async function flushDns() {
    const ok = await runAction(async () => ensureOk(await window.signSignIn.system.flushDns()));
    if (!ok) {
      Toast.warning("当前系统暂不支持自动刷新 DNS");
    } else {
      Toast.success("DNS 刷新成功");
    }
  }

  async function openExternal(url: string) {
    await runAction(async () => ensureOk(await window.signSignIn.system.openExternal(url)));
  }

  function openUpdateCenter() {
    updateCenterVisible.value = true;
  }

  function openAutoClockDialog() {
    autoClockDialogVisible.value = true;
  }

  function openWeeklyJournal() {
    if (!status.value.sessionValid) {
      Toast.warning("Session 未缓存，请先获取或刷新 JSESSIONID");
      return;
    }
    weeklyJournalVisible.value = true;
  }

  async function copyQQGroup() {
    await navigator.clipboard?.writeText(QQ_GROUP);
    Toast.success("QQ群号已复制");
  }

  function changeInput(key: DraftConfigKey, value: string) {
    draft[key] = value;
  }

  function startResize(event: MouseEvent) {
    const startX = event.clientX;
    const startWidth = logPanelWidth.value;
    const onMove = (moveEvent: MouseEvent) => {
      const next = startWidth - (moveEvent.clientX - startX);
      logPanelWidth.value = Math.min(520, Math.max(320, next));
    };
    const onUp = () => {
      document.body.classList.remove("is-resizing");
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
      stopResize = undefined;
    };
    document.body.classList.add("is-resizing");
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    stopResize = onUp;
  }

  onMounted(async () => {
    document.body.setAttribute("theme-mode", "dark");
    try {
      unsubscribeLog = window.signSignIn.log.subscribe(pushLog);
      unsubscribeCode = window.signSignIn.code.onCaptured(() => {
        if (task.value.running) return;
        Toast.success("已抓到 code，正在更新 JSESSIONID");
        void runAction(async () => {
          task.value = ensureOk(await window.signSignIn.task.refreshSessionFromCode());
          await refreshAll();
        });
      });
      await loadAuthState();
      await loadConfig();
      await loadNoticeContent();
      await refreshAll();
      timer = window.setInterval(() => {
        refreshAll().catch(() => undefined);
      }, 1000);
    } catch (error) {
      bootError.value = error instanceof Error ? error.message : "初始化失败";
      pushLocalLog(`初始化失败：${bootError.value}`, "error");
    }
  });

  onUnmounted(() => {
    unsubscribeLog?.();
    unsubscribeCode?.();
    if (timer) window.clearInterval(timer);
    stopResize?.();
  });

  return {
    actionOptions,
    authState,
    authCaptcha,
    autoClockDialogVisible,
    autoClock,
    loginAuthCaptcha,
    bootError,
    captchaLoading,
    loginCaptchaLoading,
    capture,
    changeInput,
    clearRegisterEmailCode,
    clearLogs,
    clearPacketSnapshot,
    copyLogs,
    copyPacketSnapshot,
    copyQQGroup,
    deleteSelectedImage,
    draft,
    images,
    imageManagerVisible,
    importImage,
    importImageForTask,
    enterOfflineMode,
    emailCodeLoading,
    feedbackLoading,
    feedbackVisible,
    isPhotoAction,
    login,
    loginLoading,
    loginVisible,
    logout,
    loading,
    logPanelWidth,
    logs,
    noticeContent,
    offlineMode,
    openCertManager,
    openConfigFile,
    openExternal,
    openFeedback,
    openImageDir,
    openImageManager,
    openLoginIfLoggedOut,
    openProxySettings,
    openTerminal,
    openUpdateCenter,
    openAutoClockDialog,
    openUserDataDir,
    openWeeklyJournal,
    packetLogs,
    page,
    manualRefreshAll,
    refreshAll,
    regenerateUserAgent,
    registerEmailUuid,
    registerSuccessTick,
    renameImage,
    replaceImage,
    register,
    registerLoading,
    loadCaptcha,
    loadLoginCaptcha,
    sendEmailCode,
    saveConfig,
    selectedAction,
    selectedImage,
    startCapture,
    startResize,
    startTask,
    status,
    statusItems,
    stopCapture,
    stopTask,
    submitFeedback,
    testNotification,
    toggleAutoClock,
    flushDns,
    deleteImage,
    task,
    updateCenterVisible,
    weeklyJournalVisible
  };
}
