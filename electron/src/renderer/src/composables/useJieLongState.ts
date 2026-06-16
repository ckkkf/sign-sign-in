import Modal from "@kousum/semi-ui-vue/dist/modal";
import Toast from "@kousum/semi-ui-vue/dist/toast";
import { computed, onMounted, onUnmounted, reactive, ref, watch } from "vue";
import type { JieLongField, JieLongFieldAnswer, JieLongFileInfo, JieLongFormBundle, JieLongSettings, JieLongSubmitPayload } from "@shared/types";
import { ensureOk } from "../utils/api";

function plain<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function formatDateRange(start: unknown, end: unknown) {
  const compact = (value: unknown) => {
    const text = String(value || "").trim();
    if (!text || text === "-") return "-";
    const parts = text.split(/\s+/);
    if (parts.length >= 2 && parts[0].length === 10) return `${parts[0].slice(5)} ${parts[1].slice(0, 5)}`;
    return text;
  };
  const left = compact(start);
  const right = compact(end);
  return left === "-" && right === "-" ? "-" : `${left} -> ${right}`;
}

function splitLocation(value: string) {
  const text = value.trim();
  if (!text) return ["", ""];
  const separator = text.includes("•") ? "•" : text.includes("·") ? "·" : "";
  if (!separator) return [text, ""];
  return text.split(separator, 2).map((item) => item.trim());
}

function composeLocation(answer: JieLongFieldAnswer) {
  const area = String(answer.area || "").trim();
  const place = String(answer.place || "").trim();
  if (area && place) return `${area}•${place}`;
  return area || place;
}

function validateCoordinate(value: string, axis: "longitude" | "latitude") {
  const text = String(value || "").trim();
  if (!text) return false;
  const number = Number(text);
  if (!Number.isFinite(number)) return false;
  return axis === "longitude" ? number >= -180 && number <= 180 : number >= -90 && number <= 90;
}

