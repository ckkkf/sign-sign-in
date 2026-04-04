import json
from copy import deepcopy
from typing import Any, Dict, List, Optional

import requests


JIELONG_REFERER = "https://servicewechat.com/wx8027adefde914aa3/463/page-frame.html"
JIELONG_REQUEST_REFERER = "https://servicewechat.com/wx8027adefde914aa3"
JIELONG_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 "
    "MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI "
    "MiniProgramEnv/Windows WindowsWechat/WMPF WindowsWechat(0x63090a13) "
    "UnifiedPCWindowsWechat(0xf254181d) XWEB/19201"
)

JIELONG_ENDPOINTS = {
    "detail": {
        "url": "https://api.jielong.com/api/CheckIn/Detail",
        "payload": "par0NCtm+oBuEkBOI+w464RegjsQ/qtwdXVV59qer75djTR6N2ImzP+0o0k9HhhQAAGiVmy9pb6iRb6XwvCi1f/ogbSz1XGrZvZ3RntW9rfGpQ5fNPzKU2TY1k3f+Gfc7R8PtqkDQfAI+NorxafDCs400l35i7y2ABvUjZ0RA4fOqVK9BTq1AS8CqkOyQpji50o46SrH+xt0D9y8VnXEJFMay0LOWtyYSiKyQiVI/UkRIn8WWE0xNIXzaTW3EKzH",
    },
    "form_info": {
        "url": "https://api.jielong.com/api/User/Forminfo",
        "payload": "par0NCtm+oBuEkBOI+w469O3sv7VkPQdbSZ/b146+eR59OABQtitF7jAqrza2ox4D4RUAVssL7FhoL1xIV03g90epOmj7/zKW23Ao+J5BAEGYocngDSjVMXZUnbfFG7Ka21uQjcid9Iv4VRj0yyX4qeQZRZ58wFUsW13wCd1BhHqMkS3WmJxnSq51iAEzmtIywg1nPDwc1WM4+a3Gs2ubdCQG4imuCrQbGjz0jbl7yWcPNmOGy1vHpMP7yVoRowO",
    },
    "edit_record_detail": {
        "url": "https://api.jielong.com/api/CheckIn/EditRecordDetail",
        "payload": "par0NCtm+oBuEkBOI+w46xC2JxFsUHr7SyrC3zgfsFRdL3quyfUfhuyIRBhO9FmaAHCkxrmR+Y8KV+pSK3WhZTAl1nZ8aRtzx661t3uyOpKGc+BcbvLB2PJv30vser4F6CzcBP5PF+CXH8dO7iQaZPU+mmL8+Ci5nCSws2n0vzDdkI3oRoLp868ykBb0MWaz053J0Of4UV7H9mlCHgaxeN2LYxa0ljj4Pw5OX1eXSl5BfnE8uC2drThjiNfqduTy",
    },
    "record_draft": {
        "url": "https://api.jielong.com/api/Thread/RecordDraft",
        "payload": "par0NCtm+oBuEkBOI+w466ekfU0HwI5JL1d8CmzerE+Yyoq84vMN0LThT6W4RqPFl8vrmFFhE+M2ceXZoj2aFFXKgAL+N3UNqwzEhy1Xam6Oik/AVQvHtVJ72U4BvWaHuSXv5QdX2zFgFrF4q7dZINK7Dbvx5fmnn78ba7yDrizlAEgeSUUtEGe1QRRHPvj/Mx5RR8Ww3HTpZgLyTIsIPdlZyO5xdUhYWnINW81BQ+ueYA/BMXsFSBwL4qL3WhiWcDgwQRub0VF3LIGM6gbZKA==",
    },
    "edit_record": {
        "url": "https://api.jielong.com/api/CheckIn/EditRecord",
        "payload": "par0NCtm+oBuEkBOI+w461REzcksEiTE3hYAk2qfDuRAORiAFZFU7iBYoEM7RQf68ggrRgHuyBaQYOQX/Bvsj4Tfe4v/NXbmh0NRDWr+C61L+mYkFKfSm3KdWIfsgZeHDoYZbM5ZZxa5lXSpJps8l4EDpJDZ7RRuQ0bH8yNkoV5/5K5+GRsesQmNSCB873E3qpT3GLmuYdZ7jlI1n1FRwQ2/zHiPpu3sJ8XpzH82+IUFG6pu9n+2sIOZ1tUaouq4",
    },
}


