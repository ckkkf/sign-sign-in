import os
from core.paths import get_base_dir

# 项目信息
VERSION = "v1.1.2"

# QQ群信息
QQ_GROUP = "859098272"

# 后端接口
API_URL = "https://langoo.cn"

# 代理地址
MITM_PROXY = "127.0.0.1:13140"

# 项目根目录（openSource）
BASE_DIR = get_base_dir()

# app目录
APP_DIR = os.path.join(BASE_DIR, "app")

# 资源目录
RES_DIR = os.path.join(BASE_DIR, "resources")

# mitmdump
MITM_DIR = os.path.join(RES_DIR, "mitm")

# 配置文件目录（你如果想放 resources/config/ 也可以）
CONFIG_FILE = os.path.join(RES_DIR, "config", "config.json")

# code文件目录
CODE_FILE = os.path.join(RES_DIR, "config", "code.json")

# code文件目录
CERT_FILE = os.path.join(RES_DIR, "cert", "mitmproxy-ca-cert.p12")

# 图片目录
IMAGE_DIR = os.path.join(RES_DIR, "img")

# 周记目录
JOURNAL_DIR = os.path.join(RES_DIR, "journals")
JOURNAL_HISTORY_FILE = os.path.join(JOURNAL_DIR, "history.json")

# 会话缓存文件
SESSION_CACHE_FILE = os.path.join(RES_DIR, "config", "session_cache.json")

# mitm addons
ADDONS_DIR = os.path.join(MITM_DIR, "addons")

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
