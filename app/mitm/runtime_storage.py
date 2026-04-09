import os
import shutil

from app.config.common import CERT_FILE, MITM_CERT_STATE_FILE, MITM_CONF_DIR, MITM_RESOURCE_DIR, RES_DIR

STATE_FILE = MITM_CERT_STATE_FILE
LEGACY_STATE_FILE = os.path.join(RES_DIR, "config", "mitm_cert_state.json")
LEGACY_MITM_CONF_DIR = os.path.join(MITM_RESOURCE_DIR, "conf")
LEGACY_CERT_FILE = os.path.join(RES_DIR, "cert", "mitmproxy-ca-cert.p12")


def _copy_tree_if_missing(source: str, destination: str):
    if not os.path.isdir(source) or os.path.exists(destination):
        return
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    shutil.copytree(source, destination)


def _copy_file_if_missing(source: str, destination: str):
    if not os.path.isfile(source) or os.path.exists(destination):
        return
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    shutil.copy2(source, destination)


def ensure_runtime_mitm_files():
    _copy_tree_if_missing(LEGACY_MITM_CONF_DIR, MITM_CONF_DIR)
    _copy_file_if_missing(LEGACY_STATE_FILE, STATE_FILE)
    _copy_file_if_missing(LEGACY_CERT_FILE, CERT_FILE)

    os.makedirs(MITM_CONF_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    os.makedirs(os.path.dirname(CERT_FILE), exist_ok=True)
