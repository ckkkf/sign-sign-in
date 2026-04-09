import hashlib
import json
import os

from app.config.common import MITM_CERT_STATE_FILE, MITM_CONF_DIR
from app.mitm.runtime_storage import ensure_runtime_mitm_files
from app.utils.commands import check_cert

STATE_FILE = MITM_CERT_STATE_FILE
CURRENT_CERT_FILE = os.path.join(MITM_CONF_DIR, "mitmproxy-ca-cert.cer")


def _read_state():
    ensure_runtime_mitm_files()
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}


def _write_state(payload: dict):
    ensure_runtime_mitm_files()
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def current_cert_fingerprint():
    ensure_runtime_mitm_files()
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
    current_cert_matches = current_cert_matches_installed_state()
    cert_installed = check_cert()

    if current_cert_matches and cert_installed:
        return True, "新mitm证书"

    if cert_installed:
        return False, "旧mitm证书"

    if current_cert_matches or current_cert_fingerprint():
        return False, "未安装证书"

    return False, "未生成证书"
