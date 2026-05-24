import Toast from "@kousum/semi-ui-vue/dist/toast";
import { computed, onMounted, onUnmounted, reactive, ref } from "vue";
import type {
  AuthState,
  AuthCaptcha,
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
  const registerLoading = ref(false);
  const captchaLoading = ref(false);
  const authCaptcha = ref<AuthCaptcha | null>(null);
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
    pushplusToken: ""
  });

  const signActions = ["普通签到", "普通签退", "普通签到签退", "拍照签到", "拍照签退"] as const;
  const actionOptions: Array<{ label: SignOption["action"]; value: SignOption["action"] }> = signActions.map((action) => ({
    label: action,
    value: action
  }));
  const noticeText = "本软件完全免费，若您是付费获得，请及时退款并警惕倒卖。本项目仅支持个人学习，请勿用于商业活动。";
  const noticeContent = noticeText;
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
      { key: "Session", value: status.value.sessionValid ? "JSESSIONID 有效" : "未缓存", tone: status.value.sessionValid ? "success" as const : "warning" as const },
      { key: "Code", value: capture.value.lastCode || "未捕获", tone: capture.value.lastCode ? "success" as const : "muted" as const }
    ];
  });
  const offlineMode = computed(() => authState.value.offline);

  let unsubscribeLog: (() => void) | undefined;
  let unsubscribeCode: (() => void) | undefined;
  let timer: number | undefined;
  let stopResize: (() => void) | undefined;
  let refreshing = false;

  function isPacketLog(message: string) {
    return [
      "MITM",
      "HTTPS",
      "TLS",
      "抓包",
      "code",
      "Code",
      "代理",
      "小程序",
      "微信",
      "JSESSIONID",
      "上游连接"
    ].some((keyword) => message.includes(keyword));
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

  async function refreshAll() {
    if (refreshing) return;
    refreshing = true;
    try {
      await runAction(async () => {
        const [statusResult, taskResult, captureResult, imageResult] = await Promise.all([
          window.signSignIn.system.getStatus(),
          window.signSignIn.task.getState(),
          window.signSignIn.code.getState(),
          window.signSignIn.image.list()
        ]);
        status.value = ensureOk(statusResult);
        task.value = ensureOk(taskResult);
        capture.value = ensureOk(captureResult);
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

  async function loadAuthState() {
    await runAction(async () => {
      const state = ensureOk(await window.signSignIn.auth.getState());
      authState.value = state;
      loginVisible.value = !state.loggedIn && !state.offline;
      if (state.loggedIn) {
        Toast.success("登录成功");
      }
    });
  }

  function openLoginIfLoggedOut() {
    if (authState.value.loggedIn) return;
    loginVisible.value = true;
  }

  async function login(payload: LoginPayload) {
    loginLoading.value = true;
    try {
      await runAction(async () => {
        const state = ensureOk(await window.signSignIn.auth.login(payload));
        authState.value = state;
        loginVisible.value = false;
      }, "登录成功");
    } finally {
      loginLoading.value = false;
    }
  }

  async function loadCaptcha() {
    captchaLoading.value = true;
    try {
      await runAction(async () => {
        authCaptcha.value = ensureOk(await window.signSignIn.auth.captcha());
      });
    } finally {
      captchaLoading.value = false;
    }
  }

  async function register(payload: RegisterPayload) {
    registerLoading.value = true;
    try {
      await runAction(async () => {
        ensureOk(await window.signSignIn.auth.register(payload));
      }, "注册成功，请登录");
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
    await runAction(async () => {
      const item = ensureOk(await window.signSignIn.image.import());
      selectedImage.value = item.path;
      await refreshAll();
    }, "图片已导入");
  }

  async function deleteSelectedImage() {
    if (!selectedImage.value) return;
    await runAction(async () => {
      ensureOk(await window.signSignIn.image.delete(selectedImage.value));
      selectedImage.value = "";
      await refreshAll();
    }, "图片已删除");
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
        pushplus: {
          token: draft.pushplusToken
        }
      }
    };
    await runAction(async () => {
      config.value = ensureOk(await window.signSignIn.config.save(next));
      await loadConfig();
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

  async function copyQQGroup() {
    await navigator.clipboard?.writeText("859098272");
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
    bootError,
    captchaLoading,
    capture,
    changeInput,
    clearLogs,
    clearPacketSnapshot,
    copyLogs,
    copyPacketSnapshot,
    copyQQGroup,
    deleteSelectedImage,
    draft,
    images,
    importImage,
    enterOfflineMode,
    isPhotoAction,
    login,
    loginLoading,
    loginVisible,
    loading,
    logPanelWidth,
    logs,
    noticeContent,
    offlineMode,
    openCertManager,
    openLoginIfLoggedOut,
    openProxySettings,
    packetLogs,
    page,
    manualRefreshAll,
    refreshAll,
    regenerateUserAgent,
    register,
    registerLoading,
    loadCaptcha,
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
    task
  };
}