NAME_KEYS = ("姓名", "名字")
STUDENT_NO_KEY = "学号"
JOB_NO_KEY = "工号"
MOBILE_KEY = "手机"
EMAIL_KEY = "邮箱"
ADDRESS_KEY = "地址"


def normalize_authorization(token: str) -> str:
    token = str(token or "").strip()
    if not token:
        raise RuntimeError("请先填写接龙 Bearer Token")
    if not token.lower().startswith("bearer "):
        token = f"Bearer {token}"
    return token


def normalize_thread_id(thread_id: str) -> str:
    thread_id = str(thread_id or "").strip()
    if not thread_id:
        raise RuntimeError("请先填写接龙 threadId")
    return thread_id


def _build_headers(token: str, endpoint_key: str) -> Dict[str, str]:
    payload = JIELONG_ENDPOINTS[endpoint_key]["payload"]
    return {
        "accept": "*/*",
        "accept-language": "zh-CN,zh;q=0.9",
        "authorization": normalize_authorization(token),
        "cache-control": "no-cache",
        "content-type": "application/json",
        "platform": "wx_bak",
        "pragma": "no-cache",
        "referer": JIELONG_REFERER,
        "user-agent": JIELONG_USER_AGENT,
        "x-api-request-mode": "cors",
        "x-api-request-payload": payload,
        "x-api-request-referer": JIELONG_REQUEST_REFERER,
        "xweb_xhr": "1",
    }


