<script setup lang="ts">
import Button from "@kousum/semi-ui-vue/dist/button";
import Input from "@kousum/semi-ui-vue/dist/input";
import Modal from "@kousum/semi-ui-vue/dist/modal";
import Select from "@kousum/semi-ui-vue/dist/select";
import Spin from "@kousum/semi-ui-vue/dist/spin";
import Tag from "@kousum/semi-ui-vue/dist/tag";
import TextArea from "@kousum/semi-ui-vue/dist/input/textArea";
import Toast from "@kousum/semi-ui-vue/dist/toast";
import {
  IconChevronDown,
  IconChevronUp,
  IconDeleteStroked,
  IconDownload,
  IconExternalOpen,
  IconFolderOpen,
  IconRefresh,
  IconStop
} from "@kousum/semi-icons-vue";
import { computed, onUnmounted, ref, watch } from "vue";
import type { UpdateCheckResult, UpdateDownloadState, UpdateRelease, UpdateSettings } from "@shared/types";
import { ensureOk } from "../utils/api";
import { stringifyParam, trackClientEvent } from "../utils/analytics";
import { renderIcon } from "../utils/icons";

const props = defineProps<{ visible: boolean }>();
const emit = defineEmits<{ (event: "close"): void }>();

const loading = ref(false);
const checkResult = ref<UpdateCheckResult | null>(null);
const downloadState = ref<UpdateDownloadState | null>(null);
const expanded = ref<Record<string, boolean>>({});
const downloadedTags = ref<Record<string, boolean>>({});
const loadingMore = ref(false);
const historyCollapsed = ref(true);
const downloadDetailVisible = ref(false);
const floatPosition = ref({ x: 28, y: 120 });
const dragging = ref(false);
const autoInstallTag = ref("");
const lastEtaText = ref("");
const lastSpeedText = ref("");
let dragStart:
  | {
      pointerId: number;
      clientX: number;
      clientY: number;
      x: number;
      y: number;
      moved: boolean;
    }
  | null = null;
let timer: number | undefined;

const defaultSettings: UpdateSettings = {
  source: "github",
  customSource: "",
  downloadDir: "",
  sources: { custom: "" },
  download_dir: ""
};
const sourceOptions = [
  { value: "github", label: "GitHub 官方" },
  { value: "gh_proxy", label: "gh-proxy" },
  { value: "gh_proxy_hk", label: "gh-proxy 香港" },
  { value: "gh_proxy_cdn", label: "gh-proxy Fastly" },
  { value: "gh_proxy_edgeone", label: "gh-proxy EdgeOne" },
  { value: "custom", label: "自定义" }
];
const settings = ref<UpdateSettings>({ ...defaultSettings });
const latest = computed(() => checkResult.value?.latestRelease);
const releases = computed(() => [latest.value, ...(checkResult.value?.historyReleases || [])].filter(Boolean) as UpdateRelease[]);
const downloadPercent = computed(() => Math.max(0, Math.min(100, Math.round(Number(downloadState.value?.percent || 0)))));
const hasDownloadTask = computed(() => Boolean(downloadState.value?.tag || downloadState.value?.running || downloadState.value?.paused || downloadPercent.value > 0));
const downloadEtaText = computed(() => displayMetric(downloadState.value?.etaText, lastEtaText.value));
const downloadSpeedText = computed(() => displayMetric(downloadState.value?.speedText, lastSpeedText.value));
const updateStatusText = computed(() => {
  if (!checkResult.value) return "未拉取版本信息";
  return checkResult.value.hasUpdate ? "发现新版本" : "已是最新版本 ✅";
});
const versionSummary = computed(() => (checkResult.value ? `当前 ${checkResult.value.currentVersion} / 最新 ${checkResult.value.latestVersion}` : ""));
const updateStatusClass = computed(() => (checkResult.value ? (checkResult.value.hasUpdate ? "has-update" : "up-to-date") : "idle"));

watch(
  () => props.visible,
  (visible) => {
    if (!visible) {
      stopPolling();
      return;
    }
    void loadSettings();
    void refreshDownloadState();
  }
);

onUnmounted(stopPolling);

async function run<T>(action: () => Promise<T>, success?: string): Promise<T | undefined> {
  try {
    const value = await action();
    if (success) Toast.success(success);
    return value;
  } catch (error) {
    Toast.error(error instanceof Error ? error.message : String(error));
    return undefined;
  }
}

