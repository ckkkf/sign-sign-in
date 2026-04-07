import json
import os
from datetime import datetime
from urllib.parse import urlsplit

from mitmproxy import http

CODE_FILE = os.path.normpath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "config",
        "mitm_code.json",
    )
)
PACKET_LOG_FILE = os.path.normpath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "logs",
        "mitm_packet.log",
    )
)


XYB_SOURCE = "xyb_code"
JIELONG_SOURCE = "jielong_token"


def append_packet_log(message: str):
    os.makedirs(os.path.dirname(PACKET_LOG_FILE), exist_ok=True)
    now = datetime.now().strftime("%H:%M:%S")
    with open(PACKET_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{now} | {message}\n")


def mask_value(value, keep: int = 6):
    value = str(value or "")
    if len(value) <= keep:
        return value
    return f"{value[:keep]}..."


def compact_text(value, max_len: int = 120):
    text = " ".join(str(value or "").split())
    if len(text) <= max_len:
        return text
    return f"{text[:max_len]}..."


def format_pairs(items):
    parts = []
    for key, value in items:
        key_text = str(key or "")
        if key_text.lower() in {"code", "openid", "unionid", "sessionid", "encryptvalue", "authorization"}:
            value_text = mask_value(value)
        else:
            value_text = compact_text(value, 40)
        parts.append(f"{key_text}={value_text}")
    return ", ".join(parts)


def flow_label(flow: http.HTTPFlow):
    url = urlsplit(flow.request.pretty_url)
    return f"{flow.request.method} {url.netloc}{url.path}"


def is_interesting_flow(flow: http.HTTPFlow):
    host = (flow.request.host or "").lower()
    url = (flow.request.pretty_url or "").lower()
    return (
        "getopenid.action" in url
        or "/api/user/token" in url
        or host.endswith("xybsyw.com")
        or host.endswith("servicewechat.com")
        or host.endswith("jielong.com")
    )


def log_request_details(flow: http.HTTPFlow):
    label = flow_label(flow)
    append_packet_log(f"[MITM][REQ] {label}")

    content_type = flow.request.headers.get("content-type", "")
    user_agent = compact_text(flow.request.headers.get("user-agent", ""), 60)
    append_packet_log(f"[MITM][REQ] content-type={content_type or '-'} | ua={user_agent or '-'}")

    query_items = list(flow.request.query.items(multi=True))
    if query_items:
        append_packet_log(f"[MITM][REQ][QUERY] {format_pairs(query_items[:8])}")

    form_items = list(flow.request.urlencoded_form.items(multi=True))
    if form_items:
        append_packet_log(f"[MITM][REQ][FORM] {format_pairs(form_items[:12])}")
    else:
        body_preview = compact_text(flow.request.get_text(strict=False), 160)
        if body_preview:
            append_packet_log(f"[MITM][REQ][BODY] {body_preview}")


def log_response_details(flow: http.HTTPFlow):
    if not flow.response:
        return

    label = flow_label(flow)
    content_type = flow.response.headers.get("content-type", "")
    body_text = flow.response.get_text(strict=False)
    append_packet_log(
        f"[MITM][RES] {label} | status={flow.response.status_code} | type={content_type or '-'} | bytes={len(flow.response.content or b'')}"
    )

    if "application/json" in content_type.lower():
        try:
            payload = json.loads(body_text or "{}")
        except json.JSONDecodeError:
            append_packet_log(f"[MITM][RES][BODY] {compact_text(body_text, 180)}")
            return

        if isinstance(payload, dict):
            code = payload.get("code")
            msg = compact_text(payload.get("msg", ""), 80)
            data = payload.get("data")
            summary = f"code={code}, msg={msg or '-'}"
            if isinstance(data, dict):
                summary += f", data_keys={','.join(list(data.keys())[:8])}"
            elif isinstance(data, list):
                summary += f", data_len={len(data)}"
            append_packet_log(f"[MITM][RES][JSON] {summary}")
        else:
            append_packet_log(f"[MITM][RES][JSON] {compact_text(payload, 180)}")
        return

    snippet = compact_text(body_text, 180)
    if snippet:
        append_packet_log(f"[MITM][RES][BODY] {snippet}")


def write_payload(payload: dict):
    os.makedirs(os.path.dirname(CODE_FILE), exist_ok=True)
    with open(CODE_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)


class GetCode:
    XYB_TARGET = "getOpenId.action"
    JIELONG_TARGET = "/api/User/Token"

    def _capture_xyb_code(self, flow: http.HTTPFlow):
        code = flow.request.urlencoded_form.get("code")
        if not code:
            append_packet_log(f"[MITM] ?? {flow.request.method} {flow.request.pretty_url}?????? code")
            return

        code_preview = mask_value(code)
        append_packet_log(f"[MITM] ?? {flow.request.method} {flow.request.pretty_url} | code={code_preview}")

        try:
            write_payload({"source": XYB_SOURCE, "code": code})
            append_packet_log(f"[MITM] code ?????: {CODE_FILE}")
            print(f"[addon] ??? ???? code ?????: {CODE_FILE}")
        except Exception as exc:
            append_packet_log(f"[MITM] code ??????: {exc}")
            print(f"[addon] ? code ??????: {exc}")

        flow.kill()

    def _capture_jielong_token_code(self, flow: http.HTTPFlow):
        try:
            body = json.loads(flow.request.get_text(strict=False) or "{}")
        except json.JSONDecodeError:
            append_packet_log(f"[MITM] ?? User/Token ??????? JSON: {compact_text(flow.request.get_text(strict=False), 120)}")
            return

        code = str(body.get("code") or "").strip()
        if not code:
            append_packet_log(f"[MITM] ???? User/Token?????? code")
            return

        payload = {
            "source": JIELONG_SOURCE,
            "code": code,
            "qCode": str(body.get("qCode") or ""),
            "authorization": str(flow.request.headers.get("authorization") or ""),
            "request_payload": str(flow.request.headers.get("x-api-request-payload") or ""),
            "request_referer": str(flow.request.headers.get("x-api-request-referer") or ""),
            "referer": str(flow.request.headers.get("referer") or ""),
            "user_agent": str(flow.request.headers.get("user-agent") or ""),
            "platform": str(flow.request.headers.get("platform") or ""),
        }
        append_packet_log(
            "[MITM] ???? User/Token | "
            f"code={mask_value(code)} | authorization={mask_value(payload['authorization'])}"
        )

        try:
            write_payload(payload)
            append_packet_log(f"[MITM] ???? payload ?????: {CODE_FILE}")
            print(f"[addon] ? ???????? code ?????: {CODE_FILE}")
        except Exception as exc:
            append_packet_log(f"[MITM] ???? payload ??????: {exc}")
            print(f"[addon] ? ???? payload ??????: {exc}")

        flow.kill()

    def request(self, flow: http.HTTPFlow):
        if not is_interesting_flow(flow):
            return

        log_request_details(flow)

        if self.XYB_TARGET in flow.request.pretty_url:
            self._capture_xyb_code(flow)
            return

        if flow.request.method.upper() == "POST" and self.JIELONG_TARGET in flow.request.pretty_url:
            self._capture_jielong_token_code(flow)
            return

    def response(self, flow: http.HTTPFlow):
        if not is_interesting_flow(flow):
            return
        log_response_details(flow)

    def error(self, flow: http.HTTPFlow):
        if not is_interesting_flow(flow):
            return
        append_packet_log(f"[MITM][ERR] {flow_label(flow)} | {flow.error}")


addons = [GetCode()]