def _request_json(endpoint_key: str, token: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    endpoint = JIELONG_ENDPOINTS[endpoint_key]
    response = requests.get(
        endpoint["url"],
        headers=_build_headers(token, endpoint_key),
        params=params or {},
        timeout=12,
    )
    response.raise_for_status()
    data = response.json()
    if data.get("Type") != "000001":
        raise RuntimeError(data.get("Description") or f"{endpoint_key} 接口返回异常")
    return data


def _post_json(endpoint_key: str, token: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    endpoint = JIELONG_ENDPOINTS[endpoint_key]
    response = requests.post(
        endpoint["url"],
        headers=_build_headers(token, endpoint_key),
        data=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()
    if data.get("Type") != "000001":
        raise RuntimeError(data.get("Description") or f"{endpoint_key} 接口返回异常")
    return data


def fetch_detail(token: str, thread_id: str) -> Dict[str, Any]:
    return _request_json("detail", token, {"threadId": normalize_thread_id(thread_id)})


def fetch_form_info(token: str) -> Dict[str, Any]:
    return _request_json("form_info", token)


def fetch_edit_record_detail(token: str, thread_id: int) -> Dict[str, Any]:
    return _request_json(
        "edit_record_detail",
        token,
        {
            "threadId": str(thread_id),
            "recordId": "0",
            "isFillCheckIn": "false",
            "fillSignature": "",
            "fillNumber": "0",
        },
    )


def fetch_record_draft(token: str, thread_id: int) -> Dict[str, Any]:
    return _request_json("record_draft", token, {"ThreadId": str(thread_id)})


def _parse_draft_content(draft_data: Dict[str, Any]) -> Dict[str, Any]:
    content = ((draft_data or {}).get("Data") or {}).get("Content")
    if not content:
        return {}
    try:
        return json.loads(content)
    except Exception:
        return {}


def _first_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
        return " / ".join(items)
    return str(value).strip()


def parse_control_options(raw_options: Any) -> List[Dict[str, Any]]:
    if not raw_options:
        return []
    data = raw_options
    if isinstance(raw_options, str):
        try:
            data = json.loads(raw_options)
        except Exception:
            return [{"Text": raw_options, "Value": raw_options, "IsOtherOption": False}]
    if isinstance(data, dict):
        data = data.get("Options") or []
    if not isinstance(data, list):
        return []

    result: List[Dict[str, Any]] = []
    for item in data:
        if isinstance(item, str):
            text = item.strip()
            if text:
                result.append({"Text": text, "Value": text, "IsOtherOption": False})
            continue
        if not isinstance(item, dict):
            continue
        text = str(item.get("Text") or item.get("Name") or item.get("Label") or item.get("Value") or "").strip()
        value = str(item.get("Value") or text).strip()
        if text:
            result.append(
                {
                    "Text": text,
                    "Value": value,
                    "IsOtherOption": bool(item.get("IsOtherOption")),
                }
            )
    return result


def _resolve_builtin_value(field: Dict[str, Any], form_info_data: Dict[str, Any]) -> str:
    form_info = (form_info_data or {}).get("FormInfo") or {}
    nickname = (form_info_data or {}).get("Nickname") or ""
    name = str(field.get("Name") or "")
    field_id = int(field.get("Id") or 0)

    if field_id == 0 or any(key in name for key in NAME_KEYS):
        return _first_text(
            form_info.get("FormUserName")
            or form_info.get("Name")
            or form_info.get("Author")
            or nickname
        )
    if STUDENT_NO_KEY in name:
        return _first_text(form_info.get("StudentNumber"))
    if JOB_NO_KEY in name:
        return _first_text(form_info.get("JobNumber"))
    if MOBILE_KEY in name:
        return _first_text(form_info.get("Moblie"))
    if EMAIL_KEY in name:
        return _first_text(form_info.get("Email"))
    if ADDRESS_KEY in name:
        return _first_text(form_info.get("Address"))
    return ""


def _extract_field_value(field: Dict[str, Any], draft_map: Dict[str, Any], form_info_data: Dict[str, Any]) -> str:
    draft_item = draft_map.get(str(field.get("Id")))
    if isinstance(draft_item, dict):
        value = draft_item.get("value") or {}
        text = _first_text(value.get("Texts"))
        if text:
            return text
        text = _first_text(value.get("Values"))
        if text:
            return text
        text = _first_text(value.get("OtherValue"))
        if text:
            return text

    default_value = _first_text(field.get("Defaultvalue"))
    if default_value:
        return default_value

    return _resolve_builtin_value(field, form_info_data)


def build_render_fields(edit_detail_data: Dict[str, Any], draft_map: Dict[str, Any], form_info_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    check_in_setting = (edit_detail_data or {}).get("CheckInSetting") or {}
    fields: List[Dict[str, Any]] = []

    signature = check_in_setting.get("Signature")
    if isinstance(signature, dict):
        fields.append(signature)

    for item in check_in_setting.get("Settings") or []:
        if isinstance(item, dict):
            fields.append(item)

    rendered_fields = []
    for field in fields:
        current = deepcopy(field)
        current["InitialValue"] = _extract_field_value(current, draft_map, form_info_data)
        rendered_fields.append(current)
    return rendered_fields


def _make_record_value(field_id: int) -> Dict[str, Any]:
    return {
        "FieldId": field_id,
        "Values": [],
        "Texts": [],
        "OtherValue": "",
        "MatrixValues": [],
        "Files": [],
        "Scores": [],
        "HasValue": False,
        "CustomTableValues": [],
        "FillInMatrixFieldValues": [],
        "MatrixFormValues": [],
    }


def _stringify_field_id(field_id: Any) -> str:
    return str(int(field_id or 0))


def _get_field_answer(field_answers: Dict[str, Dict[str, Any]], field_id: Any) -> Dict[str, Any]:
    return field_answers.get(_stringify_field_id(field_id)) or {}


def _location_payload(location: Dict[str, Any], text: str) -> Dict[str, List[str]]:
    if not isinstance(location, dict):
        raise RuntimeError("缺少接龙定位坐标，请先在配置中填写经纬度")
    try:
        longitude = float(location.get("longitude"))
        latitude = float(location.get("latitude"))
    except (TypeError, ValueError):
        raise RuntimeError("接龙位置字段需要有效的经纬度配置")
    location_value = json.dumps(
        {"latitude": latitude, "longitude": longitude},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    label = str(text or "").strip() or f"{latitude:.6f},{longitude:.6f}"
    return {"Values": [location_value], "Texts": [label]}


def _build_field_record(
    field: Dict[str, Any],
    answer: Dict[str, Any],
    *,
    location: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    field_id = int(field.get("Id") or 0)
    field_type = int(field.get("FieldType") or 0)
    required = bool(field.get("IsRequired"))

    if field_id == 0:
        return None

    record = _make_record_value(field_id)
    text_value = str(answer.get("value") or "").strip()

    if field_type == 16:
        if not location:
            if required:
                raise RuntimeError(f"{field.get('Name') or '位置'} 为必填，但当前未配置经纬度")
            return None
        record.update(_location_payload(location, text_value))
        record["HasValue"] = True
        return record

    if field_type == 25:
        files = answer.get("files") or []
        if not files:
            if required:
                raise RuntimeError(f"{field.get('Name') or '文件'} 为必填，当前版本暂不支持上传")
            return None
        record["Files"] = files
        record["HasValue"] = True
        return record

    options = parse_control_options(field.get("ControlOptions"))
    if options:
        selected_text = str(answer.get("option_text") or "").strip()
        selected_value = str(answer.get("option_value") or "").strip()
        if not selected_text or not selected_value:
            if required:
                raise RuntimeError(f"请选择 {field.get('Name') or '接龙选项'}")
            return None
        record["Values"] = [selected_value]
        record["Texts"] = [selected_text]
        record["OtherValue"] = str(answer.get("other_value") or "").strip()
        record["HasValue"] = True
        return record

    if not text_value:
        if required:
            raise RuntimeError(f"请填写 {field.get('Name') or '必填字段'}")
        return None

    record["Values"] = [text_value]
    record["Texts"] = [text_value]
    record["HasValue"] = True
    return record


def build_submit_payload(
    bundle: Dict[str, Any],
    field_answers: Dict[str, Dict[str, Any]],
    *,
    signature: str = "",
    number: str = "",
    location: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    thread = bundle.get("thread") or {}
    edit_detail = (bundle.get("edit_detail") or {}).copy()
    thread_id = thread.get("ThreadId") or edit_detail.get("ThreadId")
    if not thread_id:
        raise RuntimeError("未找到提交可用的 threadId")

    resolved_signature = str(signature or edit_detail.get("LastSignature") or edit_detail.get("Signature") or "").strip()
    if not resolved_signature:
        raise RuntimeError("接龙缺少署名信息，请先填写姓名")

    payload = {
        "Id": 0,
        "ThreadId": int(thread_id),
        "Number": str(number or edit_detail.get("Number") or ""),
        "Signature": resolved_signature,
        "RecordValues": [],
        "DateTarget": "",
        "IsNeedManualAudit": False,
        "MinuteTarget": -1,
        "IsNameNumberComfirm": False,
    }

    for field in bundle.get("fields") or []:
        record = _build_field_record(
            field,
            _get_field_answer(field_answers, field.get("Id")),
            location=location,
        )
        if record:
            payload["RecordValues"].append(record)

    return payload


def load_form_bundle(token: str, thread_id: str) -> Dict[str, Any]:
    detail_resp = fetch_detail(token, thread_id)
    detail_data = detail_resp.get("Data") or {}
    thread_data = detail_data.get("Thread") or {}
    numeric_thread_id = thread_data.get("ThreadId")
    if not numeric_thread_id:
        raise RuntimeError("未从接龙详情中拿到数字 threadId")

    form_info_resp = fetch_form_info(token)
    form_info_data = form_info_resp.get("Data") or {}

    edit_detail_resp = fetch_edit_record_detail(token, int(numeric_thread_id))
    edit_detail_data = edit_detail_resp.get("Data") or {}

    draft_resp = fetch_record_draft(token, int(numeric_thread_id))
    draft_map = _parse_draft_content(draft_resp)

    return {
        "detail": detail_data,
        "thread": thread_data,
        "check_in": detail_data.get("CheckIn") or {},
        "form_info": form_info_data,
        "edit_detail": edit_detail_data,
        "draft_map": draft_map,
        "fields": build_render_fields(edit_detail_data, draft_map, form_info_data),
    }


def submit_record(token: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    return _post_json("edit_record", token, payload)
