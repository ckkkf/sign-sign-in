<script setup lang="ts">
import Button from "@kousum/semi-ui-vue/dist/button";
import Input from "@kousum/semi-ui-vue/dist/input";
import Modal from "@kousum/semi-ui-vue/dist/modal";
import Progress from "@kousum/semi-ui-vue/dist/progress";
import Select from "@kousum/semi-ui-vue/dist/select";
import Space from "@kousum/semi-ui-vue/dist/space";
import Spin from "@kousum/semi-ui-vue/dist/spin";
import Tag from "@kousum/semi-ui-vue/dist/tag";
import TextArea from "@kousum/semi-ui-vue/dist/input/textArea";
import Toast from "@kousum/semi-ui-vue/dist/toast";
import { IconDeleteStroked, IconDownload, IconExternalOpen, IconFolderOpen, IconPlay, IconRefresh, IconStop } from "@kousum/semi-icons-vue";
import { computed, onUnmounted, ref, watch } from "vue";
import type { UpdateCheckResult, UpdateDownloadState, UpdateRelease, UpdateSettings } from "@shared/types";
import { ensureOk } from "../utils/api";
import { renderIcon } from "../utils/icons";

const props = defineProps<{ visible: boolean }>();
const emit = defineEmits<{ (event: "close"): void }>();

