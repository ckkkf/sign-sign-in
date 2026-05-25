import { basename } from "node:path";
import type {
  JieLongField,
  JieLongFieldAnswer,
  JieLongFileInfo,
  JieLongFormBundle,
  JieLongQrLogin,
  JieLongQrState,
  JieLongSettings,
  JieLongSubmitPayload,
  SignConfig
} from "@shared/types";
import * as jielongApi from "../api/jielongClient";
import type { JieLongApiData } from "../api/types/jielongTypes";
import { jielongDraftStore } from "../stores/jielongDraftStore";
import { configStore } from "./configStore";
import { buildLocalMediaFiles } from "./jielongMedia";

export { looksLikeInvalidJieLongToken } from "../api/jielongClient";

function firstText(value: unknown): string {
  if (value === null || value === undefined) {
    return "";
  }

  if (typeof value === "string") {
    return value.trim();
  }

  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }

  if (Array.isArray(value)) {
    return value.map((item) => String(item).trim()).filter(Boolean).join(" / ");
  }

  return String(value).trim();
}

function parseDraftContent(draftData: JieLongApiData): JieLongApiData {
  const content = draftData?.Data?.Content;
  if (!content) {
    return {};
  }

  try {
    return JSON.parse(content);
  } catch {
    return {};
  }
}

function resolveBuiltinValue(field: JieLongField, formInfoData: JieLongApiData): string {
  const formInfo = formInfoData.FormInfo || {};
  const nickname = formInfoData.Nickname || "";
  const name = String(field.Name || "");
  const fieldId = Number(field.Id || 0);
  if (fieldId === 0 || name.includes("姓名") || name.includes("名字")) {
    return firstText(formInfo.FormUserName || formInfo.Name || formInfo.Author || nickname);
  }

  if (name.includes("学号")) {
    return firstText(formInfo.StudentNumber);
  }

  if (name.includes("工号")) {
    return firstText(formInfo.JobNumber);
  }

  if (name.includes("手机")) {
    return firstText(formInfo.Moblie);
  }

  if (name.includes("邮箱")) {
    return firstText(formInfo.Email);
  }

  if (name.includes("地址")) {
    return firstText(formInfo.Address);
  }

  return "";
}

function extractFieldValue(field: JieLongField, draftMap: JieLongApiData, formInfoData: JieLongApiData): string {
  const draftItem = draftMap[String(field.Id)];
  if (draftItem && typeof draftItem === "object") {
    const value = draftItem.value || {};
    return firstText(value.Texts) || firstText(value.Values) || firstText(value.OtherValue) || "";
  }
  return firstText(field.Defaultvalue) || resolveBuiltinValue(field, formInfoData);
}

function extractFieldFiles(field: JieLongField, draftMap: JieLongApiData): JieLongFileInfo[] {
  const draftItem = draftMap[String(field.Id)];
  if (!draftItem || typeof draftItem !== "object") {
    return [];
  }

  const value = draftItem.value || {};
  const files = value.Files || draftItem.Files || [];
  return Array.isArray(files) ? structuredClone(files) : [];
}

function buildRenderFields(editDetailData: JieLongApiData, draftMap: JieLongApiData, formInfoData: JieLongApiData): JieLongField[] {
  const setting = editDetailData.CheckInSetting || {};
  const fields: JieLongField[] = [];
  if (setting.Signature && typeof setting.Signature === "object") {
    fields.push(setting.Signature);
  }

  for (const item of setting.Settings || []) {
    if (item && typeof item === "object") {
      fields.push(item);
    }
  }

  return fields.map((field) => ({
    ...structuredClone(field),
    InitialValue: extractFieldValue(field, draftMap, formInfoData),
    InitialFiles: extractFieldFiles(field, draftMap)
  }));
}

export class JieLongService {
  getSettings(): JieLongSettings {
    const config = configStore.read();
    const jielong = config.settings?.jielong || {};
    return {
      authorization: String(jielong.authorization || ""),
      thread_id: String(jielong.thread_id || ""),
      share_url: String(jielong.share_url || ""),
      openId: String(jielong.openId || ""),
      sId: String(jielong.sId || ""),
      expire: jielong.expire,
      termsAgreed: jielong.termsAgreed === true,
      isNew: jielong.isNew === true
    };
  }

  saveSettings(settings: Partial<JieLongSettings>): JieLongSettings {
    const config = configStore.read();
    const current = this.getSettings();
    const next = { ...current, ...settings };
    const updated: SignConfig = {
      ...config,
      settings: {
        ...config.settings,
        jielong: next
      }
    };
    configStore.write(updated);
    return next;
  }

  createQrLogin(): Promise<JieLongQrLogin> {
    return jielongApi.createQrLogin();
  }

  pollQrLogin(uuid: string): Promise<JieLongQrState> {
    return jielongApi.pollQrLogin(uuid);
  }

