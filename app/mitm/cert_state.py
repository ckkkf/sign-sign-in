import hashlib
import json
import os

from app.config.common import MITM_DIR, RES_DIR
from app.utils.commands import check_cert

STATE_FILE = os.path.join(RES_DIR, "config", "mitm_cert_state.json")
CURRENT_CERT_FILE = os.path.join(MITM_DIR, "conf", "mitmproxy-ca-cert.cer")


def _read_state():
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}


def _write_state(payload: dict):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def current_cert_fingerprint():
    if not os.path.exists(CURRENT_CERT_FILE):
        return ""

    digest = hashlib.sha256()
    with open(CURRENT_CERT_FILE, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def remember_current_cert_installed():
    fingerprint = current_cert_fingerprint()
    if not fingerprint:
        return False

    _write_state({"sha256": fingerprint})
    return True


def current_cert_matches_installed_state():
    fingerprint = current_cert_fingerprint()
    if not fingerprint:
        return False
    return _read_state().get("sha256") == fingerprint


def summarize_cert_state():
    if current_cert_matches_installed_state():
        return True, "匹配当前 mitm 证书"

    if check_cert():
        return False, "已安装旧证书"

    if current_cert_fingerprint():
        return False, "未安装当前证书"

    return False, "未生成证书"
