import json
import logging
import mimetypes
import os
import re
import time
from copy import deepcopy
from typing import Any, Dict, List, Optional
import requests
from app.utils.files import check_img
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
    "attachment_cos_upload_policy": {
        "url": "https://api.jielong.com/api/Attachment/CosUploadPolicy",
        "payload": "par0NCtm+oBuEkBOI+w4657/Rp+uOyL1eVJwWmjKJP8JE18OvIuCRlAPTb0jXlPBm6E9VDx7BY4L2pQpNwZmgma1Be7gqP7v095SoUlcbQX2dcMzvifV/RWmwg5g/xw8NZ0bvxzthj35C+mDtjT7TbW7E0KRSxhkVP30PsXnIBKqCTTHMgIBjoUKP3ZEP3dh+ECW2pY+H4mYLMbDqp7NUEsdoMxmgO6T07srpzelu5y9Ou7IDXBNrMAGQH93vq7HhG+BYqR4tktlPMTSsBk9Yw==",
    },
}
JIELONG_QR_OPENAUTH_URL = "https://i-api.jielong.com/api/User/OpenAuth"
JIELONG_QR_OPENAUTH_REQUEST_PAYLOAD = (
    "par0NCtm+oBuEkBOI+w465ziSpJ1q2mHTwrJUpSxsfAX1QxuVPVW2/9V4YvOWp6AQlKmpxnUrPCFYO0fx0CgXQ4Z"
    "EIEYYAPCsJhmBtt7bkXykLpl6C2P/mlQmYWuYhs6JwqmgnsXGYfJGorQSmikaKm6Bz5zAhwLgxbKzVz8gWO887Hh"
    "dLmrG1GoYU1uBil8oBCAaUviVwIY5orn4jkb6aKE/En/cwBqyfeZMCF3BcBTzMLzfWeoi1JfOL7GNHeTp/DcIPrqr0x"
    "9vs1bY0KMiA=="
)
JIELONG_QR_CONNECT_URL = "https://open.weixin.qq.com/connect/qrconnect"
JIELONG_QR_POLL_URL = "https://lp.open.weixin.qq.com/connect/l/qrconnect"
JIELONG_QR_CODE_URL = "https://open.weixin.qq.com/connect/qrcode/{uuid}"
JIELONG_QR_APP_ID = "wx4a23ae4b8f291087"
JIELONG_QR_REDIRECT_URI = "https://i.jielong.com/login-callback"
JIELONG_QR_STYLE_HREF = (
    "data:text/css;base64,Ci5pbXBvd2VyQm94IC5xcmNvZGUgewogIHdpZHRoOiAzMDBweDsKICBib3JkZXI6IG5vbmU7Cn0K"
    "LmltcG93ZXJCb3ggLnRpdGxlIHsKICBkaXNwbGF5OiBub25lOwp9Ci5pbXBvd2VyQm94IC5pbmZvIHsKICBkaXNwbGF5"
    "OiBub25lOwp9Ci5pbXBvd2VyQm94IC5xcmNvZGUgewogIG1hcmdpbi10b3A6IDBweCAhaW1wb3J0YW50Owp9Ci5zdGF0"
    "dXNfaWNvbiB7CiAgZGlzcGxheTogbm9uZTsKfQouanNfcXVpY2tfbG9naW4gewogIG1hcmdpbi10b3A6IDUwcHg7Cn0="
)
JIELONG_QR_STATUS_TEXT = {
    "408": "等待扫码",
    "404": "扫码成功，请在手机上确认登录",
    "405": "登录确认成功，正在换取 Token",
    "402": "二维码已过期，请刷新后重试",
    "403": "本次扫码已取消，请重新扫码",
}
NAME_KEYS = ("姓名", "名字")
STUDENT_NO_KEY = "学号"
JOB_NO_KEY = "工号"
MOBILE_KEY = "手机"
EMAIL_KEY = "邮箱"
ADDRESS_KEY = "地址"
JIELONG_TENANT_TYPE_ID = "300221"
JIELONG_YUN_STORE = 2
def normalize_authorization(token: str) -> str:
    token = str(token or "").strip()
    if not token:
        raise RuntimeError("请先填写接龙 Bearer Token")
    if not token.lower().startswith("bearer "):
        token = f"Bearer {token}"
    return token