async function checkUpdate() {
  loading.value = true;
  const startedAt = Date.now();
  try {
    await run(async () => {
      const result = ensureOk(await window.signSignIn.update.check());
      checkResult.value = result;
      settings.value = normalizeSettings(result.settings);
      trackClientEvent({
        operType: "UPDATE_CHECK",
        status: "0",
        title: "检查更新",
        responseSummary: `current=${result.currentVersion}, latest=${result.latestVersion}, hasUpdate=${result.hasUpdate}`,
        costTime: Date.now() - startedAt
      });
    });
  } finally {
    loading.value = false;
  }
}

async function loadSettings() {
  await run(async () => {
    settings.value = normalizeSettings(ensureOk(await window.signSignIn.update.getSettings()));
  });
}

function normalizeSettings(next?: UpdateSettings): UpdateSettings {
  return {
    ...defaultSettings,
    ...(next || {}),
    source: next?.source || "github",
    customSource: next?.customSource || next?.sources?.custom || "",
    downloadDir: next?.downloadDir || next?.download_dir || "",
    sources: { custom: next?.customSource || next?.sources?.custom || "" },
    download_dir: next?.downloadDir || next?.download_dir || ""
  };
}

async function saveSettings(partial: Partial<UpdateSettings>) {
  await run(async () => {
    const next = ensureOk(await window.signSignIn.update.saveSettings(partial));
    settings.value = normalizeSettings(next);
    if (checkResult.value) checkResult.value.settings = settings.value;
  });
}

async function browseDir() {
  await run(async () => {
    const next = ensureOk(await window.signSignIn.update.browseDownloadDir());
    settings.value = normalizeSettings(next);
    if (checkResult.value) checkResult.value.settings = settings.value;
  });
}

async function refreshDownloadState() {
  await run(async () => {
    const previous = downloadState.value;
    downloadState.value = ensureOk(await window.signSignIn.update.getDownloadState());
    cacheDownloadMetrics();
    if (downloadState.value.message === "下载完成" && downloadState.value.tag) {
      downloadedTags.value = { ...downloadedTags.value, [downloadState.value.tag]: true };
      syncDownloadedPath(downloadState.value.tag, downloadState.value.filePath);
      if (autoInstallTag.value === downloadState.value.tag) {
        const release = releases.value.find((item) => item.tag === downloadState.value?.tag);
        autoInstallTag.value = "";
        if (release) {
          await install({ ...release, downloadedPath: downloadState.value.filePath });
        }
      }
    }
    if (previous?.running && !downloadState.value.running) stopPolling();
    if (downloadState.value.running) startPolling();
  });
}

function startPolling() {
  if (timer) return;
  timer = window.setInterval(() => {
    refreshDownloadState().catch(() => undefined);
  }, 800);
}

function stopPolling() {
  if (timer) window.clearInterval(timer);
  timer = undefined;
}

function clampFloatPosition(x: number, y: number) {
  const size = downloadDetailVisible.value ? { width: 324, height: 72 } : { width: 72, height: 72 };
  const maxX = Math.max(8, window.innerWidth - size.width - 8);
  const maxY = Math.max(8, window.innerHeight - size.height - 8);
  return {
    x: Math.min(Math.max(8, x), maxX),
    y: Math.min(Math.max(8, y), maxY)
  };
}

function onFloatPointerDown(event: PointerEvent) {
  const target = event.currentTarget as HTMLElement;
  target.setPointerCapture(event.pointerId);
  dragging.value = true;
  dragStart = {
    pointerId: event.pointerId,
    clientX: event.clientX,
    clientY: event.clientY,
    x: floatPosition.value.x,
    y: floatPosition.value.y,
    moved: false
  };
}

function onFloatPointerMove(event: PointerEvent) {
  if (!dragStart || dragStart.pointerId !== event.pointerId) return;
  const dx = event.clientX - dragStart.clientX;
  const dy = event.clientY - dragStart.clientY;
  if (Math.abs(dx) + Math.abs(dy) > 4) dragStart.moved = true;
  floatPosition.value = clampFloatPosition(dragStart.x + dx, dragStart.y + dy);
}

function onFloatPointerUp(event: PointerEvent) {
  const target = event.currentTarget as HTMLElement;
  try {
    if (dragStart?.pointerId === event.pointerId && target.hasPointerCapture(event.pointerId)) {
      target.releasePointerCapture(event.pointerId);
    }
  } catch {
    // Pointer capture release is best-effort; do not block click behavior.
  }
  dragStart = null;
  dragging.value = false;
}

