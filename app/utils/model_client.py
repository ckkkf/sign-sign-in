import json

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

def call_chat_model(
    model_cfg: dict,
    prompt: str,
    system_prompt: str = "你是一个实习助手",
    on_delta=None,
) -> str:
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
        "stream": True,
        "temperature": 0.3,
        "max_tokens": 800
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    chunks = []

    with requests.post(
        endpoint,
        headers=headers,
        json=payload,
        timeout=(10, 120),
        stream=True,
    ) as response:
        response.raise_for_status()
        for raw_line in response.iter_lines(decode_unicode=True):
            if not raw_line:
                continue
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("data:"):
                line = line[5:].strip()
            if line == "[DONE]":
                break
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                # 非流式或一次性返回
                try:
                    data = json.loads(response.text)
                except Exception as exc:
                    raise RuntimeError(f"无法解析模型响应：{exc}") from exc
                line = None

            if not isinstance(data, dict):
                continue

            choices = data.get("choices") or []
            if not choices:
                continue

            delta = choices[0].get("delta") or choices[0].get("message") or {}
            content = delta.get("content")
            if not content:
                continue

            chunks.append(content)
            if on_delta:
                on_delta(content)

    final_text = "".join(chunks).strip()
    if not final_text:
        raise RuntimeError("模型响应内容为空")
    return final_text


def test_model_connection(model_cfg: dict) -> str:
    return call_chat_model(
        model_cfg,
        "请用一句中文回复：模型连通性测试成功。",
        "你是一个测试助手，用一句中文复述用户信息。"
    )





