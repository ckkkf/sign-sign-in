import json
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import requests


class JournalServerError(RuntimeError):
    pass


def _build_url(base_url: str, path: str) -> str:
    if not base_url:
        raise JournalServerError("请先配置周记服务器地址")
    base = base_url if base_url.endswith("/") else base_url + "/"
    rel = path.lstrip("/")
    return urljoin(base, rel)


def _request_json(method: str, url: str, *, token: Optional[str] = None, data: Optional[dict] = None) -> Dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    kwargs = {"headers": headers, "timeout": 10}
    if data is not None:
        kwargs["json"] = data
    response = requests.request(method.upper(), url, **kwargs)
    try:
        payload = response.json()
    except json.JSONDecodeError:
        payload = {"message": response.text}
    if response.status_code >= 400:
        raise JournalServerError(payload.get("message") or payload.get("msg") or "服务器返回错误")
    # 常见风格：{code:200,data:{}} 或 {data:{}} 或 {token:xxx}
    if isinstance(payload, dict) and payload.get("code") not in (None, 200, "200"):
        raise JournalServerError(payload.get("message") or payload.get("msg") or "服务器处理失败")
    return payload


def register(base_url: str, username: str, password: str) -> Dict[str, Any]:
    if not username or not password:
        raise JournalServerError("请输入用户名和密码")
    url = _build_url(base_url, "/api/auth/register")
    return _request_json("post", url, data={"username": username, "password": password})


def login(base_url: str, username: str, password: str) -> Dict[str, Any]:
    if not username or not password:
        raise JournalServerError("请输入用户名和密码")
    url = _build_url(base_url, "/api/auth/login")
    payload = _request_json("post", url, data={"username": username, "password": password})
    token = payload.get("data")
    if not token:
        raise JournalServerError("登录失败：服务器未返回 token")
    return {"token": token, "user": username}


def fetch_journals(base_url: str, token: str) -> List[Dict[str, Any]]:
    if not token:
        raise JournalServerError("请先登录")
    url = _build_url(base_url, "/api/journals/latest")
    payload = _request_json("get", url, token=token)
    data = payload.get("data")
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return [data]
    if "entries" in payload and isinstance(payload["entries"], list):
        return payload["entries"]
    raise JournalServerError("服务器未返回周记内容")

