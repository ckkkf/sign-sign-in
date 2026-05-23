<script setup lang="ts">
import { computed, h, onMounted, onUnmounted, reactive, ref } from "vue";
import Banner from "@kousum/semi-ui-vue/dist/banner";
import Button from "@kousum/semi-ui-vue/dist/button";
import Card from "@kousum/semi-ui-vue/dist/card";
import Descriptions from "@kousum/semi-ui-vue/dist/descriptions";
import Input from "@kousum/semi-ui-vue/dist/input";
import RadioGroup from "@kousum/semi-ui-vue/dist/radio/radioGroup";
import Select from "@kousum/semi-ui-vue/dist/select";
import Space from "@kousum/semi-ui-vue/dist/space";
import Tag from "@kousum/semi-ui-vue/dist/tag";
import TextArea from "@kousum/semi-ui-vue/dist/input/textArea";
import Toast from "@kousum/semi-ui-vue/dist/toast";
import TypographyText from "@kousum/semi-ui-vue/dist/typography/text";
import TypographyTitle from "@kousum/semi-ui-vue/dist/typography/title";
import {
  IconApps,
  IconClock,
  IconCodeStroked,
  IconCopy,
  IconDeleteStroked,
  IconDesktop,
  IconFile,
  IconHomeStroked,
  IconImage,
  IconLink,
  IconLockStroked,
  IconPlay,
  IconRefresh,
  IconSave,
  IconSendStroked,
  IconSetting,
  IconShieldStroked,
  IconStop,
  IconTerminal,
  IconUpload,
  IconUser
} from "@kousum/semi-icons-vue";
import type { CaptureState, ImageItem, LogEntry, SignConfig, SignOption, SystemStatus, TaskState } from "@shared/types";
import { buildUserAgent } from "./services/config";

type PageKey = "dashboard" | "config";

