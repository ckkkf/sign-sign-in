import axios from "axios";
import { app, dialog, shell } from "electron";
import { createWriteStream, existsSync, readFileSync, renameSync, statSync, unlinkSync, writeFileSync } from "node:fs";
import { homedir, tmpdir } from "node:os";
import { basename, extname, join } from "node:path";
import { unescape as htmlUnescape } from "node:querystring";
import { spawn } from "node:child_process";
import type {
  UpdateCheckResult,
  UpdateDownloadState,
  UpdateRelease,
  UpdateSettings,
  UpdateSourceOption
} from "@shared/types";
import { ensureDir, ensureParent, getProjectRoot, getUserRoot } from "./paths";
import { logger } from "./logger";
import { analyticsService } from "./analyticsService";

const PROJECT_GITHUB = "https://github.com/ckkkf/sign-sign-in";
const OWNER = "ckkkf";
const REPO = "sign-sign-in";
const PAGE_SIZE = 5;

const SOURCES: UpdateSourceOption[] = [
  { key: "github", label: "GitHub 官方", value: "" },
  { key: "gh_proxy", label: "gh-proxy", value: "https://gh-proxy.org/{url}" },
  { key: "gh_proxy_hk", label: "gh-proxy 香港", value: "https://hk.gh-proxy.org/{url}" },
  { key: "gh_proxy_cdn", label: "gh-proxy Fastly", value: "https://cdn.gh-proxy.org/{url}" },
  { key: "gh_proxy_edgeone", label: "gh-proxy EdgeOne", value: "https://edgeone.gh-proxy.org/{url}" },
  { key: "custom", label: "自定义", value: "" }
];

const emptyDownloadState: UpdateDownloadState = {
  running: false,
  paused: false,
  tag: "",
  fileName: "",
  filePath: "",
  receivedBytes: 0,
  totalBytes: 0,
  percent: 0,
  speedText: "-",
  etaText: "-",
  message: "未下载"
};

type GitHubAsset = {
  name: string;
  browser_download_url: string;
  size?: number;
};

type GitHubRelease = {
  tag_name: string;
  name?: string;
  body?: string;
  published_at?: string;
  html_url?: string;
  draft?: boolean;
  prerelease?: boolean;
  assets?: GitHubAsset[];
};

type HtmlRelease = GitHubRelease & {
  raw_download_url?: string;
  download_name?: string;
};

function settingsPath(): string {
  return join(getUserRoot(), "cache", "update_settings.json");
}

function assetCachePath(): string {
  return join(getUserRoot(), "cache", "update_asset_cache.json");
}

function defaultDownloadDir(): string {
  return join(homedir(), "Downloads", "sign-sign-in");
}

function readPackageVersion(): string {
  try {
    const pkg = JSON.parse(readFileSync(join(getProjectRoot(), "package.json"), "utf-8"));
    return `v${pkg.version || "1.3.1"}`;
  } catch {
    return "v1.3.1";
  }
}

function versionTuple(version: string): number[] {
  const parts = version.match(/\d+/g) || [];
  return parts.map((part) => Number(part));
}

function compareVersion(a: string, b: string): number {
  const left = versionTuple(a);
  const right = versionTuple(b);
  const length = Math.max(left.length, right.length);
  for (let index = 0; index < length; index += 1) {
    const diff = (left[index] || 0) - (right[index] || 0);
    if (diff !== 0) return diff;
  }
  return 0;
}

function chooseAsset(assets: GitHubAsset[] = []): GitHubAsset | undefined {
  if (!assets.length) return undefined;
  const lower = (asset: GitHubAsset) => asset.name.toLowerCase();
  const matchers =
    process.platform === "win32"
      ? [
          (asset: GitHubAsset) => lower(asset).includes("windows") && lower(asset).endsWith(".zip"),
          (asset: GitHubAsset) => lower(asset).includes("windows") && lower(asset).endsWith(".exe"),
          (asset: GitHubAsset) => lower(asset).endsWith(".exe"),
          (asset: GitHubAsset) => lower(asset).endsWith(".zip") && !lower(asset).includes("mac")
        ]
      : process.platform === "darwin"
        ? [
            (asset: GitHubAsset) => lower(asset).endsWith(".dmg"),
            (asset: GitHubAsset) => lower(asset).endsWith(".pkg"),
            (asset: GitHubAsset) => lower(asset).includes("mac") && lower(asset).endsWith(".zip")
          ]
        : [(asset: GitHubAsset) => lower(asset).endsWith(".zip"), (asset: GitHubAsset) => lower(asset).endsWith(".exe")];
  for (const matcher of matchers) {
    const found = assets.find(matcher);
    if (found) return found;
  }
  return assets[0];
}

