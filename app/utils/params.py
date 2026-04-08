import hashlib
import json
import random
import re
import time
import urllib.parse

from gmssl import sm2

from app.config.common import (
    XYB_APP_ID,
    XYB_EXCLUDED_KEYS,
    XYB_KEY,
    XYB_N_HEADER,
    XYB_SM2_MODE,
    XYB_SM2_PUBLIC_KEY,
)
from app.utils.common import rand_str


def _normalize_header_token_value(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple, dict, set)):
        try:
            return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        except TypeError:
            return str(value)
    return str(value)


def get_device_code(openId, device):
    sm2_crypt = sm2.CryptSM2(
        public_key=XYB_SM2_PUBLIC_KEY,
        private_key=None,
        mode=XYB_SM2_MODE,
    )
    return sm2_crypt.encrypt(
            f'b|_{device["brand"]},{device["model"]},{device["system"]},{device["platform"]}aid|_{XYB_APP_ID}t|_{int(time.time() * 1000)}uid|_{rand_str()}oid|_{openId}'.encode()).hex().strip()


def get_header_token(e):
    # 映射列表
    n = list(XYB_KEY)

    # 初始化o列表
    o = [str(i) for i in range(62)]

    # 获取当前时间戳（秒）
    l = int(time.time())

    # 随机打乱o列表并选取前20个元素
    p = random.sample(o, 20)

    # 拼接字符串g
    g = "".join(n[int(e)] for e in p)

    # 排序传入字典e的键
    u = {k: e[k] for k in sorted(e)}

    # 初始化结果字符串d
    d = ""

    # 正则表达式：匹配特殊字符
    special_char_regex = re.compile(r"[`~!@#$%^&*()+=|{}':;',\[\].<>/?~！@#￥%……&*（）——+|{}【】‘；：”“’。，、？]")

    # 遍历u字典，构建d字符串
    for c in u:
        value_text = _normalize_header_token_value(u[c])
        # 如果字段值不包含特殊字符且不在排除字段中
        if c not in XYB_EXCLUDED_KEYS and not special_char_regex.search(value_text):
            d += value_text

    # 拼接最终的字符串
    d = f"{d}{l}{g}"

    # 清理掉不需要的字符
    d = (d.replace(" ", "")
         .replace("\n", "")
         .replace("\r", "")
         .replace("<", "")
         .replace(">", "")
         .replace("&", "")
         .replace("-", "")
         .replace(r"\uD83C[\uDF00-\uDFFF]", "")
         .replace(r"\uD83D[\uDC00-\uDE4F]", ""))

    # URL 编码
    d = urllib.parse.quote(d)

    # 计算MD5值
    md5_value = hashlib.md5(d.encode('utf-8')).hexdigest()

    return {
        "m": md5_value,
        "t": str(l),
        "s": "_".join(p) if len(p) > 0 else "",
        "n": XYB_N_HEADER
    }

