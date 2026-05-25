import type { JieLongField, JieLongFieldAnswer, JieLongFormBundle, JieLongQrState, JieLongSubmitPayload } from "./types";

export function parseQrUuid(xml: string): string {
  const match = String(xml || "").match(/<uuid><!\[CDATA\[(.*?)\]\]><\/uuid>/);
  const uuid = match?.[1]?.trim() || "";
  if (!uuid) throw new Error("未获取到接龙二维码 UUID");
  return uuid;
}

export function parseQrPoll(text: string): JieLongQrState {
  const raw = String(text || "");
  const errcode = raw.match(/window\.wx_errcode=(\d+);/)?.[1] || "";
  const code = raw.match(/window\.wx_code='(.*?)'/)?.[1]?.trim() || "";
  let status: JieLongQrState["status"] = "waiting";
  if (code) status = "confirmed";
  else if (errcode === "404") status = "scanned";
  else if (errcode === "402" || errcode === "403") status = "expired";
  else if (errcode && errcode !== "408") status = "error";
  return {
    status,
    wxErrcode: errcode,
    code,
    message:
      {
        "408": "等待扫码",
        "404": "扫码成功，请在手机上确认登录",
        "405": "登录确认成功，正在换取 Token",
        "402": "二维码已过期，请刷新后重试",
        "403": "本次扫码已取消，请重新扫码"
      }[errcode] || "等待扫码",
    raw
  };
}

export function parseControlOptions(rawOptions: unknown): Array<{ Text: string; Value: string; IsOtherOption: boolean }> {
  if (!rawOptions) return [];
  let data = rawOptions;
  if (typeof rawOptions === "string") {
    try {
      data = JSON.parse(rawOptions);
    } catch {
      return rawOptions.trim() ? [{ Text: rawOptions.trim(), Value: rawOptions.trim(), IsOtherOption: false }] : [];
    }
  }
  if (data && typeof data === "object" && !Array.isArray(data)) {
    data = (data as Record<string, any>).Options || [];
  }
  if (!Array.isArray(data)) return [];
  return data.flatMap((item) => {
    if (typeof item === "string") {
      const text = item.trim();
      return text ? [{ Text: text, Value: text, IsOtherOption: false }] : [];
    }
    if (!item || typeof item !== "object") return [];
    const body = item as Record<string, any>;
    const text = String(body.Text || body.Name || body.Label || body.Value || "").trim();
    const value = String(body.Value || text).trim();
    return text ? [{ Text: text, Value: value, IsOtherOption: Boolean(body.IsOtherOption) }] : [];
  });
}

function makeRecordValue(fieldId: number): Record<string, any> {
  return {
    FieldId: fieldId,
    Values: [],
    Texts: [],
    OtherValue: "",
    MatrixValues: [],
    Files: [],
    Scores: [],
    HasValue: false,
    CustomTableValues: [],
    FillInMatrixFieldValues: [],
    MatrixFormValues: []
  };
}

function locationPayload(answer: JieLongFieldAnswer): Pick<Record<string, string[]>, "Values" | "Texts"> {
  const longitudeRaw = String(answer.longitude || "").trim();
  const latitudeRaw = String(answer.latitude || "").trim();
  if (!longitudeRaw || !latitudeRaw) throw new Error("请在表单中填写位置经纬度");
  const longitude = Number(longitudeRaw);
  const latitude = Number(latitudeRaw);
  if (!Number.isFinite(longitude) || !Number.isFinite(latitude)) throw new Error("位置字段的经纬度格式无效，请填写数字");
  const label = String(answer.value || "").trim() || `${latitude.toFixed(6)},${longitude.toFixed(6)}`;
  return {
    Values: [JSON.stringify({ latitude, longitude })],
    Texts: [label]
  };
}

function buildFieldRecord(field: JieLongField, answer: JieLongFieldAnswer): Record<string, any> | null {
  const fieldId = Number(field.Id || 0);
  const fieldType = Number(field.FieldType || 0);
  const required = Boolean(field.IsRequired);
  if (fieldId === 0) return null;
  const record = makeRecordValue(fieldId);
  const textValue = String(answer.value || "").trim();
  if (fieldType === 16) {
    if (!answer || !Object.keys(answer).length) {
      if (required) throw new Error(`${field.Name || "位置"} 为必填`);
      return null;
    }
    Object.assign(record, locationPayload(answer));
    record.HasValue = true;
    return record;
  }
  if (fieldType === 25) {
    const files = answer.files || [];
    if (!files.length) {
      if (required) throw new Error(`${field.Name || "文件"} 为必填，当前版本暂不支持上传`);
      return null;
    }
    record.Files = files;
    record.HasValue = true;
    return record;
  }
  const options = parseControlOptions(field.ControlOptions);
  if (options.length) {
    const selectedText = String(answer.option_text || "").trim();
    const selectedValue = String(answer.option_value || "").trim();
    if (!selectedText || !selectedValue) {
      if (required) throw new Error(`请选择 ${field.Name || "接龙选项"}`);
      return null;
    }
    record.Values = [selectedValue];
    record.Texts = [selectedText];
    record.OtherValue = String(answer.other_value || "").trim();
    record.HasValue = true;
    return record;
  }
  if (!textValue) {
    if (required) throw new Error(`请填写 ${field.Name || "必填字段"}`);
    return null;
  }
  record.Values = [textValue];
  record.Texts = [textValue];
  record.HasValue = true;
  return record;
}

export function buildSubmitPayload(
  bundle: JieLongFormBundle,
  fieldAnswers: Record<string, JieLongFieldAnswer>,
  signature = "",
  number = ""
): JieLongSubmitPayload {
  const thread = bundle.thread || {};
  const editDetail = bundle.edit_detail || {};
  const threadId = thread.ThreadId || editDetail.ThreadId;
  if (!threadId) throw new Error("未找到提交可用的 threadId");
  const resolvedSignature = String(signature || editDetail.LastSignature || editDetail.Signature || "").trim();
  if (!resolvedSignature) throw new Error("接龙缺少署名信息，请先填写姓名");
  const payload: JieLongSubmitPayload = {
    Id: 0,
    ThreadId: Number(threadId),
    Number: String(number || editDetail.Number || ""),
    Signature: resolvedSignature,
    RecordValues: [],
    DateTarget: "",
    IsNeedManualAudit: false,
    MinuteTarget: -1,
    IsNameNumberComfirm: false
  };
  for (const field of bundle.fields || []) {
    const record = buildFieldRecord(field, fieldAnswers[String(Number(field.Id || 0))] || {});
    if (record) payload.RecordValues.push(record);
  }
  return payload;
}