function formatBytesPerSecond(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(2)} MB/s`;
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} KB/s`;
  return `${Math.max(0, Math.round(bytes))} B/s`;
}

function formatEta(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) return "-";
  if (seconds < 60) return `${Math.ceil(seconds)} 秒`;
  return `${Math.ceil(seconds / 60)} 分钟`;
}

function installKindFor(name: string): string {
  const ext = extname(name || "").replace(".", "").toLowerCase();
  return ext || "unknown";
}

function installSupportedFor(kind: string): boolean {
  return ["zip", "exe", "dmg", "pkg", "app"].includes(kind);
}

function isPartFile(filePath: string): boolean {
  return filePath.toLowerCase().endsWith(".part");
}

function stripHtml(value: string): string {
  return String(value || "")
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<\/p\s*>/gi, "\n\n")
    .replace(/<\/li\s*>/gi, "\n")
    .replace(/<li[^>]*>/gi, "- ")
    .replace(/<[^>]+>/g, "")
    .replace(/\r\n?/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

export class UpdateService {
  private releases: UpdateRelease[] = [];
  private downloadedFiles = new Map<string, string>();
  private abortController: AbortController | null = null;
  private downloadState: UpdateDownloadState = { ...emptyDownloadState };

  private trackDownload(payload: {
    title: string;
    status?: "0" | "1";
    tag?: string;
    fileName?: string;
    filePath?: string;
    receivedBytes?: number;
    totalBytes?: number;
    errorMsg?: string;
    costTime?: number;
  }): void {
    analyticsService.track({
      operType: "UPDATE_DOWNLOAD_TASK",
      status: payload.status || "0",
      title: payload.title,
      requestUrl: "update://download",
      requestParam: JSON.stringify({
        tag: payload.tag || this.downloadState.tag,
        fileName: payload.fileName || this.downloadState.fileName
      }),
      responseSummary: JSON.stringify({
        filePath: payload.filePath || this.downloadState.filePath,
        receivedBytes: payload.receivedBytes ?? this.downloadState.receivedBytes,
        totalBytes: payload.totalBytes ?? this.downloadState.totalBytes,
        percent: this.downloadState.percent
      }),
      errorMsg: payload.errorMsg,
      costTime: payload.costTime
    }).catch(() => undefined);
  }

  getSettings(): UpdateSettings {
    try {
      if (existsSync(settingsPath())) {
        const raw = JSON.parse(readFileSync(settingsPath(), "utf-8"));
        const customSource = raw.sources?.custom || raw.customSource || "";
        const downloadDir = raw.download_dir || raw.downloadDir || defaultDownloadDir();
        const source = raw.source === "gh_proxy_edgeone" && !raw.version ? "github" : raw.source || "github";
        return {
          source,
          customSource,
          downloadDir,
          sources: { custom: customSource },
          download_dir: downloadDir
        };
      }
    } catch {
      // fall through to defaults
    }
    const downloadDir = defaultDownloadDir();
    return { source: "github", customSource: "", downloadDir, sources: { custom: "" }, download_dir: downloadDir };
  }

  saveSettings(settings: Partial<UpdateSettings>): UpdateSettings {
    const current = this.getSettings();
    const customSource = settings.customSource ?? settings.sources?.custom ?? current.customSource;
    const downloadDir = settings.downloadDir ?? settings.download_dir ?? current.downloadDir;
    const next: UpdateSettings = {
      ...current,
      ...settings,
      customSource,
      downloadDir,
      sources: { custom: customSource },
      download_dir: downloadDir
    };
    const persisted = {
      version: 2,
      source: next.source,
      sources: { custom: customSource },
      download_dir: downloadDir
    };
    ensureParent(settingsPath());
    writeFileSync(settingsPath(), JSON.stringify(persisted, null, 2), "utf-8");
    this.releases = this.releases.map((release) => this.withSource(release, next));
    return next;
  }

  async browseDownloadDir(): Promise<UpdateSettings> {
    const result = await dialog.showOpenDialog({ properties: ["openDirectory", "createDirectory"] });
    if (result.canceled || !result.filePaths[0]) return this.getSettings();
    return this.saveSettings({ downloadDir: result.filePaths[0], download_dir: result.filePaths[0] });
  }

  async check(): Promise<UpdateCheckResult> {
    const settings = this.getSettings();
    this.releases = await this.fetchReleases(settings);

    const currentVersion = readPackageVersion();
    const latestRelease = this.releases[0];
    const latestVersion = latestRelease?.tag || currentVersion;
    const history = this.releases.slice(1, 1 + PAGE_SIZE);
    return {
      currentVersion,
      latestVersion,
      hasUpdate: Boolean(latestRelease && compareVersion(latestRelease.tag, currentVersion) > 0),
      latestRelease,
      historyReleases: history,
      historyCursor: this.releases.length > 1 + PAGE_SIZE ? { start: 1 + PAGE_SIZE } : null,
      settings,
      sources: SOURCES
    };
  }

  private async fetchReleases(settings: UpdateSettings): Promise<UpdateRelease[]> {
    try {
      const response = await axios.get<GitHubRelease[]>(`https://api.github.com/repos/${OWNER}/${REPO}/releases`, {
        timeout: 20000,
        headers: {
          Accept: "application/vnd.github+json",
          "User-Agent": "SignSignIn-Electron"
        }
      });
      return response.data
        .filter((release) => !release.draft && !release.prerelease)
        .map((release) => this.mapRelease(release, settings));
    } catch (error) {
      const status = axios.isAxiosError(error) ? error.response?.status : undefined;
      logger.warn(`GitHub API 拉取失败${status ? `(${status})` : ""}，切换到 releases 页面解析`);
      return this.fetchReleasesFromHtml(settings);
    }
  }

  private async fetchReleasesFromHtml(settings: UpdateSettings): Promise<UpdateRelease[]> {
    const releases: HtmlRelease[] = [];
    let page = 1;
    let emptyPages = 0;
    while (releases.length < 1 + PAGE_SIZE * 3 && emptyPages < 2) {
      const html = await this.requestText(`https://github.com/${OWNER}/${REPO}/releases${page > 1 ? `?page=${page}` : ""}`, settings);
      const pageReleases = this.parseReleasesPage(html, page === 1);
      if (!pageReleases.length) emptyPages += 1;
      for (const release of pageReleases) {
        if (!releases.some((item) => item.tag_name === release.tag_name)) releases.push(release);
      }
      page += 1;
    }
    return releases.map((release) => this.mapRelease(release, settings));
  }

  private async requestText(url: string, settings: UpdateSettings): Promise<string> {
    const candidates = this.requestCandidates(url, settings);
    let lastError: unknown;
    for (const candidate of candidates) {
      try {
        const response = await axios.get<string>(candidate, {
          timeout: 20000,
          responseType: "text",
          headers: {
            "User-Agent": "Mozilla/5.0 SignSignIn-Electron",
            Accept: "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
          }
        });
        return String(response.data || "");
      } catch (error) {
        lastError = error;
      }
    }
    throw lastError instanceof Error ? lastError : new Error("请求 GitHub releases 页面失败");
  }

  private requestCandidates(url: string, settings: UpdateSettings): string[] {
    const prefixed = this.applySourceToUrl(url, settings);
    return prefixed && prefixed !== url ? [prefixed, url] : [url];
  }

  private parseReleasesPage(html: string, resolveFirstAsset: boolean): HtmlRelease[] {
    const matches = Array.from(
      html.matchAll(new RegExp(`href="(?:https://github\\.com)?/${OWNER}/${REPO}/releases/tag/([^"#?]+)"[^>]*>(.*?)</a>`, "gis"))
    );
    const releases: HtmlRelease[] = [];
    for (let index = 0; index < matches.length; index += 1) {
      const match = matches[index];
      const start = match.index || 0;
      const end = index + 1 < matches.length ? matches[index + 1].index || html.length : html.length;
      const block = html.slice(start, end);
      const lowered = block.toLowerCase().replace(/\s+/g, " ");
      if (lowered.includes(">draft<") || lowered.includes(">pre-release<") || lowered.includes(">pre release<")) continue;
      const tag = decodeURIComponent(match[1].trim());
      const title = stripHtml(match[2]) || tag;
      const body =
        stripHtml(block.match(/<div[^>]*class="[^"]*markdown-body[^"]*"[^>]*>(.*?)<\/div>/is)?.[1] || "") || "暂无更新说明";
      const publishedAt =
        block.match(/<relative-time[^>]*datetime="([^"]+)"/i)?.[1] ||
        block.match(/<time[^>]*datetime="([^"]+)"/i)?.[1] ||
        "";
      const assets = resolveFirstAsset && releases.length === 0 ? this.parseAssets(block) : [];
      const asset = chooseAsset(assets);
      releases.push({
        tag_name: tag,
        name: title,
        body,
        published_at: publishedAt,
        html_url: `${PROJECT_GITHUB}/releases/tag/${tag}`,
        assets: asset ? [asset] : [],
        raw_download_url: asset?.browser_download_url,
        download_name: asset?.name
      });
    }
    return releases;
  }

  private parseAssets(html: string): GitHubAsset[] {
    const assets: GitHubAsset[] = [];
    const seen = new Set<string>();
    for (const match of html.matchAll(/href="([^"]+\/releases\/download\/[^"]+)"/gi)) {
      let href = match[1].replace(/&amp;/g, "&");
      if (href.startsWith("/")) href = `https://github.com${href}`;
      if (seen.has(href)) continue;
      seen.add(href);
      assets.push({ name: basename(new URL(href).pathname), browser_download_url: href });
    }
    return assets;
  }

  loadMoreHistory(cursor: { start: number }, excludeTag?: string): { releases: UpdateRelease[]; historyCursor: { start: number } | null } {
    const start = Math.max(1, Number(cursor?.start || 1));
    const all = excludeTag ? this.releases.filter((release) => release.tag !== excludeTag) : this.releases;
    const releases = all.slice(start, start + PAGE_SIZE);
    const nextStart = start + PAGE_SIZE;
    return {
      releases,
      historyCursor: all.length > nextStart ? { start: nextStart } : null
    };
  }

  getDownloadState(): UpdateDownloadState {
    return { ...this.downloadState };
  }

  async download(tag: string): Promise<UpdateDownloadState> {
    if (this.downloadState.running) throw new Error("已有下载任务正在进行");
    const previousState = this.downloadState.tag === tag ? this.downloadState : null;
    const release = await this.ensureReleaseAsset(tag);
    const settings = this.getSettings();
    ensureDir(settings.downloadDir);
    const fileName = release.downloadName || basename(release.rawDownloadUrl);
    const filePath = join(settings.downloadDir, fileName);
    const partPath = `${filePath}.part`;
    const downloadedBytes = existsSync(partPath) ? statSync(partPath).size : 0;
    const totalBytes = previousState && previousState.filePath === filePath ? previousState.totalBytes : 0;
    const percent = totalBytes ? Math.min(100, (downloadedBytes / totalBytes) * 100) : 0;
    this.abortController = new AbortController();
    this.downloadState = {
      ...emptyDownloadState,
      running: true,
      tag,
      fileName,
      filePath,
      receivedBytes: downloadedBytes,
      totalBytes,
      percent,
      speedText: previousState?.speedText || emptyDownloadState.speedText,
      etaText: previousState?.etaText || emptyDownloadState.etaText,
      message: downloadedBytes ? "继续下载中" : "下载中"
    };

    void this.runDownload(release.downloadUrl, partPath, filePath, downloadedBytes).catch((error) => {
      const message = error instanceof Error ? error.message : String(error);
      if (message === "canceled") return;
      logger.error(`下载更新失败：${message}`);
      this.downloadState = { ...this.downloadState, running: false, paused: false, message };
      this.abortController = null;
      this.trackDownload({
        title: "更新包下载失败",
        status: "1",
        tag,
        fileName,
        filePath,
        errorMsg: message
      });
    });

    return this.getDownloadState();
  }

  pause(): UpdateDownloadState {
    if (!this.downloadState.running) return this.getDownloadState();
    this.abortController?.abort();
    this.downloadState = { ...this.downloadState, running: false, paused: true, message: "已暂停" };
    this.abortController = null;
    this.trackDownload({ title: "暂停更新包下载" });
    return this.getDownloadState();
  }

  async resume(): Promise<UpdateDownloadState> {
    if (!this.downloadState.paused || !this.downloadState.tag) return this.getDownloadState();
    const tag = this.downloadState.tag;
    this.downloadState = { ...this.downloadState, paused: false };
    return this.download(tag);
  }

  stop(): UpdateDownloadState {
    this.abortController?.abort();
    const filePath = this.downloadState.filePath;
    const partPath = filePath ? `${filePath}.part` : "";
    if (partPath && existsSync(partPath)) unlinkSync(partPath);
    this.abortController = null;
    this.trackDownload({ title: "停止更新包下载" });
    this.downloadState = { ...emptyDownloadState, message: "已停止" };
    return this.getDownloadState();
  }

  async openDownloadDir(): Promise<boolean> {
    await shell.openPath(this.getSettings().downloadDir);
    return true;
  }

  async openRelease(tag: string): Promise<boolean> {
    await shell.openExternal(this.findRelease(tag).htmlUrl);
    return true;
  }

  async openCompare(tag: string): Promise<boolean> {
    await shell.openExternal(this.findRelease(tag).compareUrl);
    return true;
  }

  async deletePackage(tag: string): Promise<boolean> {
    const file = this.downloadedFiles.get(tag);
    if (file && existsSync(file)) unlinkSync(file);
    this.downloadedFiles.delete(tag);
    this.releases = this.releases.map((release) => (release.tag === tag ? { ...release, downloadedPath: undefined } : release));
    return true;
  }

  async install(tag: string): Promise<boolean> {
    const resolved = await this.resolveDownloadedPackage(tag);
    if (!resolved.filePath) {
      if (resolved.partPath) throw new Error("安装包仍在下载中，请等待下载完成后再安装");
      throw new Error("请先下载该版本安装包");
    }
    const filePath = resolved.filePath;
    const ext = extname(filePath).toLowerCase();
    if ([".exe", ".dmg", ".pkg", ".app"].includes(ext)) {
      await shell.openPath(filePath);
      return true;
    }
    if (ext !== ".zip") {
      throw new Error("暂不支持该更新包格式，请使用浏览器下载手动更新");
    }
    if (process.platform !== "win32") {
      await shell.openPath(filePath);
      return true;
    }
    const result = await dialog.showMessageBox({
      type: "question",
      title: "一键更新",
      message: "将自动替换当前程序并保留 resources/config 配置，完成后自动重启。是否继续？",
      buttons: ["继续", "取消"],
      defaultId: 0,
      cancelId: 1
    });
    if (result.response !== 0) return false;
    this.launchWindowsZipUpdater(filePath);
    return true;
  }

  private async runDownload(url: string, partPath: string, filePath: string, downloadedBytes: number): Promise<void> {
    const startedAt = Date.now();
    let lastBytes = downloadedBytes;
    let lastAt = startedAt;
    const response = await axios.get(url, {
      responseType: "stream",
      signal: this.abortController?.signal,
      timeout: 30000,
      headers: downloadedBytes ? { Range: `bytes=${downloadedBytes}-` } : undefined
    });
    const totalBytes = Number(response.headers["content-length"] || 0) + downloadedBytes;
    const stream = createWriteStream(partPath, { flags: downloadedBytes ? "a" : "w" });

    await new Promise<void>((resolve, reject) => {
      response.data.on("data", (chunk: Buffer) => {
        this.downloadState.receivedBytes += chunk.length;
        this.downloadState.totalBytes = totalBytes;
        this.downloadState.percent = totalBytes ? Math.min(100, (this.downloadState.receivedBytes / totalBytes) * 100) : 0;
        const now = Date.now();
        if (now - lastAt >= 800) {
          const speed = ((this.downloadState.receivedBytes - lastBytes) * 1000) / (now - lastAt);
          this.downloadState.speedText = formatBytesPerSecond(speed);
          this.downloadState.etaText = formatEta((totalBytes - this.downloadState.receivedBytes) / speed);
          lastAt = now;
          lastBytes = this.downloadState.receivedBytes;
        }
      });
      response.data.on("error", reject);
      stream.on("error", reject);
      stream.on("finish", resolve);
      response.data.pipe(stream);
    });

    renameSync(partPath, filePath);
    this.markDownloadedFile(this.downloadState.tag, filePath);
    const tag = this.downloadState.tag;
    this.downloadState = {
      ...this.downloadState,
      running: false,
      paused: false,
      receivedBytes: totalBytes,
      totalBytes,
      percent: 100,
      speedText: "-",
      etaText: "-",
      message: "下载完成"
    };
    this.abortController = null;
    this.trackDownload({
      title: "更新包下载完成",
      tag,
      filePath,
      receivedBytes: totalBytes,
      totalBytes,
      costTime: Date.now() - startedAt
    });
  }

  private findRelease(tag: string): UpdateRelease {
    const release = this.releases.find((item) => item.tag === tag);
    if (!release) throw new Error(`未找到版本 ${tag}`);
    return release;
  }

  private readAssetCache(): Record<string, Partial<UpdateRelease>> {
    try {
      if (!existsSync(assetCachePath())) return {};
      const raw = JSON.parse(readFileSync(assetCachePath(), "utf-8"));
      return raw && typeof raw === "object" ? raw : {};
    } catch {
      return {};
    }
  }

  private writeAssetCache(cache: Record<string, Partial<UpdateRelease>>): void {
    ensureParent(assetCachePath());
    writeFileSync(assetCachePath(), JSON.stringify(cache, null, 2), "utf-8");
  }

  private existingFile(filePath?: string): boolean {
    try {
      return Boolean(filePath && existsSync(filePath) && statSync(filePath).isFile());
    } catch {
      return false;
    }
  }

  private uniquePaths(paths: string[]): string[] {
    const seen = new Set<string>();
    return paths.filter((filePath) => {
      if (!filePath || seen.has(filePath)) return false;
      seen.add(filePath);
      return true;
    });
  }

  private expandPackageCandidates(filePath?: string): string[] {
    if (!filePath) return [];
    const candidates = [filePath];
    const withoutPart = isPartFile(filePath) ? filePath.slice(0, -".part".length) : "";
    if (withoutPart) candidates.push(withoutPart);
    if (!isPartFile(filePath)) candidates.push(`${filePath}.part`);
    const basePath = withoutPart || filePath;
    if (!extname(basePath)) candidates.push(`${basePath}.zip`, `${basePath}.exe`, `${basePath}.dmg`, `${basePath}.pkg`);
    if (extname(basePath).toLowerCase() !== ".zip") candidates.push(`${basePath}.zip`);
    return this.uniquePaths(candidates);
  }

  private findExistingPackage(candidates: string[]): { filePath?: string; partPath?: string } {
    let partPath = "";
    for (const candidate of candidates) {
      if (!this.existingFile(candidate)) continue;
      if (isPartFile(candidate)) {
        partPath ||= candidate;
        continue;
      }
      return { filePath: candidate };
    }
    return partPath ? { partPath } : {};
  }

  private expectedDownloadPaths(release: UpdateRelease): string[] {
    const downloadDir = this.getSettings().downloadDir;
    const names = this.uniquePaths([release.downloadName, basename(release.rawDownloadUrl || "")].filter(Boolean) as string[]);
    return names.map((name) => join(downloadDir, name));
  }

  private markDownloadedFile(tag: string, filePath: string): void {
    this.downloadedFiles.set(tag, filePath);
    this.releases = this.releases.map((release) => (release.tag === tag ? { ...release, downloadedPath: filePath } : release));
  }

  private async resolveDownloadedPackage(tag: string): Promise<{ filePath?: string; partPath?: string }> {
    const mapped = this.findExistingPackage(this.expandPackageCandidates(this.downloadedFiles.get(tag)));
    if (mapped.filePath) {
      this.markDownloadedFile(tag, mapped.filePath);
      return mapped;
    }

    let release = this.mergeCachedAsset(this.findRelease(tag));
    const expected = this.findExistingPackage(this.expectedDownloadPaths(release));
    if (expected.filePath) {
      this.markDownloadedFile(tag, expected.filePath);
      return expected;
    }

    const fallbackCandidates = [
      ...this.expandPackageCandidates(release.downloadedPath),
      ...(this.downloadState.tag === tag ? this.expandPackageCandidates(this.downloadState.filePath) : []),
      ...this.expectedDownloadPaths(release).flatMap((filePath) => this.expandPackageCandidates(filePath))
    ];
    let fallback = this.findExistingPackage(fallbackCandidates);
    if (fallback.filePath) {
      this.markDownloadedFile(tag, fallback.filePath);
      return fallback;
    }

    try {
      release = await this.ensureReleaseAsset(tag);
      const assetCandidates = this.expectedDownloadPaths(release).flatMap((filePath) => this.expandPackageCandidates(filePath));
      fallback = this.findExistingPackage(assetCandidates);
      if (fallback.filePath) this.markDownloadedFile(tag, fallback.filePath);
    } catch {
      // 安装入口只需要本地文件；资产解析失败时保留本地查找结果。
    }

    return fallback.filePath || fallback.partPath ? fallback : mapped.partPath ? mapped : expected.partPath ? expected : {};
  }

  private mergeCachedAsset(release: UpdateRelease): UpdateRelease {
    const cached = this.readAssetCache()[release.tag];
    if (!cached?.rawDownloadUrl && !(cached as any)?.raw_download_url) return release;
    const rawDownloadUrl = String(cached.rawDownloadUrl || (cached as any).raw_download_url || release.rawDownloadUrl || "");
    const downloadName = String(cached.downloadName || (cached as any).download_name || release.downloadName || "");
    const kind = String(cached.installKind || (cached as any).install_kind || installKindFor(downloadName));
    return this.withSource(
      {
        ...release,
        rawDownloadUrl,
        downloadName,
        assetAvailable: Boolean(cached.assetAvailable ?? (cached as any).asset_available ?? rawDownloadUrl),
        installKind: kind,
        installSupported: Boolean(cached.installSupported ?? (cached as any).install_supported ?? installSupportedFor(kind))
      },
      this.getSettings()
    );
  }

  private persistAsset(release: UpdateRelease): void {
    if (!release.rawDownloadUrl) return;
    const kind = release.installKind || installKindFor(release.downloadName);
    const cache = this.readAssetCache();
    cache[release.tag] = {
      rawDownloadUrl: release.rawDownloadUrl,
      downloadName: release.downloadName,
      assetAvailable: true,
      installKind: kind,
      installSupported: installSupportedFor(kind)
    };
    this.writeAssetCache(cache);
  }

  private async ensureReleaseAsset(tag: string): Promise<UpdateRelease> {
    let release = this.mergeCachedAsset(this.findRelease(tag));
    if (release.rawDownloadUrl) return release;
    const asset = await this.fetchReleaseAsset(tag);
    const kind = installKindFor(asset?.name || "");
    release = this.withSource(
      {
        ...release,
        rawDownloadUrl: asset?.browser_download_url || "",
        downloadName: asset?.name || "",
        assetAvailable: Boolean(asset?.browser_download_url),
        installKind: kind,
        installSupported: installSupportedFor(kind)
      },
      this.getSettings()
    );
    this.releases = this.releases.map((item) => (item.tag === tag ? release : item));
    this.persistAsset(release);
    if (!release.rawDownloadUrl) throw new Error("该版本未找到可下载的安装包");
    return release;
  }

  private async fetchReleaseAsset(tag: string): Promise<GitHubAsset | undefined> {
    try {
      const response = await axios.get<GitHubRelease>(`https://api.github.com/repos/${OWNER}/${REPO}/releases/tags/${encodeURIComponent(tag)}`, {
        timeout: 20000,
        headers: {
          Accept: "application/vnd.github+json",
          "User-Agent": "SignSignIn-Electron"
        }
      });
      return chooseAsset(response.data.assets || []);
    } catch {
      const html = await this.requestText(`https://github.com/${OWNER}/${REPO}/releases/expanded_assets/${encodeURIComponent(tag)}`, this.getSettings());
      return chooseAsset(this.parseAssets(html));
    }
  }

  private mapRelease(release: GitHubRelease, settings: UpdateSettings): UpdateRelease {
    const asset = chooseAsset(release.assets || []);
    const tag = release.tag_name;
    const mapped = this.withSource(
      {
        tag,
        name: release.name || tag,
        body: release.body || "",
        publishedAt: release.published_at || "",
        htmlUrl: release.html_url || `${PROJECT_GITHUB}/releases/tag/${tag}`,
        compareUrl: `${PROJECT_GITHUB}/compare/${readPackageVersion()}...${tag}`,
        downloadUrl: asset?.browser_download_url || "",
        rawDownloadUrl: asset?.browser_download_url || "",
        downloadName: asset?.name || "",
        assetAvailable: Boolean(asset?.browser_download_url),
        installKind: installKindFor(asset?.name || ""),
        installSupported: installSupportedFor(installKindFor(asset?.name || ""))
      },
      settings
    );
    if (mapped.rawDownloadUrl) this.persistAsset(mapped);
    return this.mergeCachedAsset(mapped);
  }

  private withSource(release: UpdateRelease, settings: UpdateSettings): UpdateRelease {
    const raw = release.rawDownloadUrl;
    const downloadUrl = this.applySourceToUrl(raw, settings);
    return { ...release, downloadUrl, downloadedPath: this.downloadedFiles.get(release.tag) || release.downloadedPath };
  }

  private applySourceToUrl(raw: string, settings: UpdateSettings): string {
    const source = SOURCES.find((item) => item.key === settings.source);
    const prefix = settings.source === "custom" ? settings.customSource : source?.value || "";
    const normalizedPrefix = prefix && !prefix.includes("{url}") && !prefix.endsWith("/") ? `${prefix}/` : prefix;
    return normalizedPrefix ? (normalizedPrefix.includes("{url}") ? normalizedPrefix.replaceAll("{url}", raw) : `${normalizedPrefix}${raw}`) : raw;
  }

  private launchWindowsZipUpdater(zipPath: string): void {
    const appDir = app.isPackaged ? join(process.resourcesPath, "..") : getProjectRoot();
    const backupDir = join(tmpdir(), `sign_update_backup_${Date.now()}`);
    const scriptPath = join(tmpdir(), `sign_update_${Date.now()}.ps1`);
    const currentPid = process.pid;
    const script = `
$ErrorActionPreference = "Stop"
Wait-Process -Id ${currentPid} -ErrorAction SilentlyContinue
$zip = ${JSON.stringify(zipPath)}
$appDir = ${JSON.stringify(appDir)}
$backupDir = ${JSON.stringify(backupDir)}
$extractDir = Join-Path $env:TEMP ("sign_update_extract_" + [DateTimeOffset]::Now.ToUnixTimeMilliseconds())
Expand-Archive -LiteralPath $zip -DestinationPath $extractDir -Force
New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
if (Test-Path (Join-Path $appDir "resources\\config")) {
  Copy-Item -LiteralPath (Join-Path $appDir "resources\\config") -Destination (Join-Path $backupDir "config") -Recurse -Force
}
$payload = Get-ChildItem -LiteralPath $extractDir | Select-Object -First 1
if ($payload -and (Test-Path (Join-Path $payload.FullName "resources"))) { $source = $payload.FullName } else { $source = $extractDir }
Copy-Item -LiteralPath (Join-Path $source "*") -Destination $appDir -Recurse -Force
if (Test-Path (Join-Path $backupDir "config")) {
  New-Item -ItemType Directory -Force -Path (Join-Path $appDir "resources") | Out-Null
  Copy-Item -LiteralPath (Join-Path $backupDir "config") -Destination (Join-Path $appDir "resources\\config") -Recurse -Force
}
$exe = Join-Path $appDir "SignSignIn.exe"
if (-not (Test-Path $exe)) { $exe = Join-Path $appDir "main.exe" }
if (Test-Path $exe) { Start-Process -FilePath $exe }
`;
    writeFileSync(scriptPath, script, "utf-8");
    spawn("powershell.exe", ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", scriptPath], {
      detached: true,
      stdio: "ignore",
      windowsHide: true
    }).unref();
    app.quit();
  }
}

export const updateService = new UpdateService();
