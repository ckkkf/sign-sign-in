import json

import requests


def notify_pushplus(title: str, content: str, token: str) -> str:
    """PushPlus 推送到微信。"""
    token = (token or "").strip()
    if not token:
        raise ValueError("pushplus token 不能为空")

    url = "http://www.pushplus.plus/send"
    data = {
        "token": token,
        "title": title,
        "content": content,
    }
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    resp = requests.post(url, data=body, headers=headers, timeout=15)
    resp.raise_for_status()
    return (resp.text or "").strip()