  async exchangeQrToken(code: string): Promise<JieLongSettings> {
    const body = await jielongApi.exchangeQrToken(code);
    const token = String(body.Token || body.token || body.Authorization || body.authorization || "").trim();
    if (!token) {
      throw new Error("接龙登录成功但未返回 Token");
    }

    return this.saveSettings({
      authorization: token,
      openId: String(body.OpenId || ""),
      sId: String(body.SId || ""),
      expire: body.Expire,
      termsAgreed: body.TermsAgreed,
      isNew: body.IsNew
    });
  }

  async parseShareUrl(shareUrl: string): Promise<string> {
    const url = String(shareUrl || "").trim();
    const threadId = await jielongApi.parseShareUrl(url);
    this.saveSettings({ share_url: url, thread_id: threadId });
    return threadId;
  }

  async loadForm(token: string, threadId: string): Promise<JieLongFormBundle> {
    const normalizedThreadId = String(threadId || "").trim();
    if (!normalizedThreadId) {
      throw new Error("请先填写接龙 threadId");
    }

    const detailResp = await jielongApi.fetchDetail(token, normalizedThreadId);
    const detailData = detailResp.Data || {};
    const threadData = detailData.Thread || {};
    const numericThreadId = threadData.ThreadId;
    if (!numericThreadId) {
      throw new Error("未从接龙详情中拿到数字 threadId");
    }

    const formInfoResp = await jielongApi.fetchFormInfo(token);
    const editDetailResp = await jielongApi.fetchEditRecordDetail(token, numericThreadId);
    const draftResp = await jielongApi.fetchRecordDraft(token, numericThreadId);
    const editDetail = editDetailResp.Data || {};
    const draftMap = parseDraftContent(draftResp);

    const bundle = {
      thread: threadData,
      check_in: detailData.CheckIn || {},
      edit_detail: editDetail,
      fields: buildRenderFields(editDetail, draftMap, formInfoResp.Data || {})
    };
    this.saveSettings({ authorization: token, thread_id: normalizedThreadId });
    return bundle;
  }

  getDraft(threadId: string): Record<string, JieLongFieldAnswer> {
    return jielongDraftStore.get(threadId);
  }

  saveDraft(threadId: string, answers: Record<string, JieLongFieldAnswer>): boolean {
    return jielongDraftStore.save(threadId, answers);
  }

  async submit(token: string, payload: JieLongSubmitPayload): Promise<JieLongApiData> {
    this.saveSettings({ authorization: token });
    const prepared = await this.prepareSubmitPayload(token, payload);
    try {
      return await jielongApi.submitRecord(token, prepared);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      if (message.includes("当前署名与您上一次提交的不符")) {
        const err = new Error(message);
        (err as Error & { code?: string }).code = "SIGNATURE_MISMATCH";
        throw err;
      }
      throw error;
    }
  }

  private async prepareSubmitPayload(token: string, payload: JieLongSubmitPayload): Promise<JieLongSubmitPayload> {
    const prepared = structuredClone(payload);
    if (!prepared.ThreadId) {
      throw new Error("未找到提交可用的 threadId");
    }

    for (const record of prepared.RecordValues || []) {
      const files = (record.Files || []) as JieLongFileInfo[];
      if (!files.length) {
        continue;
      }

      const uploaded: JieLongFileInfo[] = [];
      for (const fileInfo of files) {
        if (fileInfo.RelativePath && !fileInfo.LocalPath) {
          uploaded.push(fileInfo);
        } else {
          uploaded.push(await this.uploadMediaFile(token, prepared.ThreadId, fileInfo));
        }
      }
      record.Files = uploaded;
      record.HasValue = Boolean(record.HasValue || record.Texts?.length || record.Values?.length || uploaded.length);
    }
    return prepared;
  }

  private async uploadMediaFile(token: string, threadId: number, fileInfo: JieLongFileInfo): Promise<JieLongFileInfo> {
    const localFiles = buildLocalMediaFiles([String(fileInfo.LocalPath || "")]);
    const localPath = String(localFiles[0].LocalPath || "");
    const sourceName = String(fileInfo.FileName || fileInfo.Name || basename(localPath)).trim() || basename(localPath);
    const policy = (await jielongApi.fetchAttachmentCosUploadPolicy(token, threadId, sourceName)).Data || {};
    const uploadHost = String(policy.Host || "").trim();
    if (!uploadHost) {
      throw new Error("未获取到接龙图片上传地址");
    }

    const mime = String(fileInfo.ContentType || localFiles[0].ContentType || "image/jpeg");
    const uploaded = await jielongApi.uploadToCos(uploadHost, policy, localPath, sourceName, mime);
    return { ...uploaded, IsNewUpload: true };
  }
}

export const jielongService = new JieLongService();
