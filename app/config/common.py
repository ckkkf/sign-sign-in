import os

from core.paths import get_base_dir

# 项目信息
VERSION = "v1.1.0"

# QQ群信息
QQ_GROUP = "859098272"

# 后端接口
API_URL = "http://httpbin.org/post"

# 代理端口
MITM_PROXY = "127.0.0.1:13140"

# 项目根目录（openSource）
BASE_DIR = get_base_dir()

# app目录
APP_DIR = os.path.join(BASE_DIR, "app")

# 资源目录
RES_DIR = os.path.join(BASE_DIR, "resources")

# mitmdump
MITMDUMP_FILE = os.path.join(RES_DIR, "mitm", "mitmdump.exe")

# 配置文件目录（你如果想放 resources/config/ 也可以）
CONFIG_FILE = os.path.join(RES_DIR, "config", "config.json")

# code文件目录
CODE_FILE = os.path.join(RES_DIR, "config", "code.json")

# code文件目录
CERT_FILE = os.path.join(RES_DIR, "cert", "mitmproxy-ca-cert.p12")

# 图片目录
IMAGE_DIR = os.path.join(RES_DIR, "img")

# mitm addons
ADDONS_DIR = os.path.join(APP_DIR, "mitm", "addons")

