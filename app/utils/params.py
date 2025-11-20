from gmssl import sm2

def get_device_code(openId, device):
    sm2_crypt = sm2.CryptSM2(
        public_key='04a3c35de075a2e86f28d52a41989a08e740a82fb96d43d9af8a5509e0a4e837ecb384c44fe1ee95f601ef36f3c892214d45c9b3f75b57556466876ad6052f0f1f',
        private_key=None, mode=1)
    from utils.common import rand_str
    return sm2_crypt.encrypt(
        f'b|_{device["brand"]},{device["model"]},{device["system"]},{device["platform"]}aid|_wx9f1c2e0bbc10673ct|_{int(time.time() * 1000)}uid|_{rand_str()}oid|_{openId}'.encode()).hex().strip()


def get_header_token(e):
    # 映射列表
    n = ["5", "b", "f", "A", "J", "Q", "g", "a", "l", "p", "s", "q", "H", "4", "L", "Q", "g", "1", "6", "Q", "Z", "v",
         "w", "b", "c", "e", "2", "2", "m", "l", "E", "g", "G", "H", "I", "r", "o", "s", "d", "5", "7", "x", "t", "J",
         "S", "T", "F", "v", "w", "4", "8", "9", "0", "K", "E", "3", "4", "0", "m", "r", "i", "n"]

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

    # 排除的字段列表，根据r()返回的结果
    excluded_keys = [
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

    # 正则表达式：匹配特殊字符
    special_char_regex = re.compile(r"[`~!@#$%^&*()+=|{}':;',\[\].<>/?~！@#￥%……&*（）——+|{}【】‘；：”“’。，、？]")

    # 遍历u字典，构建d字符串
    for c in u:
        # 如果字段值不包含特殊字符且不在排除字段中
        if c not in excluded_keys and not special_char_regex.search(u[c]):
            d += u[c]

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
        "s": "_".join(p) if len(p) > 0 else ""
    }