export function useJieLongState() {
  const status = ref("待拉取");
  const loginStatus = ref("");
  const loading = ref(false);
  const submitting = ref(false);
  const qrBusy = ref(false);
  const qrPolling = ref(false);
  const qrVisible = ref(false);
  const qrImage = ref("");
  const qrUuid = ref("");
  const bundle = ref<JieLongFormBundle | null>(null);
  const settings = reactive<JieLongSettings>({
    authorization: "",
    thread_id: "",
    share_url: ""
  });
  const answers = reactive<Record<string, JieLongFieldAnswer>>({});
  const invalidFields = reactive<Record<string, boolean>>({});
  let pollTimer: number | undefined;
  let draftTimer: number | undefined;

  const statusTone = computed(() => {
    if (["拉取失败", "提交失败", "登录失败"].includes(status.value) || loginStatus.value === "登录失败") return "red";
    if (["拉取完毕", "提交成功"].includes(status.value) || loginStatus.value === "登录成功") return "green";
    if (["正在拉取", "正在提交", "生成二维码中", "扫码成功", "换取 Token 中"].includes(status.value) || loginStatus.value) return "blue";
    return "grey";
  });

  const visibleFields = computed(() => (bundle.value?.fields || []).filter((field) => isFieldVisible(field)));

  const summaryItems = computed(() => {
    const data = bundle.value;
    if (!data) return [];
    const checkIn = data.check_in || {};
    const thread = data.thread || {};
    const checkStatus = checkIn.CheckInStatus?.CheckInMsg || thread.AttendButtonText || "-";
    return [
      { key: "主题", value: String(thread.Subject || "-") },
      { key: "时间", value: formatDateRange(checkIn.StartTime, checkIn.EndTime) },
      { key: "状态", value: String(checkStatus) },
      { key: "已接龙", value: `${checkIn.CheckInUserCount || 0} 人 / ${checkIn.CheckInCount || 0} 次` }
    ];
  });

  function statusClass(text: string) {
    if (["拉取失败", "提交失败", "登录失败"].includes(text)) return "danger";
    if (["拉取完毕", "提交成功", "登录成功"].includes(text)) return "success";
    if (["正在拉取", "正在提交", "生成二维码中", "扫码成功", "换取 Token 中"].includes(text)) return "working";
    return "ready";
  }

  function fieldId(field: JieLongField) {
    return String(Number(field.Id || 0));
  }

  function fieldKind(field: JieLongField) {
    if (Number(field.FieldType || 0) === 16) return "location";
    if (Number(field.FieldType || 0) === 25) return "media";
    if (field.IsTextarea) return "textarea";
    if (parseOptions(field).length) return "select";
    return "text";
  }

  function parseOptions(field: JieLongField) {
    const raw = field.ControlOptions;
    if (!raw) return [];
    let data = raw;
    if (typeof raw === "string") {
      try {
        data = JSON.parse(raw);
      } catch {
        return raw.trim() ? [{ Text: raw.trim(), Value: raw.trim(), IsOtherOption: false }] : [];
      }
    }
    if (data && typeof data === "object" && !Array.isArray(data)) data = (data as Record<string, any>).Options || [];
    if (!Array.isArray(data)) return [];
    return data.flatMap((item) => {
      if (typeof item === "string") return item.trim() ? [{ Text: item.trim(), Value: item.trim(), IsOtherOption: false }] : [];
      if (!item || typeof item !== "object") return [];
      const body = item as Record<string, any>;
      const text = String(body.Text || body.Name || body.Label || body.Value || "").trim();
      const value = String(body.Value || text).trim();
      return text ? [{ Text: text, Value: value, IsOtherOption: Boolean(body.IsOtherOption) }] : [];
    });
  }

  function selectedOption(field: JieLongField) {
    const answer = answers[fieldId(field)] || {};
    const options = parseOptions(field);
    return options.find((option) => option.Value === answer.option_value || option.Text === answer.option_text);
  }

  function isOtherOption(field: JieLongField) {
    return Boolean(selectedOption(field)?.IsOtherOption);
  }

  function isFieldVisible(field: JieLongField) {
    const relationId = String(field.RelationId || "").trim();
    if (!relationId) return true;
    const controllers = bundle.value?.fields || [];
    for (const controller of controllers) {
      for (const condition of controller.VisibilityCondition || []) {
        const targets = (condition.RelationIdList || []).map((item) => String(item));
        if (!targets.includes(relationId)) continue;
        const answer = answers[fieldId(controller)] || {};
        if (String(answer.option_value || "") === String(condition.OptionValue || "")) return true;
      }
    }
    return !controllers.some((controller) =>
      (controller.VisibilityCondition || []).some((condition) => (condition.RelationIdList || []).map((item) => String(item)).includes(relationId))
    );
  }

  function applyFieldDefaults(fields: JieLongField[]) {
    for (const field of fields) {
      const id = fieldId(field);
      const kind = fieldKind(field);
      if (answers[id]) continue;
      if (kind === "media") {
        answers[id] = { files: [...(field.InitialFiles || [])] };
      } else if (kind === "location") {
        const value = String(field.InitialValue || "");
        const [area, place] = splitLocation(value);
        answers[id] = { value, area, place, longitude: "", latitude: "" };
      } else {
        answers[id] = { value: String(field.InitialValue || "") };
      }
    }
  }

  function setAnswer(id: string, patch: JieLongFieldAnswer) {
    answers[id] = { ...(answers[id] || {}), ...patch };
    if (patch.area !== undefined || patch.place !== undefined) {
      answers[id].value = composeLocation(answers[id]);
    }
    validateLocations(false);
    scheduleDraftSave();
  }

  function selectOption(field: JieLongField, value: unknown) {
    const option = parseOptions(field).find((item) => item.Value === value);
    setAnswer(fieldId(field), {
      option_text: option?.Text || "",
      option_value: option?.Value || "",
      other_value: ""
    });
  }

  function imageName(file: JieLongFileInfo) {
    return String(file.Name || file.FileName || file.LocalPath || "图片").split(/[\\/]/).pop() || "图片";
  }

  function validateLocations(strict: boolean) {
    let ok = true;
    for (const field of visibleFields.value) {
      if (fieldKind(field) !== "location") continue;
      const id = fieldId(field);
      const answer = answers[id] || {};
      const hasAny = Boolean(answer.area || answer.place || answer.longitude || answer.latitude);
      const shouldValidate = strict || field.IsRequired || hasAny;
      const invalid =
        shouldValidate &&
        (!String(answer.area || "").trim() ||
          !String(answer.place || "").trim() ||
          !validateCoordinate(String(answer.longitude || ""), "longitude") ||
          !validateCoordinate(String(answer.latitude || ""), "latitude"));
      invalidFields[id] = invalid;
      if (invalid) ok = false;
    }
    return ok;
  }

  function visibleBundle(): JieLongFormBundle {
    if (!bundle.value) throw new Error("请先拉取接龙表单");
    return {
      ...bundle.value,
      fields: visibleFields.value
    };
  }

  async function run<T>(fn: () => Promise<T>, success?: string) {
    try {
      const result = await fn();
      if (success) Toast.success(success);
      return result;
    } catch (error) {
      const message = error instanceof Error ? error.message : "操作失败";
      Toast.error(message);
      return undefined;
    }
  }

  async function loadSettings() {
    const loaded = ensureOk(await window.signSignIn.jielong.getSettings());
    Object.assign(settings, loaded);
  }

  async function saveSettings() {
    const saved = ensureOk(await window.signSignIn.jielong.saveSettings(plain(settings)));
    Object.assign(settings, saved);
  }

  async function parseShareUrl() {
    await run(async () => {
      const threadId = ensureOk(await window.signSignIn.jielong.parseShareUrl(settings.share_url));
      settings.thread_id = threadId;
      await loadSettings();
    }, `已解析 threadId：${settings.thread_id}`);
  }

  async function startQrLogin() {
    if (qrBusy.value) {
      qrVisible.value = true;
      return;
    }
    qrBusy.value = true;
    loginStatus.value = "生成二维码中";
    openQrModal();
    await run(async () => {
      await saveSettings();
      const qr = ensureOk(await window.signSignIn.jielong.createQrLogin());
      qrUuid.value = qr.uuid;
      qrImage.value = qr.image;
      loginStatus.value = "等待扫码";
      startPollingQr();
    });
    qrBusy.value = false;
  }

  function startPollingQr() {
    if (!qrVisible.value || qrPolling.value) return;
    if (pollTimer) window.clearInterval(pollTimer);
    qrPolling.value = true;
    pollTimer = window.setInterval(async () => {
      if (!qrVisible.value || !qrUuid.value || qrBusy.value) return;
      const result = await run(async () => ensureOk(await window.signSignIn.jielong.pollQrLogin(qrUuid.value)));
      if (!result) return;
      if (result.status === "scanned") loginStatus.value = "扫码成功";
      if (result.status === "waiting" || result.status === "timeout") loginStatus.value = result.message;
      if (result.status === "expired" || result.status === "error") {
        stopPolling();
        loginStatus.value = "登录失败";
        Toast.error(result.message);
      }
      if (result.status === "confirmed") {
        stopPolling();
        qrBusy.value = true;
        loginStatus.value = "换取 Token 中";
        const saved = await run(async () => ensureOk(await window.signSignIn.jielong.exchangeQrToken(result.code)), "接龙登录成功，Token 已更新");
        if (saved) {
          Object.assign(settings, saved);
          loginStatus.value = "登录成功";
          closeQrModal();
        }
        qrBusy.value = false;
      }
    }, 1000);
  }

  function stopPolling() {
    if (pollTimer) window.clearInterval(pollTimer);
    pollTimer = undefined;
    qrPolling.value = false;
  }

  function openQrModal() {
    qrVisible.value = true;
    if (qrUuid.value) startPollingQr();
  }

  function closeQrModal() {
    qrVisible.value = false;
    stopPolling();
  }

  watch(qrVisible, (visible) => {
    if (!visible) stopPolling();
  });

  async function loadForm() {
    loading.value = true;
    status.value = "正在拉取";
    await run(async () => {
      await saveSettings();
      const loaded = ensureOk(await window.signSignIn.jielong.loadForm(settings.authorization, settings.thread_id));
      bundle.value = loaded;
      Object.keys(answers).forEach((key) => delete answers[key]);
      applyFieldDefaults(loaded.fields);
      const draft = ensureOk(await window.signSignIn.jielong.getDraft(String(loaded.thread.ThreadId || settings.thread_id)));
      Object.assign(answers, draft);
      applyFieldDefaults(loaded.fields);
      status.value = "拉取完毕";
    }, "接龙表单加载成功");
    loading.value = false;
    if (status.value === "正在拉取") status.value = "拉取失败";
  }

  function scheduleDraftSave() {
    if (!bundle.value) return;
    if (draftTimer) window.clearTimeout(draftTimer);
    draftTimer = window.setTimeout(() => {
      void window.signSignIn.jielong.saveDraft(String(bundle.value?.thread.ThreadId || settings.thread_id), plain(answers));
    }, 350);
  }

  async function chooseImage(field: JieLongField, path: string) {
    if (!path) return;
    await run(async () => {
      const files = ensureOk(await window.signSignIn.jielong.buildLocalMediaFiles([path]));
      setAnswer(fieldId(field), { files });
    });
  }

  function clearImage(field: JieLongField) {
    setAnswer(fieldId(field), { files: [] });
  }

  async function submit() {
    if (!validateLocations(true)) {
      Toast.warning("请分别填写有效的市区、地点和经纬度。");
      return;
    }
    const built = await run(async () => {
      const editDetail = bundle.value?.edit_detail || {};
      const signature = answers["0"]?.value || String(editDetail.LastSignature || editDetail.Signature || "");
      return ensureOk(await window.signSignIn.jielong.buildSubmitPayload(plain(visibleBundle()), plain(answers), signature, String(editDetail.Number || "")));
    });
    if (!built) return;
    Modal.confirm({
      title: "确认提交",
      content: "确认按当前内容提交打卡吗？",
      okText: "提交",
      cancelText: "取消",
      onOk: () => void doSubmit(built)
    });
  }

  async function doSubmit(payload: JieLongSubmitPayload) {
    submitting.value = true;
    status.value = "正在提交";
    const result = await run(async () => ensureOk(await window.signSignIn.jielong.submit(settings.authorization, plain(payload))));
    submitting.value = false;
    if (result?.signatureMismatch) {
      Modal.confirm({
        title: "确认提交",
        content: "当前署名与您上一次提交的不符，是否继续提交？",
        okText: "继续提交",
        cancelText: "取消",
        onOk: () => void doSubmit({ ...payload, IsNameNumberComfirm: true })
      });
      status.value = "拉取完毕";
      return;
    }
    if (result) {
      status.value = "提交成功";
      Toast.success(String(result.Description || "提交成功"));
    } else {
      status.value = "提交失败";
      await loadSettings();
    }
  }

  onMounted(() => {
    void run(loadSettings);
  });

  onUnmounted(() => {
    stopPolling();
    if (draftTimer) window.clearTimeout(draftTimer);
  });

  return {
    status,
    loginStatus,
    loading,
    submitting,
    qrBusy,
    qrPolling,
    qrVisible,
    qrImage,
    qrUuid,
    bundle,
    settings,
    answers,
    invalidFields,
    statusTone,
    visibleFields,
    summaryItems,
    statusClass,
    fieldId,
    fieldKind,
    parseOptions,
    isOtherOption,
    setAnswer,
    selectOption,
    imageName,
    parseShareUrl,
    startQrLogin,
    closeQrModal,
    loadForm,
    chooseImage,
    clearImage,
    submit
  };
}