async function download(release: UpdateRelease) {
  await run(async () => {
    autoInstallTag.value = release.tag;
    downloadState.value = ensureOk(await window.signSignIn.update.download(release.tag));
    cacheDownloadMetrics();
    trackClientEvent({
      operType: "UPDATE_DOWNLOAD",
      status: "0",
      title: "下载更新包",
      requestParam: stringifyParam({ tag: release.tag, name: release.name })
    });
    downloadDetailVisible.value = true;
    startPolling();
  });
}

function isReleaseDownloading(release: UpdateRelease) {
  return Boolean(downloadState.value?.tag === release.tag && (downloadState.value.running || downloadState.value.paused));
}

function releasePercent(release: UpdateRelease) {
  if (downloadState.value?.tag !== release.tag) return 0;
  return Math.max(0, Math.min(100, Math.round(Number(downloadState.value.percent || 0))));
}

async function loadMoreHistory() {
  if (!checkResult.value?.historyCursor) return;
  loadingMore.value = true;
  try {
    await run(async () => {
      const cursor = { start: Number(checkResult.value!.historyCursor!.start || 1) };
      const result = ensureOk(await window.signSignIn.update.loadMoreHistory(cursor, latest.value?.tag));
      const seen = new Set(checkResult.value!.historyReleases.map((release) => release.tag));
      checkResult.value!.historyReleases = [
        ...checkResult.value!.historyReleases,
        ...result.releases.filter((release) => !seen.has(release.tag))
      ];
      checkResult.value!.historyCursor = result.historyCursor;
    });
  } finally {
    loadingMore.value = false;
  }
}

function syncDownloadedPath(tag: string, filePath: string) {
  if (!checkResult.value) return;
  if (checkResult.value.latestRelease?.tag === tag) {
    checkResult.value.latestRelease.downloadedPath = filePath;
  }
  checkResult.value.historyReleases = checkResult.value.historyReleases.map((release) =>
    release.tag === tag ? { ...release, downloadedPath: filePath } : release
  );
}

function canInstall(release: UpdateRelease) {
  return Boolean(release.downloadedPath || downloadedTags.value[release.tag]);
}

function installButtonText(release: UpdateRelease) {
  if (isReleaseDownloading(release)) return "停止";
  return canInstall(release) ? "安装" : "下载安装";
}

async function downloadOrInstall(release: UpdateRelease) {
  if (isReleaseDownloading(release)) {
    await stopDownload();
    return;
  }
  if (canInstall(release)) {
    await install(release);
    return;
  }
  await download(release);
}

async function pauseOrResume() {
  await run(async () => {
    if (downloadState.value?.running) {
      downloadState.value = ensureOk(await window.signSignIn.update.pause());
    } else {
      downloadState.value = ensureOk(await window.signSignIn.update.resume());
      startPolling();
    }
    cacheDownloadMetrics();
  });
}

async function stopDownload() {
  await run(async () => {
    downloadState.value = ensureOk(await window.signSignIn.update.stop());
    lastEtaText.value = "";
    lastSpeedText.value = "";
    autoInstallTag.value = "";
    downloadDetailVisible.value = false;
  }, "下载已停止");
}

async function pauseOrResumeFromFloat() {
  await pauseOrResume();
  downloadDetailVisible.value = true;
}

async function stopDownloadFromFloat() {
  await stopDownload();
}

async function openDownloadDir() {
  await run(async () => ensureOk(await window.signSignIn.update.openDownloadDir()));
}

async function openRelease(release: UpdateRelease) {
  await run(async () => ensureOk(await window.signSignIn.update.openRelease(release.tag)));
}

async function install(release: UpdateRelease) {
  await run(async () => {
    ensureOk(await window.signSignIn.update.install(release.tag));
    trackClientEvent({
      operType: "UPDATE_INSTALL",
      status: "0",
      title: "安装更新包",
      requestParam: stringifyParam({ tag: release.tag, name: release.name })
    });
  });
}

async function deletePackage(release: UpdateRelease) {
  await run(async () => {
    ensureOk(await window.signSignIn.update.deletePackage(release.tag));
    downloadedTags.value = { ...downloadedTags.value, [release.tag]: false };
    syncDownloadedPath(release.tag, "");
  }, "下载包已删除");
}

function cacheDownloadMetrics() {
  if (downloadState.value?.etaText && downloadState.value.etaText !== "-") lastEtaText.value = downloadState.value.etaText;
  if (downloadState.value?.speedText && downloadState.value.speedText !== "-") lastSpeedText.value = downloadState.value.speedText;
}