const loading = ref(false);
const checkResult = ref<UpdateCheckResult | null>(null);
const downloadState = ref<UpdateDownloadState | null>(null);
const expanded = ref<Record<string, boolean>>({});
const downloadedTags = ref<Record<string, boolean>>({});
const loadingMore = ref(false);
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
const hasDownloadState = computed(() => Boolean(downloadState.value?.tag || downloadState.value?.running || latest.value));

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
  try {
    await run(async () => {
      const result = ensureOk(await window.signSignIn.update.check());
      checkResult.value = result;
      settings.value = normalizeSettings(result.settings);
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
    if (downloadState.value.message === "下载完成" && downloadState.value.tag) {
      downloadedTags.value = { ...downloadedTags.value, [downloadState.value.tag]: true };
      syncDownloadedPath(downloadState.value.tag, downloadState.value.filePath);
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

async function download(release: UpdateRelease) {
  await run(async () => {
    downloadState.value = ensureOk(await window.signSignIn.update.download(release.tag));
    startPolling();
  });
}

async function loadMoreHistory() {
  if (!checkResult.value?.historyCursor) return;
  loadingMore.value = true;
  try {
    await run(async () => {
      const result = ensureOk(await window.signSignIn.update.loadMoreHistory(checkResult.value!.historyCursor!, latest.value?.tag));
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

async function pauseOrResume() {
  await run(async () => {
    if (downloadState.value?.running) {
      downloadState.value = ensureOk(await window.signSignIn.update.pause());
    } else {
      downloadState.value = ensureOk(await window.signSignIn.update.resume());
      startPolling();
    }
  });
}

async function stopDownload() {
  await run(async () => {
    downloadState.value = ensureOk(await window.signSignIn.update.stop());
  }, "下载已停止");
}

async function openDownloadDir() {
  await run(async () => ensureOk(await window.signSignIn.update.openDownloadDir()));
}

async function openRelease(release: UpdateRelease) {
  await run(async () => ensureOk(await window.signSignIn.update.openRelease(release.tag)));
}

async function openCompare(release: UpdateRelease) {
  await run(async () => ensureOk(await window.signSignIn.update.openCompare(release.tag)));
}

async function install(release: UpdateRelease) {
  await run(async () => ensureOk(await window.signSignIn.update.install(release.tag)));
}

async function deletePackage(release: UpdateRelease) {
  await run(async () => {
    ensureOk(await window.signSignIn.update.deletePackage(release.tag));
    downloadedTags.value = { ...downloadedTags.value, [release.tag]: false };
    syncDownloadedPath(release.tag, "");
  }, "下载包已删除");
}
</script>

<template>
  <Modal className="compact-tool-modal update-modal" :visible="visible" title="更新中心" :width="780" footer="" @cancel="emit('close')">
    <section class="update-center">
      <header class="update-hero">
        <div>
          <strong>{{ checkResult ? (checkResult.hasUpdate ? "发现新版本" : "已是最新版本") : "未拉取版本信息" }}</strong>
          <span>{{ checkResult ? `当前 ${checkResult.currentVersion} / 最新 ${checkResult.latestVersion}` : "使用 GitHub 官方源检查项目发布版本" }}</span>
        </div>
        <Button type="primary" :loading="loading" :icon="renderIcon(IconRefresh)" @click="checkUpdate">拉取</Button>
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
        <Button theme="light" @click="browseDir">浏览</Button>
        <Button theme="light" :icon="renderIcon(IconFolderOpen)" @click="openDownloadDir">打开</Button>
      </section>

      <Spin :spinning="loading">
        <section v-if="!checkResult" class="update-empty-state">
          <strong>还没有检查更新</strong>
          <span>点击右上角“拉取”后显示最新版本、历史版本和下载操作。</span>
        </section>

        <section v-if="latest" class="release-card latest-card">
          <div class="release-main">
            <div>
              <strong>{{ latest.name || latest.tag }}</strong>
              <span>{{ latest.publishedAt ? new Date(latest.publishedAt).toLocaleString() : "-" }}</span>
            </div>
            <Tag :color="checkResult?.hasUpdate ? 'green' : 'grey'">Latest</Tag>
          </div>
          <div class="release-actions">
            <Space wrap>
              <Button theme="light" :icon="renderIcon(IconExternalOpen)" @click="openRelease(latest)">浏览器</Button>
              <Button type="primary" :icon="renderIcon(IconDownload)" @click="download(latest)">下载</Button>
              <Button theme="light" :disabled="!canInstall(latest)" :icon="renderIcon(IconPlay)" @click="install(latest)">安装</Button>
              <Button theme="light" :icon="renderIcon(IconExternalOpen)" @click="openCompare(latest)">对比</Button>
              <Button theme="light" @click="expanded[latest.tag] = !expanded[latest.tag]">{{ expanded[latest.tag] ? "收起说明" : "展开说明" }}</Button>
            </Space>
          </div>
          <TextArea v-if="expanded[latest.tag]" :value="latest.body || '暂无更新说明'" readonly :autosize="{ minRows: 5, maxRows: 10 }" />
        </section>

        <section v-if="hasDownloadState" class="download-panel">
          <div class="download-meta">
            <strong>{{ downloadState?.message || "未下载" }}</strong>
            <span>{{ downloadState?.fileName || "-" }} · {{ downloadState?.speedText || "-" }} · 剩余 {{ downloadState?.etaText || "-" }}</span>
          </div>
          <Progress :percent="downloadState?.percent || 0" :show-info="true" />
          <Space wrap>
            <Button theme="light" :disabled="!downloadState?.tag" @click="pauseOrResume">{{ downloadState?.running ? "暂停下载" : "继续下载" }}</Button>
            <Button theme="light" type="danger" :disabled="!downloadState?.tag" :icon="renderIcon(IconStop)" @click="stopDownload">停止下载</Button>
          </Space>
        </section>

        <section v-if="checkResult" class="history-list">
          <div class="history-title">历史版本 <span>说明默认折叠</span></div>
          <article v-for="release in releases.slice(1)" :key="release.tag" class="release-card">
            <div class="release-main">
              <div>
                <strong>{{ release.name || release.tag }}</strong>
                <span>{{ release.publishedAt ? new Date(release.publishedAt).toLocaleString() : "-" }}</span>
              </div>
              <span>{{ release.downloadName || "未找到安装包" }}</span>
            </div>
            <Space wrap>
              <Button theme="light" :icon="renderIcon(IconExternalOpen)" @click="openRelease(release)">浏览器</Button>
              <Button theme="light" :icon="renderIcon(IconDownload)" @click="download(release)">下载</Button>
              <Button theme="light" :disabled="!canInstall(release)" :icon="renderIcon(IconPlay)" @click="install(release)">安装</Button>
              <Button theme="light" :icon="renderIcon(IconExternalOpen)" @click="openCompare(release)">对比</Button>
              <Button theme="light" type="danger" :disabled="!canInstall(release)" :icon="renderIcon(IconDeleteStroked)" @click="deletePackage(release)">删除</Button>
              <Button theme="light" @click="expanded[release.tag] = !expanded[release.tag]">{{ expanded[release.tag] ? "收起说明" : "展开说明" }}</Button>
            </Space>
            <TextArea v-if="expanded[release.tag]" :value="release.body || '暂无更新说明'" readonly :autosize="{ minRows: 4, maxRows: 8 }" />
          </article>
          <div v-if="checkResult && releases.length <= 1" class="dialog-empty">暂无历史版本</div>
          <Button v-if="checkResult?.historyCursor" theme="light" :loading="loadingMore" @click="loadMoreHistory">加载更多</Button>
        </section>
      </Spin>
    </section>
  </Modal>
</template>