def get_thread_id_by_url(url: str) -> str:
    share_url = str(url or "").strip()
    if not share_url:
        raise RuntimeError("请先粘贴接龙分享链接")
    logging.info("[JieLong] ===== PARSE SHARE URL =====")
    logging.info("[JieLong] GET %s", share_url)
    response = requests.get(share_url, allow_redirects=False, timeout=12)
    location = str(response.headers.get("Location") or "").strip()
    logging.info("[JieLong] redirect: %s", location or "<empty>")
    if not location:
        raise RuntimeError("分享链接解析失败：未拿到跳转地址")
    thread_id = location.rstrip("/").split("/")[-1].split("?")[0].strip()
    if not thread_id:
        raise RuntimeError("分享链接解析失败：未拿到 thread_id")
    return thread_id
def normalize_thread_id(thread_id: str) -> str:
    thread_id = str(thread_id or "").strip()
    if not thread_id:
        raise RuntimeError("请先填写接龙 threadId")
    return thread_id
def normalize_login_code(code: str) -> str:
    code = str(code or "").strip()
    if not code:
        raise RuntimeError("未获取到接龙登录 code")
    return code
def _build_qr_openauth_headers() -> Dict[str, str]:
    return {
        "accept": "application/json, text/plain, */*",
        "accept-language": "zh-CN,zh;q=0.9",
        "authorization": "undefined",
        "cache-control": "no-cache",
        "content-length": "0",
        "content-type": "application/x-www-form-urlencoded",
        "origin": "https://i.jielong.com",
        "platform": "pc",
        "pragma": "no-cache",
        "priority": "u=1, i",
        "referer": "https://i.jielong.com/",
        "sec-ch-ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
        "x-api-request-mode": "cors",
        "x-api-request-payload": JIELONG_QR_OPENAUTH_REQUEST_PAYLOAD,
    }
