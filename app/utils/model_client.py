import requests


class ModelConfigurationError(RuntimeError):
    pass


def _normalize_endpoint(base_url: str) -> str:
    if not base_url:
        raise ModelConfigurationError("模型 Base URL 不能为空")
    base = base_url.rstrip('/')
    if base.endswith("chat/completions"):
        return base
    if base.endswith("v1"):
        return f"{base}/chat/completions"
    return f"{base}/v1/chat/completions"


def call_chat_model(model_cfg: dict, prompt: str, system_prompt: str = "你是一个实习助手") -> str:
    if not model_cfg:
        raise ModelConfigurationError("未配置模型参数")

    api_key = (model_cfg.get("apiKey") or "").strip()
    model_name = (model_cfg.get("model") or "").strip()
    endpoint = _normalize_endpoint(model_cfg.get("baseUrl", "").strip())

    if not api_key:
        raise ModelConfigurationError("请填写模型 API Key")
    if not model_name:
        raise ModelConfigurationError("请填写模型名称")

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 800
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    response = requests.post(endpoint, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    data = response.json()
    choices = data.get("choices")
    if not choices:
        raise RuntimeError("模型未返回内容")
    message = choices[0].get("message") or {}
    content = message.get("content")
    if not content:
        raise RuntimeError("模型响应内容为空")
    return content.strip()


def test_model_connection(model_cfg: dict) -> str:
    return call_chat_model(
        model_cfg,
        "请用一句中文回复：模型连通性测试成功。",
        "你是一个测试助手，用一句中文复述用户信息。"
    )

