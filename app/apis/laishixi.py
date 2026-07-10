import json
import logging
import re
from typing import Any, Dict
from urllib.parse import quote, urlparse

import requests

from app.config.common import LAISHIXI_APP_LOGIN_URL, LAISHIXI_BASE_PATH, LAISHIXI_REFERER
from app.utils.files import get_valid_laishixi_session_cache, save_laishixi_session_cache


REQUEST_TIMEOUT_SECONDS = 10


def _mask(value: str, keep: int = 6) -> str:
    text = str(value or "")
    if len(text) <= keep:
        return text
    return f"{text[:keep]}...{text[-4:]}"


def _headers(config: Dict[str, Any], form: bool = False) -> Dict[str, str]:
    """优先使用真实小程序请求中捕获的 Referer 和 User-Agent。"""
    referer = str(config.get("laishixiReferer") or LAISHIXI_REFERER).strip()
    user_agent = str(config.get("laishixiUserAgent") or config.get("userAgent") or "").strip()
    headers = {"referer": referer}
    if form:
        headers["content-type"] = "application/x-www-form-urlencoded;charset=utf-8"
    if user_agent:
        headers["user-agent"] = user_agent
    return headers


def _post_app_login(action: str, payload: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    """按照解包源码中的固定表单结构调用 appLogin 网关。"""
    data = {
        "action": action,
        "key": json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        "p": "5",
        "cypher": "false",
    }
    logging.debug("Laishixi appLogin request: action=%s", action)
    response = requests.post(
        LAISHIXI_APP_LOGIN_URL,
        headers=_headers(config, form=True),
        data=data,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    try:
        result = response.json()
    except ValueError as exc:
        raise RuntimeError("莱实习登录网关返回了非 JSON 响应") from exc
    if not isinstance(result, dict):
        raise RuntimeError("莱实习登录网关响应结构无效")
    logging.debug("Laishixi appLogin response: action=%s, keys=%s", action, list(result.keys()))
    return result


def _extract_openid(result: Dict[str, Any]) -> str:
    """兼容从响应根对象或 data 对象读取 openid。"""
    for container in (result, result.get("data")):
        if not isinstance(container, dict):
            continue
        for key in ("openid", "openId"):
            value = str(container.get(key) or "").strip()
            if value:
                return value
    raise RuntimeError("莱实习 autoWechat 响应中没有 openid")


def _is_login_success(result: Dict[str, Any]) -> bool:
    """读取解包源码用于分支判断的 checklogin success 字段。"""
    for container in (result, result.get("data")):
        if not isinstance(container, dict):
            continue
        value = container.get("success")
        if value is True or value == 1 or str(value).strip().lower() == "true":
            return True
    return False


def _build_position(location: Dict[str, Any]) -> Dict[str, Any]:
    """构造 qdztcx 接收的 wx.getLocation 成功回调对象。"""
    try:
        latitude = float(str(location.get("latitude")).strip())
        longitude = float(str(location.get("longitude")).strip())
    except (TypeError, ValueError) as exc:
        raise RuntimeError("莱实习经纬度无效，请先配置经度和纬度") from exc
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise RuntimeError("莱实习经纬度超出有效范围")
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
    return text[:180] if text else "页面无可读文本"


def _merge_captured_headers(config: Dict[str, Any], cached: Dict[str, Any] | None) -> Dict[str, Any]:
    effective = dict(config)
    if cached:
        effective.setdefault("laishixiReferer", cached.get("referer"))
        effective.setdefault("laishixiUserAgent", cached.get("userAgent"))
    return effective


def _open_h5_session(openid: str, config: Dict[str, Any]) -> requests.Session:
    """每次执行都通过 loginByOpenid 新建 H5 Session，不复用丢失属性的 Cookie 字典。"""
    session = requests.Session()
    login_url = f"{LAISHIXI_BASE_PATH}/login/loginByOpenid"
    response = session.get(
        login_url,
        params={"openid": openid},
        headers=_headers(config),
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    final_path = urlparse(response.url or login_url).path.lower().rstrip("/")
    if final_path.endswith("/login/gotowelcom"):
        raise RuntimeError("莱实习账号尚未绑定，无法建立日常考勤 H5 登录态")
    return session


def login(config: Dict[str, Any], use_cache: bool = True) -> Dict[str, Any]:
    """使用 checklogin 重新校验 openid，并创建全新的 H5 Session。"""
    cached = get_valid_laishixi_session_cache() if use_cache else None
    effective_config = _merge_captured_headers(config, cached)

    openid = str(config.get("openId") or config.get("openid") or "").strip()
    if not openid and cached:
        openid = str(cached.get("openId") or "").strip()
        if openid:
            logging.info("Using cached Laishixi openid; server validity will be checked again")

    if not openid:
        code = str(config.get("code") or "").strip()
        if not code:
            raise RuntimeError("缺少莱实习 openid，请先点击“获取登录态”")
        openid = _extract_openid(_post_app_login("autoWechat", {"code": code}, effective_config))
        logging.info("Laishixi openid acquired: %s", _mask(openid))

    check_result = _post_app_login("checklogin", {"openid": openid}, effective_config)
    if not _is_login_success(check_result):
        message = check_result.get("msg") or check_result.get("message") or "账号未绑定或登录态不可用"
        raise RuntimeError(f"莱实习 checklogin 失败：{message}")

    session = _open_h5_session(openid, effective_config)
    referer = str(effective_config.get("laishixiReferer") or LAISHIXI_REFERER).strip()
    user_agent = str(
        effective_config.get("laishixiUserAgent") or effective_config.get("userAgent") or ""
    ).strip()
    save_laishixi_session_cache(open_id=openid, referer=referer, user_agent=user_agent)
    logging.info("Laishixi H5 session established")
    return {
        "service": "laishixi",
        "openId": openid,
        "referer": referer,
        "userAgent": user_agent,
        "_session": session,
    }


def load_daily_attendance_entry(args: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    """仅加载 qdztcx 日常考勤入口，不把 HTTP 200 解释为签到成功。"""
    openid = str(args.get("openId") or "").strip()
    if not openid:
        raise RuntimeError("莱实习 openid 为空，请先获取登录态")

    effective_config = dict(config)
    effective_config.setdefault("laishixiReferer", args.get("referer"))
    effective_config.setdefault("laishixiUserAgent", args.get("userAgent"))
    session = args.get("_session")
    if not isinstance(session, requests.Session):
        session = _open_h5_session(openid, effective_config)

    position = _build_position(config.get("location") or {})
    attendance_url = f"{LAISHIXI_BASE_PATH}/fqkq/qdztcx"
    params = {
        "position": json.dumps(position, ensure_ascii=False, separators=(",", ":")),
        "minitype": "mini",
    }
    logging.info(
        "Laishixi daily attendance entry: %s?position=%s&minitype=mini",
        attendance_url,
        quote(params["position"]),
    )
    response = session.get(
        attendance_url,
        params=params,
        headers=_headers(effective_config),
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()

    final_path = urlparse(response.url or attendance_url).path.lower().rstrip("/")
    expected_path = urlparse(attendance_url).path.lower().rstrip("/")
    if final_path != expected_path:
        raise RuntimeError(f"莱实习日常考勤入口被重定向，最终地址：{response.url}")

    summary = _summarize_html(response.text or "")
    logging.info(
        "Laishixi daily attendance entry loaded: HTTP %s, summary: %s",
        response.status_code,
        summary,
    )
    return {
        "entry_loaded": True,
        "sign_confirmed": False,
        "result": "unknown",
        "status_code": response.status_code,
        "url": response.url,
        "summary": summary,
    }