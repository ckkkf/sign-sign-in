import json
import logging
import re
from typing import Any, Dict
from urllib.parse import quote

import requests

from app.config.common import LAISHIXI_APP_LOGIN_URL, LAISHIXI_BASE_PATH, LAISHIXI_REFERER
from app.utils.files import get_valid_laishixi_session_cache, save_laishixi_session_cache


def _mask(value: str, keep: int = 6) -> str:
    text = str(value or "")
    if len(text) <= keep:
        return text
    return f"{text[:keep]}...{text[-4:]}"


def _headers(config: Dict[str, Any]) -> Dict[str, str]:
    user_agent = str(config.get("userAgent") or "").strip()
    headers = {
        "content-type": "application/x-www-form-urlencoded;charset=utf-8",
        "referer": LAISHIXI_REFERER,
    }
    if user_agent:
        headers["user-agent"] = user_agent
    return headers


def _post_app_login(action: str, payload: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    data = {
        "action": action,
        "key": json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        "p": "5",
        "cypher": "false",
    }
    logging.debug("Laishixi appLogin request: action=%s, key=%s", action, _mask(data["key"], 24))
    response = requests.post(
        LAISHIXI_APP_LOGIN_URL,
        headers=_headers(config),
        data=data,
        timeout=10,
    )
    response.raise_for_status()
    try:
        result = response.json()
    except ValueError as exc:
        raise RuntimeError("Laishixi appLogin returned non-JSON response") from exc
    logging.debug("Laishixi appLogin response: action=%s, keys=%s", action, list(result.keys()) if isinstance(result, dict) else type(result))
    if not isinstance(result, dict):
        raise RuntimeError("Laishixi appLogin response shape is invalid")
    return result


def _extract_openid(result: Dict[str, Any]) -> str:
    for key in ("openid", "openId"):
        value = str(result.get(key) or "").strip()
        if value:
            return value
    data = result.get("data")
    if isinstance(data, dict):
        for key in ("openid", "openId"):
            value = str(data.get(key) or "").strip()
            if value:
                return value
    raise RuntimeError("Laishixi autoWechat did not return openid")


def _is_login_success(result: Dict[str, Any]) -> bool:
    if result.get("success") is True:
        return True
    data = result.get("data")
    if isinstance(data, dict) and data.get("success") is True:
        return True
    return False


def _build_position(location: Dict[str, Any]) -> Dict[str, Any]:
    try:
        latitude = float(str(location.get("latitude")).strip())
        longitude = float(str(location.get("longitude")).strip())
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Laishixi location is invalid; configure latitude and longitude first") from exc
    return {
        "errMsg": "getLocation:ok",
        "latitude": latitude,
        "longitude": longitude,
        "speed": -1,
        "accuracy": 65,
        "altitude": 0,
        "verticalAccuracy": 65,
        "horizontalAccuracy": 65,
    }


def _summarize_html(html: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", html or "", flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = " ".join(text.split())
    return text[:180] if text else "no readable page text"


def login(config: Dict[str, Any], use_cache: bool = True) -> Dict[str, Any]:
    if use_cache:
        cached = get_valid_laishixi_session_cache()
        if cached:
            logging.info("Using cached Laishixi openid")
            return cached

    code = str(config.get("code") or "").strip()
    if not code:
        raise RuntimeError("Missing Laishixi wx.login code; click get-code first")

    openid_result = _post_app_login("autoWechat", {"code": code}, config)
    openid = _extract_openid(openid_result)
    logging.info("Laishixi openid acquired: %s", _mask(openid))

    check_result = _post_app_login("checklogin", {"openid": openid}, config)
    if not _is_login_success(check_result):
        msg = check_result.get("msg") or check_result.get("message") or "account is not bound or login state is unavailable"
        raise RuntimeError(f"Laishixi checklogin failed: {msg}")

    session = requests.Session()
    login_url = f"{LAISHIXI_BASE_PATH}/login/loginByOpenid"
    response = session.get(login_url, params={"openid": openid}, headers=_headers(config), timeout=10)
    response.raise_for_status()
    cookies = requests.utils.dict_from_cookiejar(session.cookies)
    save_laishixi_session_cache(open_id=openid, cookies=cookies)
    logging.info("Laishixi H5 session cached; cookie_count=%s", len(cookies))
    return {"service": "laishixi", "openId": openid, "cookies": cookies}


def daily_attendance(args: Dict[str, Any], config: Dict[str, Any], opt: Dict[str, Any]) -> Dict[str, Any]:
    openid = str(args.get("openId") or "").strip()
    if not openid:
        raise RuntimeError("Laishixi openid is empty; refresh code first")

    cookies = args.get("cookies") if isinstance(args.get("cookies"), dict) else {}
    session = requests.Session()
    for key, value in cookies.items():
        session.cookies.set(str(key), str(value), domain="shx.lwvc.edu.cn")

    login_url = f"{LAISHIXI_BASE_PATH}/login/loginByOpenid"
    login_response = session.get(login_url, params={"openid": openid}, headers=_headers(config), timeout=10)
    login_response.raise_for_status()

    position = _build_position(config.get("location") or {})
    attendance_url = f"{LAISHIXI_BASE_PATH}/fqkq/qdztcx"
    params = {
        "position": json.dumps(position, ensure_ascii=False, separators=(",", ":")),
        "minitype": "mini",
    }
    logging.info("Laishixi daily attendance entry: %s?position=%s&minitype=mini", attendance_url, quote(params["position"]))
    response = session.get(attendance_url, params=params, headers=_headers(config), timeout=10)
    response.raise_for_status()
    html = response.text or ""
    summary = _summarize_html(html)
    logging.info("Laishixi daily attendance response: HTTP %s, summary: %s", response.status_code, summary)

    save_laishixi_session_cache(open_id=openid, cookies=requests.utils.dict_from_cookiejar(session.cookies))
    return {
        "success": response.status_code == 200,
        "status_code": response.status_code,
        "url": response.url,
        "summary": summary,
        "action": opt.get("action"),
    }