function displayMetric(value: string | undefined, fallback: string) {
  return value && value !== "-" ? value : fallback || "-";
}

function releaseTitleParts(release: UpdateRelease) {
  const title = release.name || release.tag;
  const match = title.match(/v?\d+(?:\.\d+){1,3}(?:[-+][0-9A-Za-z.-]+)?/);
  if (!match || match.index === undefined) return { before: title, version: "", after: "" };
  return {
    before: title.slice(0, match.index),
    version: match[0],
    after: title.slice(match.index + match[0].length)
  };
}
</script>

<template>
  <Modal className="compact-tool-modal update-modal" :visible="visible" title="更新中心" :width="720" footer="" @cancel="emit('close')">
    <section class="update-center">
      <header :class="['update-hero', updateStatusClass]">
        <div>
          <strong>{{ updateStatusText }} <span v-if="versionSummary" class="version-inline">{{ versionSummary }}</span></strong>
          <span v-if="!checkResult">使用 GitHub 官方源检查项目发布版本</span>
        </div>
        <Button type="primary" :loading="loading" :icon="renderIcon(IconRefresh)" @click="checkUpdate">检查更新</Button>
      </header>

      <section :class="['update-settings', { 'has-custom-source': settings.source === 'custom' }]">
        <label>
          <span>更新源</span>
          <Select
            :value="settings.source || 'github'"
            :option-list="sourceOptions"
            @change="(value: any) => saveSettings({ source: String(value) })"
          />
        </label>
        <label v-if="settings.source === 'custom'" class="custom-source-field">
          <span>自定义源</span>
          <Input
            :value="settings.customSource"
            placeholder="支持 {url} 模板"
            @change="(value: string) => saveSettings({ customSource: value })"
          />
        </label>
        <label class="download-dir-field">
          <span>下载目录</span>
          <Input className="download-dir-input" :value="settings.downloadDir || ''" readonly />
        </label>
        <Button theme="light" @click="browseDir">选择目录</Button>
        <Button theme="light" :icon="renderIcon(IconFolderOpen)" @click="openDownloadDir">打开目录</Button>
      </section>

      <Spin :spinning="loading">
        <section v-if="!checkResult" class="update-empty-state">
          <strong>还没有检查更新</strong>
          <span>点击右上角“检查更新”后显示最新版本、历史版本和下载操作。</span>
        </section>

        <section v-if="latest" class="release-card latest-card">
          <div class="release-main">
            <div class="release-title-line">
              <strong>
                {{ releaseTitleParts(latest).before }}<span v-if="releaseTitleParts(latest).version" class="release-version-highlight">{{ releaseTitleParts(latest).version }}</span>{{ releaseTitleParts(latest).after }}
              </strong>
              <span>{{ latest.publishedAt ? new Date(latest.publishedAt).toLocaleString() : "-" }}</span>
              <Button theme="borderless" size="small" :icon="renderIcon(IconExternalOpen)" @click="openRelease(latest)" />
            </div>
            <Tag :color="checkResult?.hasUpdate ? 'green' : 'grey'">Latest</Tag>
          </div>
          <div class="release-actions">
            <div class="release-actions-main">
              <Button :type="isReleaseDownloading(latest) ? 'danger' : 'primary'" :icon="renderIcon(isReleaseDownloading(latest) ? IconStop : IconDownload)" @click="downloadOrInstall(latest)">{{ installButtonText(latest) }}</Button>
              <Button theme="light" :icon="renderIcon(IconFolderOpen)" @click="openDownloadDir">打开目录</Button>
            </div>
            <Button className="release-icon-button" theme="borderless" :icon="renderIcon(expanded[latest.tag] ? IconChevronUp : IconChevronDown)" @click="expanded[latest.tag] = !expanded[latest.tag]" />
          </div>
          <div v-if="isReleaseDownloading(latest)" :class="['release-inline-progress', { running: downloadState?.running, paused: downloadState?.paused }]">
            <span>{{ downloadState?.message || "下载中" }}</span>
            <div class="release-progress-track"><i :style="{ width: `${releasePercent(latest)}%` }" /></div>
            <strong>{{ releasePercent(latest) }}%</strong>
          </div>
          <TextArea v-if="expanded[latest.tag]" className="release-body-textarea" :value="latest.body || '暂无更新说明'" readonly :autosize="{ minRows: 5, maxRows: 10 }" />
        </section>

        <section v-if="checkResult" class="history-list">
          <button class="history-title history-toggle" type="button" @click="historyCollapsed = !historyCollapsed">
            <span>历史版本</span>
            <strong>{{ historyCollapsed ? "展开" : "收起" }}</strong>
          </button>
          <article v-for="release in historyCollapsed ? [] : releases.slice(1)" :key="release.tag" class="release-card">
            <div class="release-main">
              <div class="release-title-line">
                <strong>
                  {{ releaseTitleParts(release).before }}<span v-if="releaseTitleParts(release).version" class="release-version-highlight">{{ releaseTitleParts(release).version }}</span>{{ releaseTitleParts(release).after }}
                </strong>
                <span>{{ release.publishedAt ? new Date(release.publishedAt).toLocaleString() : "-" }}</span>
                <Button theme="borderless" size="small" :icon="renderIcon(IconExternalOpen)" @click="openRelease(release)" />
              </div>
              <span>{{ release.downloadName || "未找到安装包" }}</span>
            </div>
            <div class="release-actions">
              <div class="release-actions-main">
              <Button :theme="isReleaseDownloading(release) ? 'solid' : 'light'" :type="isReleaseDownloading(release) ? 'danger' : 'primary'" :icon="renderIcon(isReleaseDownloading(release) ? IconStop : IconDownload)" @click="downloadOrInstall(release)">{{ installButtonText(release) }}</Button>
              <Button theme="light" :icon="renderIcon(IconFolderOpen)" @click="openDownloadDir">打开目录</Button>
              <Button theme="light" type="danger" :disabled="!canInstall(release)" :icon="renderIcon(IconDeleteStroked)" @click="deletePackage(release)">删除</Button>
              </div>
              <Button className="release-icon-button" theme="borderless" :icon="renderIcon(expanded[release.tag] ? IconChevronUp : IconChevronDown)" @click="expanded[release.tag] = !expanded[release.tag]" />
            </div>
            <div v-if="isReleaseDownloading(release)" :class="['release-inline-progress', { running: downloadState?.running, paused: downloadState?.paused }]">
              <span>{{ downloadState?.message || "下载中" }}</span>
              <div class="release-progress-track"><i :style="{ width: `${releasePercent(release)}%` }" /></div>
              <strong>{{ releasePercent(release) }}%</strong>
            </div>
            <TextArea v-if="expanded[release.tag]" className="release-body-textarea" :value="release.body || '暂无更新说明'" readonly :autosize="{ minRows: 4, maxRows: 8 }" />
          </article>
          <div v-if="checkResult && releases.length <= 1" class="dialog-empty">暂无历史版本</div>
          <Button v-if="!historyCollapsed && checkResult?.historyCursor" theme="light" :loading="loadingMore" @click="loadMoreHistory">加载更多</Button>
        </section>
      </Spin>
    </section>
  </Modal>

  <div
    v-if="hasDownloadTask"
    :class="[
      'download-float',
      {
        expanded: downloadDetailVisible,
        dragging,
        running: downloadState?.running,
        paused: downloadState?.paused
      }
    ]"
    :style="{ left: `${floatPosition.x}px`, top: `${floatPosition.y}px` }"
  >
    <div
      class="download-orb"
      :style="{ '--progress': downloadPercent }"
      @pointerdown="onFloatPointerDown"
      @pointermove="onFloatPointerMove"
      @pointerup="onFloatPointerUp"
      @pointercancel="onFloatPointerUp"
      @click.stop="downloadDetailVisible = !downloadDetailVisible"
    >
      <svg viewBox="0 0 72 72" aria-hidden="true">
        <circle class="download-orb-track" cx="36" cy="36" r="31" />
        <circle class="download-orb-progress" cx="36" cy="36" r="31" />
      </svg>
      <strong>{{ downloadPercent }}%</strong>
    </div>
    <section v-if="downloadDetailVisible" class="download-float-detail">
      <div class="download-meta">
        <strong>{{ downloadState?.message || "下载中" }}</strong>
        <span>{{ downloadState?.fileName || "-" }}</span>
        <span>{{ downloadSpeedText }} · 剩余 {{ downloadEtaText }}</span>
      </div>
      <div class="download-actions">
        <Button theme="light" size="small" :disabled="!downloadState?.tag" @click.stop="pauseOrResumeFromFloat">{{ downloadState?.running ? "暂停" : "继续" }}</Button>
        <Button theme="light" size="small" type="danger" :disabled="!downloadState?.tag" :icon="renderIcon(IconStop)" @click.stop="stopDownloadFromFloat">停止</Button>
      </div>
    </section>
  </div>
</template>
