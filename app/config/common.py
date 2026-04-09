import os

from core.paths import get_base_dir, get_user_data_dir

# 项目信息
PROJECT_VERSION = "v1.3.0"
PROJECT_NAME = "🔰 Sign sign in"
PROJECT_GITHUB = "https://github.com/ckkkf/sign-sign-in"
PROJECT_GITEE = "https://gitee.com/ckkk524334/sign-sign-in"

# QQ群信息
QQ_GROUP = "859098272"

# 校友邦版本
XYB_VERSION = "1.6.40"
# 校友邦key
XYB_KEY = "ZsE4rGnjI9PkHqAz2WseDc4RF8Uh7YgVMb5Ke48NemJ4saA6XcQ821fFT061pC"
# 校友邦appid
XYB_APP_ID = "wx9f1c2e0bbc10673c"
# 校友邦referer id
XYB_REFERER_ID = "560"
# 校友邦referer
XYB_REFERER = "https://servicewechat.com/" + XYB_APP_ID + "/" + XYB_REFERER_ID + "/page-frame.html"
# 校友邦签名排除字段（对应请求头 n）
XYB_EXCLUDED_KEYS = [
    "content", "deviceName", "keyWord", "blogBody", "blogTitle", "getType",
    "responsibilities", "street", "text", "reason", "searchvalue", "key",
    "answers", "leaveReason", "personRemark", "selfAppraisal", "imgUrl",
    "wxname", "deviceId", "avatarTempPath", "file", "model", "brand", "system",
    "platform", "code", "openId", "unionid", "clockDeviceToken", "clockDevice",
    "address", "name", "enterpriseEmail", "practiceTarget", "guardianName",
    "guardianPhone", "practiceDays", "linkman", "enterpriseName",
    "companyIntroduction", "accommodationStreet", "accommodationLongitude",
    "accommodationLatitude", "internshipDestination", "specialStatement",
    "enterpriseStreet", "insuranceName", "insuranceFinancing", "policyNumber",
    "overtimeRemark", "riskStatement", "specialStatement"
]
XYB_N_HEADER = ",".join(XYB_EXCLUDED_KEYS)

# 高德逆地理解析 key
AMAP_WEB_KEY = "c222383ff12d31b556c3ad6145bb95f4"

# SM2 设备指纹加密参数
XYB_SM2_PUBLIC_KEY = "04a3c35de075a2e86f28d52a41989a08e740a82fb96d43d9af8a5509e0a4e837ecb384c44fe1ee95f601ef36f3c892214d45c9b3f75b57556466876ad6052f0f1f"
XYB_SM2_MODE = 1

# 后端接口
API_URL = "https://langoo.cn"

# 代理地址
MITM_PROXY = "127.0.0.1:13140"

# code 本地接收服务（保留兼容）
CODE_RECEIVER_HOST = "127.0.0.1"
CODE_RECEIVER_PORT = 13141

# 项目根目录（openSource）
BASE_DIR = get_base_dir()

# app目录
APP_DIR = os.path.join(BASE_DIR, "app")

# 资源目录
RES_DIR = os.path.join(BASE_DIR, "resources")
USER_DATA_DIR = get_user_data_dir("SignSignIn")
REQUIRED_RESOURCE_DIRS = [
    os.path.join(RES_DIR, "cert"),
    os.path.join(RES_DIR, "config"),
    os.path.join(RES_DIR, "img"),
    os.path.join(RES_DIR, "journals"),
    os.path.join(RES_DIR, "logs"),
    os.path.join(RES_DIR, "mitm"),
    os.path.join(RES_DIR, "mitm", "addons"),
    os.path.join(RES_DIR, "mitm", "conf"),
    os.path.join(RES_DIR, "software"),
]

# mitm static resources / runtime dirs
MITM_RESOURCE_DIR = os.path.join(RES_DIR, "mitm")
MITM_DIR = os.path.join(USER_DATA_DIR, "mitm")
MITM_CONF_DIR = os.path.join(MITM_DIR, "conf")
MITM_CERT_STATE_FILE = os.path.join(USER_DATA_DIR, "config", "mitm_cert_state.json")

# 配置文件目录（你如果想放 resources/config/ 也可以）
CONFIG_FILE = os.path.join(RES_DIR, "config", "config.json")

# code文件目录
CERT_FILE = os.path.join(USER_DATA_DIR, "cert", "mitmproxy-ca-cert.p12")

# 图片目录
IMAGE_DIR = os.path.join(RES_DIR, "img")

# 周记目录
JOURNAL_DIR = os.path.join(RES_DIR, "journals")
JOURNAL_HISTORY_FILE = os.path.join(JOURNAL_DIR, "history.json")

# 日志目录
LOG_DIR = os.path.join(RES_DIR, "logs")
PACKET_LOG_FILE = os.path.join(LOG_DIR, "mitm_packet.log")

# 会话缓存文件
SESSION_CACHE_FILE = os.path.join(RES_DIR, "config", "session_cache.json")

# mitm addons
ADDONS_DIR = os.path.join(MITM_RESOURCE_DIR, "addons")

# code 文件传递路径（mitm addon 写入，主程序轮询读取）
CODE_FILE = os.path.join(RES_DIR, "config", "mitm_code.json")


def ensure_resource_layout():
    for directory in REQUIRED_RESOURCE_DIRS:
        os.makedirs(directory, exist_ok=True)

# system prompt
SYSTEM_PROMPT = """
你是一名擅长撰写公司实习周记的写作助手。你的任务是根据用户提供的信息，生成一篇内容真实、结构清晰、符合企业实习场景的周记。你必须严格遵守以下要求：
每次生成要确保不一样，且不能出现这是第几周。
输出必须是纯文本，不能使用任何 Markdown、不能使用代码块、不能使用特殊符号格式。
周记内容必须贴合公司实习场景，语气自然专业，像真实实习生写的周记。
周记必须包含以下内容：本周完成的工作内容、本周学习到的技术或业务知识、遇到的困难及解决方式、与同事/导师的交流情况、本周的收获与下周计划。
字数保持在 300 至 600 字之间，内容必须连贯，不得敷衍堆砌。
如果用户提供了具体工作经历、技术内容或关键词，你必须将这些信息自然融入周记中，并在保持连贯性的前提下进行扩展。
如果用户未提供任何内容，你需要自动构建一个合理的企业实习生一周经历，包括工作内容、学习内容、困难与成长等元素。
生成的周记不得提及任何关于 AI、模型、提示词或生成方式的信息。
"""