def exchange_qr_login_token(code: str) -> Dict[str, Any]:
    params = {"code": normalize_login_code(code)}
    _log_request("POST", JIELONG_QR_OPENAUTH_URL, params=params)
    response = requests.post(
        JIELONG_QR_OPENAUTH_URL,
        headers=_build_qr_openauth_headers(),
        params=params,
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()
    _log_response("POST", JIELONG_QR_OPENAUTH_URL, data)
    if data.get("Type") != "000001":
        raise RuntimeError(_normalize_api_error(_extract_api_message(data) or "接龙登录失败"))
    return data
def exchange_login_token(
    code: str,
    authorization: str = "",
    q_code: str = "",
    capture_payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    capture_payload = capture_payload or {}
    q_code_value = str(q_code or capture_payload.get("qCode") or "")
    response = requests.post(
        JIELONG_LOGIN_URL,
        headers=_build_login_headers(authorization="", capture_payload=capture_payload),
        data=json.dumps(
            {
                "code": normalize_login_code(code),
                "qCode": q_code_value,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()
    if data.get("Type") != "000001":
        raise RuntimeError(data.get("Description") or "接龙登录失败")
    return data
def create_qr_login() -> Dict[str, str]:
    now_ms = int(time.time() * 1000)
    response = requests.get(
        JIELONG_QR_CONNECT_URL,
        headers={
            "accept": "application/xml, text/xml, */*; q=0.01",
            "accept-language": "zh-CN,zh;q=0.9",
            "cache-control": "no-cache",
            "pragma": "no-cache",
            "priority": "u=1, i",
            "referer": (
                "https://open.weixin.qq.com/connect/qrconnect"
                f"?appid={JIELONG_QR_APP_ID}&scope=snsapi_login"
                f"&redirect_uri={JIELONG_QR_REDIRECT_URI}"
            ),
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
            ),
            "x-requested-with": "XMLHttpRequest",
        },
        params={
            "appid": JIELONG_QR_APP_ID,
            "scope": "snsapi_login",
            "redirect_uri": JIELONG_QR_REDIRECT_URI,
            "state": "",
            "login_type": "jssdk",
            "self_redirect": "true",
            "styletype": "",
            "sizetype": "",
            "bgcolor": "",
            "rst": "",
            "ts": now_ms,
            "style": "black",
            "href": JIELONG_QR_STYLE_HREF,
            "f": "xml",
            "_": now_ms,
        },
        timeout=12,
    )
    response.raise_for_status()
    match = re.search(r"<uuid><!\[CDATA\[(.*?)\]\]></uuid>", response.text)
    if not match:
        raise RuntimeError("未获取到接龙二维码 UUID")
    uuid = match.group(1).strip()
    if not uuid:
        raise RuntimeError("接龙二维码 UUID 为空")
    return {
        "uuid": uuid,
        "qrcode_url": JIELONG_QR_CODE_URL.format(uuid=uuid),
    }
def download_qrcode_image(qrcode_url: str) -> bytes:
    response = requests.get(qrcode_url, timeout=12)
    response.raise_for_status()
    return response.content
def poll_qr_login(uuid: str) -> Dict[str, Any]:
    response = requests.get(
        JIELONG_QR_POLL_URL,
        headers={
            "accept": "*/*",
            "accept-language": "zh-CN,zh;q=0.9",
            "cache-control": "no-cache",
            "pragma": "no-cache",
            "referer": "https://open.weixin.qq.com/",
            "sec-fetch-dest": "script",
            "sec-fetch-mode": "no-cors",
            "sec-fetch-site": "same-site",
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
            ),
        },
        params={
            "uuid": str(uuid or "").strip(),
            "_": int(time.time() * 1000),
        },
        timeout=12,
    )
    response.raise_for_status()
    text = response.text or ""
    errcode_match = re.search(r"window\.wx_errcode=(\d+);", text)
    errcode = errcode_match.group(1) if errcode_match else ""
    code_match = re.search(r"window\.wx_code='(.*?)'", text)
    wx_code = code_match.group(1).strip() if code_match else ""
    status = "waiting"
    if wx_code:
        status = "confirmed"
    elif errcode == "404":
        status = "scanned"
    elif errcode in {"402", "403"}:
        status = "expired"
    elif errcode and errcode != "408":
        status = "error"
    return {
        "status": status,
        "wx_errcode": errcode,
        "code": wx_code,
        "message": JIELONG_QR_STATUS_TEXT.get(errcode, "等待扫码"),
        "raw": text,
    }
def _mask_token(token: str) -> str:
    token = str(token or "").strip()
    if not token:
        return "<empty>"
    if len(token) <= 18:
        return token
    return f"{token[:10]}...{token[-6:]}"
def _extract_api_message(data: Any) -> str:
    if not isinstance(data, dict):
        return str(data or "").strip()
    for key in ("Description", "description", "Msg", "msg", "Message", "message", "error"):
        value = data.get(key)
        if str(value or "").strip():
            return str(value).strip()
    nested = data.get("Data") or data.get("data")
    if isinstance(nested, dict):
        for key in ("Description", "description", "Msg", "msg", "Message", "message", "error"):
            value = nested.get(key)
            if str(value or "").strip():
                return str(value).strip()
    if isinstance(nested, str) and nested.strip():
        return nested.strip()
    return ""
def _normalize_api_error(message: str) -> str:
    text = str(message or "").strip()
    lower = text.lower()
    if (
        "未登录" in text
        or "请先登录" in text
        or "登录" in text
        or "授权验证失败" in text
        or "token" in lower
        or "authorization" in lower
        or "bearer" in lower
    ):
        return f"{text}；当前 Token 可能无效、已过期，或不是该接龙可用的 Token"
    return text


def _log_request(method: str, url: str, *, params: Optional[Dict[str, Any]] = None, payload: Optional[Dict[str, Any]] = None, token: str = "") -> None:
    logging.info("[JieLong] ===== REQUEST =====")
    logging.info("[JieLong] %s %s", method, url)
    if params is not None:
        logging.info("[JieLong] params: %s", json.dumps(params, ensure_ascii=False, separators=(",", ":")))
    if payload is not None:
        logging.info("[JieLong] body: %s", json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    if token:
        logging.info("[JieLong] authorization: %s", _mask_token(token))
def _log_response(method: str, url: str, data: Any) -> None:
    try:
        rendered = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    except TypeError:
        rendered = str(data)
    logging.info("[JieLong] ===== RESPONSE =====")
    logging.info("[JieLong] %s %s", method, url)
    logging.info("[JieLong] data: %s", rendered)
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
    request_params = params or {}
    _log_request("GET", endpoint["url"], params=request_params, token=token)
    response = requests.get(
        endpoint["url"],
        headers=_build_headers(token, endpoint_key),
        params=request_params,
        timeout=12,
    )
    response.raise_for_status()
    data = response.json()
    _log_response("GET", endpoint["url"], data)
    if data.get("Type") != "000001":
        raise RuntimeError(_normalize_api_error(_extract_api_message(data) or f"{endpoint_key} 接口返回异常"))
    return data


def _post_json(endpoint_key: str, token: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    endpoint = JIELONG_ENDPOINTS[endpoint_key]
    _log_request("POST", endpoint["url"], payload=payload, token=token)
    response = requests.post(
        endpoint["url"],
        headers=_build_headers(token, endpoint_key),
        data=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()
    _log_response("POST", endpoint["url"], data)
    if data.get("Type") != "000001":
        raise RuntimeError(_normalize_api_error(_extract_api_message(data) or f"{endpoint_key} 接口返回异常"))
    return data


def fetch_attachment_cos_upload_policy(token: str, thread_id: int, file_name: str) -> Dict[str, Any]:
    return _post_json(
        "attachment_cos_upload_policy",
        token,
        {
            "tenantTypeId": JIELONG_TENANT_TYPE_ID,
            "fileName": file_name,
            "associateId": int(thread_id),
            "yunStore": JIELONG_YUN_STORE,
        },
    )
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
def _extract_field_files(field: Dict[str, Any], draft_map: Dict[str, Any]) -> List[Dict[str, Any]]:
    draft_item = draft_map.get(str(field.get("Id")))
    if not isinstance(draft_item, dict):
        return []
    value = draft_item.get("value") or {}
    files = value.get("Files") or draft_item.get("Files") or []
    if isinstance(files, list):
        return deepcopy(files)
    return []
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
        current["InitialFiles"] = _extract_field_files(current, draft_map)
        rendered_fields.append(current)
    return rendered_fields
def build_local_media_files(image_paths: List[str]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for raw_path in image_paths or []:
        path = check_img(raw_path)
        mime, _ = mimetypes.guess_type(path)
        result.append(
            {
                "Name": os.path.basename(path),
                "FileName": os.path.basename(path),
                "ContentType": mime or "image/jpeg",
                "Size": os.path.getsize(path),
                "LocalPath": path,
            }
        )
    return result
def upload_media_file(token: str, thread_id: int, file_info: Dict[str, Any]) -> Dict[str, Any]:
    local_path = str(file_info.get("LocalPath") or "").strip()
    if not local_path:
        raise RuntimeError("图片上传缺少本地文件路径")
    local_path = check_img(local_path)
    source_name = str(file_info.get("FileName") or file_info.get("Name") or os.path.basename(local_path)).strip()
    if not source_name:
        source_name = os.path.basename(local_path)
    policy_resp = fetch_attachment_cos_upload_policy(token, thread_id, source_name)
    policy_data = policy_resp.get("Data") or {}
    upload_host = str(policy_data.get("Host") or "").strip()
    if not upload_host:
        raise RuntimeError("未获取到接龙图片上传地址")
    mime = str(file_info.get("ContentType") or mimetypes.guess_type(local_path)[0] or "image/jpeg")
    with open(local_path, "rb") as file_obj:
        response = requests.post(
            upload_host,
            data={
                "key": policy_data.get("Key") or "",
                "success_action_status": "200",
                "policy": policy_data.get("Policy") or "",
                "Content-Type": policy_data.get("ContentType") or mime,
                "q-sign-algorithm": policy_data.get("Algorithm") or "",
                "q-ak": policy_data.get("Ak") or "",
                "q-key-time": policy_data.get("KeyTime") or "",
                "q-signature": policy_data.get("Signature") or "",
                "x-cos-callback": policy_data.get("Callback") or "",
            },
            files={
                "file": (source_name, file_obj, mime),
            },
            headers={
                "referer": JIELONG_REFERER,
                "user-agent": JIELONG_USER_AGENT,
            },
            timeout=30,
        )
    response.raise_for_status()
    upload_data = response.json()
    if upload_data.get("Type") != "000001":
        raise RuntimeError(upload_data.get("Description") or "接龙图片上传失败")
    remote_file = upload_data.get("Data") or {}
    remote_file["IsNewUpload"] = True
    return remote_file
def prepare_submit_payload(token: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    prepared = deepcopy(payload)
    thread_id = int(prepared.get("ThreadId") or 0)
    if not thread_id:
        raise RuntimeError("未找到提交可用的 threadId")
    for record in prepared.get("RecordValues") or []:
        files = record.get("Files") or []
        if not files:
            continue
        uploaded_files = []
        for file_info in files:
            if file_info.get("RelativePath") and not file_info.get("LocalPath"):
                uploaded_files.append(file_info)
                continue
            uploaded_files.append(upload_media_file(token, thread_id, file_info))
        record["Files"] = uploaded_files
        record["HasValue"] = bool(
            record.get("HasValue")
            or record.get("Texts")
            or record.get("Values")
            or uploaded_files
        )
    return prepared
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
def _location_payload(answer: Dict[str, Any]) -> Dict[str, List[str]]:
    text_value = str(answer.get("value") or "").strip()
    longitude_raw = str(answer.get("longitude") or "").strip()
    latitude_raw = str(answer.get("latitude") or "").strip()
    if not longitude_raw or not latitude_raw:
        raise RuntimeError("请在表单中填写位置经纬度")
    try:
        longitude = float(longitude_raw)
        latitude = float(latitude_raw)
    except (TypeError, ValueError):
        raise RuntimeError("位置字段的经纬度格式无效，请填写数字")
    location_value = json.dumps(
        {"latitude": latitude, "longitude": longitude},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    label = text_value or f"{latitude:.6f},{longitude:.6f}"
    return {"Values": [location_value], "Texts": [label]}
def _build_field_record(
    field: Dict[str, Any],
    answer: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    field_id = int(field.get("Id") or 0)
    field_type = int(field.get("FieldType") or 0)
    required = bool(field.get("IsRequired"))
    if field_id == 0:
        return None
    record = _make_record_value(field_id)
    text_value = str(answer.get("value") or "").strip()
    if field_type == 16:
        if not answer:
            if required:
                raise RuntimeError(f"{field.get('Name') or '位置'} 为必填")
            return None
        record.update(_location_payload(answer))
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
        )
        if record:
            payload["RecordValues"].append(record)
    return payload
def load_form_bundle(token: str, thread_id: str) -> Dict[str, Any]:
    # 这 4 个请求当前都仍然在用：
    # - detail: 主题/时间/接龙状态
    # - form_info: 姓名等内建字段默认值
    # - edit_record_detail: 接龙字段结构
    # - record_draft: 已有草稿值/已传文件回填
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
    # 仅保留 UI 真正消费的数据；原始 detail/form_info/draft_map 响应暂不继续透传。
    return {
        "thread": thread_data,
        "check_in": detail_data.get("CheckIn") or {},
        "edit_detail": edit_detail_data,
        "fields": build_render_fields(edit_detail_data, draft_map, form_info_data),
    }
def submit_record(token: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    prepared_payload = prepare_submit_payload(token, payload)
    return _post_json("edit_record", token, prepared_payload)