const page = ref<PageKey>("dashboard");
const loading = ref(false);
const bootError = ref("");
const selectedAction = ref<SignOption["action"]>("普通签到");
const selectedImage = ref("");
const manualCode = ref("");
const logs = ref<LogEntry[]>([]);
const images = ref<ImageItem[]>([]);
const config = ref<SignConfig | null>(null);
const logPanelWidth = ref(420);
const status = ref<SystemStatus>({
  time: "-",
  proxy: "未检测",
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
const noticeContent = `公告 · ${noticeText}`;
const isPhotoAction = computed(() => selectedAction.value === "拍照签到" || selectedAction.value === "拍照签退");
const statusItems = computed(() => [
  { key: "时间", value: status.value.time },
  { key: "PID", value: "Electron" },
  { key: "网络", value: status.value.proxy === "直连" ? "直连" : "代理" },
  { key: "速度", value: "-" },
  { key: "代理", value: status.value.proxy },
  { key: "证书", value: status.value.certInstalled ? "已就绪" : "未安装" },
  { key: "Mitm", value: status.value.proxyServerRunning ? "运行中" : "未启动" },
  { key: "IP", value: status.value.ip },
  { key: "Session", value: status.value.sessionValid ? "JSESSIONID 有效" : "未缓存" }
]);
const packetItems = computed(() => [
  { key: "proxy", value: status.value.proxy },
  { key: "capture", value: capture.value.running ? "running" : "stopped" },
  { key: "code", value: capture.value.lastCode || "empty" },
  { key: "task", value: task.value.message || "idle" }
]);
const headlineStatus = computed(() => [
  {
    label: "Code 捕获",
    value: capture.value.running ? "运行中" : "未启动",
    tone: capture.value.running ? "success" : "muted"
  },
  {
    label: "系统代理",
    value: status.value.proxy || "未检测",
    tone: status.value.proxyServerRunning ? "success" : "warning"
  },
  {
    label: "证书",
    value: status.value.certInstalled ? "已安装" : "未安装",
    tone: status.value.certInstalled ? "success" : "warning"
  },
  {
    label: "Session",
    value: status.value.sessionValid ? "有效" : "未缓存",
    tone: status.value.sessionValid ? "success" : "warning"
  }
]);

let unsubscribeLog: (() => void) | undefined;
let unsubscribeCode: (() => void) | undefined;
let timer: number | undefined;
let stopResize: (() => void) | undefined;

function ensureOk<T>(result: { ok: boolean; data?: T; error?: string }): T {
  if (!result.ok) throw new Error(result.error || "操作失败");
  return result.data as T;
}

function pushLocalLog(message: string, level: LogEntry["level"] = "info") {
  logs.value.unshift({
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

async function startFridaHook() {
  await runAction(async () => {
    capture.value = ensureOk(await window.signSignIn.code.startFridaHook());
    await refreshAll();
  }, "Frida Hook 已启动");
}

async function applyManualCode() {
  await runAction(async () => {
    capture.value = ensureOk(await window.signSignIn.code.setManualCode(manualCode.value));
    await refreshAll();
  }, "code 已写入");
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
  await runAction(async () => {
    const text = packetItems.value.map((item) => `${item.key}: ${item.value}`).join("\n");
    await navigator.clipboard.writeText(text);
  }, "抓包快照已复制");
}

async function clearPacketSnapshot() {
  await runAction(async () => {
    manualCode.value = "";
    capture.value = ensureOk(await window.signSignIn.code.setManualCode(""));
    await refreshAll();
  }, "抓包快照已清空");
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

function renderIcon(icon: unknown) {
  return h(icon as never, { size: "small" });
}

function changeInput(key: keyof typeof draft, value: string) {
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
    unsubscribeLog = window.signSignIn.log.subscribe((entry) => logs.value.unshift(entry));
    unsubscribeCode = window.signSignIn.code.onCaptured(() => {
      // 抓到 code 后主进程已自动停代理；这里联动当前选中的签到动作。
      // 防止重复触发：仅在没有任务在跑时启动。
      if (task.value.running) return;
      if (isPhotoAction.value && !selectedImage.value) {
        pushLocalLog("已抓到 code，但当前为拍照签到/签退且未选图片，跳过自动执行", "warn");
        return;
      }
      Toast.success("已抓到 code，自动执行签到");
      void startTask();
    });
    await loadConfig();
    await refreshAll();
    timer = window.setInterval(() => {
      refreshAll().catch(() => undefined);
    }, 2500);
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
</script>

<template>
  <main class="app-shell">
    <section class="layout" :style="{ '--log-panel-width': `${logPanelWidth}px` }">
      <aside class="nav">
        <div class="rail-brand">
          <IconUser size="default" />
        </div>
        <TypographyText class-name="rail-hint">SIGN</TypographyText>
        <div class="rail-nav-shell">
          <Button
            class-name="rail-nav-button"
            :theme="page === 'dashboard' ? 'solid' : 'light'"
            type="primary"
            :icon="renderIcon(IconHomeStroked)"
            @click="page = 'dashboard'"
          />
          <Button
            class-name="rail-nav-button"
            :theme="page === 'config' ? 'solid' : 'light'"
            type="primary"
            :icon="renderIcon(IconSetting)"
            @click="page = 'config'"
          />
        </div>
        <div class="rail-spacer" />
        <Button class-name="rail-nav-button" theme="light" type="primary" :icon="renderIcon(IconRefresh)" @click="refreshAll" />
      </aside>

      <section class="main-panel">
        <Banner
          v-if="bootError"
          class-name="free-banner"
          type="danger"
          title="初始化失败"
          :description="bootError"
          :bordered="false"
        />
        <div
          v-else
          class="free-banner notice-banner"
          :title="noticeContent"
        >
          <div class="notice-track">
            <span>{{ noticeContent }}</span>
            <span aria-hidden="true">{{ noticeContent }}</span>
          </div>
        </div>

        <template v-if="page === 'dashboard'">
          <section class="home-panel">
            <header class="title-row">
              <div class="title-pair">
                <TypographyTitle :heading="3">Sign sign in</TypographyTitle>
                <TypographyText>自动化实习签到系统</TypographyText>
              </div>
              <Space>
                <Tag :color="task.running ? 'blue' : 'grey'">{{ task.running ? "TASK RUNNING" : "IDLE" }}</Tag>
                <Tag :color="status.sessionValid ? 'green' : 'orange'">{{ status.sessionValid ? "SESSION READY" : "NEED CODE" }}</Tag>
              </Space>
            </header>

            <Button class-name="qq-strip" theme="light" block :icon="renderIcon(IconCopy)" @click="copyQQGroup">
              <span class="qq-badge">QQ</span>
              <span class="qq-label">交流群</span>
              <span class="qq-divider">/</span>
              <span class="qq-number">859098272</span>
              <span class="qq-hint">点击复制</span>
            </Button>

            <TypographyText class-name="section-label">状态域</TypographyText>
            <section class="monitor-box">
              <div v-for="item in statusItems" :key="item.key" class="status-cell">
                <span>{{ item.key }}</span>
                <strong>{{ item.value }}</strong>
              </div>
            </section>

            <TypographyText class-name="section-label">工具箱</TypographyText>
            <section class="tool-grid">
              <Button theme="light" :icon="renderIcon(IconLink)" @click="openProxySettings">系统代理</Button>
              <Button theme="light" :icon="renderIcon(IconLockStroked)" @click="openCertManager">证书管理</Button>
              <Button theme="light" :icon="renderIcon(IconFile)" @click="page = 'config'">编辑配置</Button>
              <Button theme="light" :icon="renderIcon(IconRefresh)" @click="refreshAll">刷新状态</Button>
              <Button theme="light" :icon="renderIcon(IconCodeStroked)" @click="startFridaHook">Frida Hook</Button>
              <Button theme="light" :icon="renderIcon(IconSendStroked)" disabled>发送反馈</Button>
              <Button theme="light" :icon="renderIcon(IconImage)" @click="importImage">图片管理</Button>
              <Button theme="light" :icon="renderIcon(IconShieldStroked)" disabled>更新中心</Button>
              <Button theme="light" :icon="renderIcon(IconApps)" disabled>AI 与周记</Button>
              <Button theme="light" :icon="renderIcon(IconClock)" disabled>定时打卡</Button>
            </section>

            <div class="reminder-line">提示：小程序会自动关闭，签到请在本软件完成</div>

            <TypographyText class-name="section-label">执行操作（拍照签到签退经纬度不准会导致外勤）</TypographyText>
            <section class="mode-row">
              <RadioGroup
                class-name="mode-group"
                :value="selectedAction"
                :options="actionOptions"
                direction="horizontal"
                @change="(event: any) => (selectedAction = event.target.value)"
              />
            </section>

            <div v-if="isPhotoAction" class="field-row">
              <Select
                :value="selectedImage"
                placeholder="选择签到图片"
                class-name="flex-field"
                :option-list="images.map((image) => ({ value: image.path, label: image.name }))"
                @change="(value: any) => (selectedImage = String(value || ''))"
              />
              <Button theme="light" :icon="renderIcon(IconUpload)" @click="importImage">导入</Button>
              <Button theme="light" type="danger" :disabled="!selectedImage" :icon="renderIcon(IconDeleteStroked)" @click="deleteSelectedImage">删除</Button>
            </div>

            <div class="field-row">
              <Input
                :value="manualCode"
                placeholder="手动粘贴 code 兜底"
                show-clear
                class-name="flex-field"
                @change="(value: string) => (manualCode = value)"
              />
              <Button theme="light" @click="applyManualCode">写入</Button>
            </div>

            <section class="main-actions">
              <Button
                type="primary"
                size="large"
                :class-name="['get-code-btn', capture.running ? 'is-stopping' : ''].filter(Boolean).join(' ')"
                :icon="renderIcon(capture.running ? IconStop : IconCodeStroked)"
                @click="capture.running ? stopCapture() : startCapture()"
              >
                {{ capture.running ? "停止捕获" : "获取code" }}
              </Button>
              <Button
                type="primary"
                size="large"
                class-name="start-btn"
                :loading="loading"
                :disabled="task.running || (isPhotoAction && !selectedImage)"
                :icon="renderIcon(IconPlay)"
                @click="startTask"
              >
                开始执行
              </Button>
              <Button v-if="task.running" theme="outline" :icon="renderIcon(IconStop)" @click="stopTask">停止执行</Button>
            </section>

            <section class="support-row">
              <Button theme="outline">支持作者</Button>
              <Button theme="outline">开源仓库</Button>
            </section>
          </section>
        </template>

        <template v-else>
          <section class="home-panel config-panel">
            <header class="title-row">
              <div class="title-pair">
                <TypographyTitle :heading="3">配置</TypographyTitle>
                <TypographyText>位置、设备、推送与 User-Agent</TypographyText>
              </div>
            </header>
            <Card title="配置中心" :bordered="false" class-name="section-card">
              <div class="config-grid">
                <label>
                  <TypographyText type="secondary">经度</TypographyText>
                  <Input :value="draft.longitude" show-clear @change="(value: string) => changeInput('longitude', value)" />
                </label>
                <label>
                  <TypographyText type="secondary">纬度</TypographyText>
                  <Input :value="draft.latitude" show-clear @change="(value: string) => changeInput('latitude', value)" />
                </label>
                <label>
                  <TypographyText type="secondary">抖动半径（米）</TypographyText>
                  <Input :value="draft.locationJitterMeters" show-clear @change="(value: string) => changeInput('locationJitterMeters', value)" />
                </label>
                <label>
                  <TypographyText type="secondary">平台</TypographyText>
                  <Select :value="draft.platform" :option-list="[{ value: 'android', label: 'android' }, { value: 'ios', label: 'ios' }]" @change="(value: any) => { changeInput('platform', String(value)); regenerateUserAgent(); }" />
                </label>
                <label>
                  <TypographyText type="secondary">品牌</TypographyText>
                  <Input :value="draft.brand" show-clear @change="(value: string) => { changeInput('brand', value); regenerateUserAgent(); }" />
                </label>
                <label>
                  <TypographyText type="secondary">型号</TypographyText>
                  <Input :value="draft.model" show-clear @change="(value: string) => { changeInput('model', value); regenerateUserAgent(); }" />
                </label>
                <label>
                  <TypographyText type="secondary">Android 版本</TypographyText>
                  <Input :value="draft.systemVersion" show-clear @change="(value: string) => { changeInput('systemVersion', value); regenerateUserAgent(); }" />
                </label>
                <label>
                  <TypographyText type="secondary">PushPlus Token</TypographyText>
                  <Input :value="draft.pushplusToken" show-clear @change="(value: string) => changeInput('pushplusToken', value)" />
                </label>
                <label class="wide">
                  <TypographyText type="secondary">User-Agent</TypographyText>
                  <TextArea :value="draft.userAgent" :autosize="{ minRows: 4, maxRows: 6 }" show-clear @change="(value: string) => changeInput('userAgent', value)" />
                </label>
              </div>
              <template #footer>
                <Space wrap>
                  <Button theme="light" :icon="renderIcon(IconRefresh)" @click="regenerateUserAgent">生成 UA</Button>
                  <Button type="primary" :icon="renderIcon(IconSave)" @click="saveConfig">保存配置</Button>
                </Space>
              </template>
            </Card>
          </section>
        </template>
      </section>

      <div class="splitter" title="拖动调整日志宽度" @mousedown="startResize" />

      <aside class="log-panel">
        <section class="terminal terminal-main">
          <header class="terminal-head">
            <Space>
              <IconTerminal />
              <span>&gt;_ SYSTEM LOG</span>
            </Space>
            <Space class="terminal-actions">
              <Button size="small" theme="light" :icon="renderIcon(IconCopy)" @click="copyLogs">复制</Button>
              <Button size="small" theme="light" :icon="renderIcon(IconDeleteStroked)" @click="clearLogs">清空</Button>
            </Space>
          </header>
          <div class="log-list terminal-body">
            <div v-for="entry in logs" :key="`${entry.time}-${entry.message}`" :class="['log-line', entry.level]">
              <span>{{ entry.time }}</span>
              <strong>{{ entry.level }}</strong>
              <p>{{ entry.message }}</p>
            </div>
            <TypographyText v-if="!logs.length" type="tertiary">暂无日志</TypographyText>
          </div>
        </section>

        <section class="terminal packet-terminal">
          <header class="terminal-head packet-head">
            <Space>
              <IconTerminal />
              <span>&gt;_ PACKET SNAPSHOT</span>
            </Space>
            <Space class="terminal-actions">
              <Button size="small" theme="light" :icon="renderIcon(IconCopy)" @click="copyPacketSnapshot">复制</Button>
              <Button size="small" theme="light" :icon="renderIcon(IconDeleteStroked)" @click="clearPacketSnapshot">清空</Button>
            </Space>
          </header>
          <div class="packet-list terminal-body">
            <div v-for="item in packetItems" :key="item.key">
              <span>{{ item.key }}</span>
              <strong>{{ item.value }}</strong>
            </div>
          </div>
        </section>
      </aside>
    </section>
  </main>
</template>
