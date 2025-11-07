# -*- coding: utf-8 -*-
import hashlib
import json
import logging
import os
import platform
import random
import re
import string
import subprocess
import sys
import time
import urllib
import urllib.parse

import psutil
import qrcode
import requests
from colorama import Fore
from colorlog import ColoredFormatter
from gmssl import sm2

# ================== 配置区 ==================
### 日志配置
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
logger.handlers.clear()  # 清空已存在的 handler（避免重复）
console_handler = logging.StreamHandler(stream=sys.stdout)  # 创建一个输出到控制台的 handler
console_handler.setFormatter(ColoredFormatter(  # 设置彩色格式
    "%(log_color)s%(asctime)s - %(levelname)s - %(message)s",
    datefmt=None,
    log_colors={
        'DEBUG': 'white',
        'INFO': 'light_green',
        'WARNING': 'light_yellow',
        'ERROR': 'light_red',
        'CRITICAL': 'bold_red',
    }
))
logger.addHandler(console_handler)


# ===========================================

def read_config(file_path: str) -> dict:
    """
    从指定的 JSON 文件读取参数并返回字典格式。

    :param file_path: 存储 JSON 文件的路径。
    :return: 读取的 JSON 数据，字典格式。
    """
    try:
        # 打开并读取 JSON 文件
        with open(file_path, 'r', encoding='utf-8') as file:
            params = json.load(file)
        logging.debug(f"成功读取参数: {params}")
        return params
    except Exception as e:
        logging.error(f"读取失败: {e}")
        return {}


def save_json_file(file_path: str, params: dict) -> None:
    """
    将请求参数保存为 JSON 格式到指定文件中。

    :param params: 要保存的参数，应该是字典格式。
    :param file_path: 存储 JSON 文件的路径。
    """
    try:
        # 将字典格式的参数写入 JSON 文件
        with open(file_path, 'w', encoding='utf-8') as file:
            json.dump(params, file, ensure_ascii=False, indent=4)
        logging.info(f"参数已成功保存到 {file_path}")
    except Exception as e:
        logging.info(f"保存失败: {e}")


# 修改 JSON 文件中的数据，传递一个字典来进行修改
def update_config(file_path: str, changes: dict) -> None:
    # 1. 读取当前的参数数据
    config = read_config(file_path)

    # 2. 修改某些数据
    if config:
        # 更新原数据
        config.update(changes)

        # 3. 保存修改后的数据回文件
        save_json_file(file_path, config)


def regeo(userAgent, location):
    logging.info('正在调用高德地图解析经纬度...')
    url = "https://restapi.amap.com/v3/geocode/regeo".strip()
    headers = {
        "xweb_xhr": "1",
        "Content-Type": "application/json",
        "Referer": "https://servicewechat.com/wx9f1c2e0bbc10673c/533/page-frame.html",
        "User-Agent": userAgent,
    }
    params = {
        "s": "rsx",
        "platform": "WXJS",
        "logversion": "2.0",
        "extensions": "all",
        "sdkversion": "1.2.0",
        "key": "c222383ff12d31b556c3ad6145bb95f4",
        "appname": "c222383ff12d31b556c3ad6145bb95f4",
        "location": f"{location['longitude']},{location['latitude']}",
    }
    logger.info(f"url:{url}, headers: {headers}, params: {params}")
    response = requests.get(url, headers=headers, params=params)
    json = response.json()
    logging.info(f'{response}  |  {response.json()['regeocode']['formatted_address']}')
    return json['regeocode']


def get_plan(userAgent, args):
    logging.info('正在获取实习计划...')
    url = "https://xcx.xybsyw.com/student/clock/GetPlan.action".strip()
    data = {}
    header_token = get_header_token(data)
    headers = {
        "v": "1.6.39",
        "wechat": "1",
        "xweb_xhr": "1",
        "content-type": "application/x-www-form-urlencoded",
        "encryptvalue": args['encryptValue'],
        "n": "content,deviceName,keyWord,blogBody,blogTitle,getType,responsibilities,street,text,reason,searchvalue,key,answers,leaveReason,personRemark,selfAppraisal,imgUrl,wxname,deviceId,avatarTempPath,file,file,model,brand,system,deviceId,platform,code,openId,unionid,clockDeviceToken,clockDevice,address,name,enterpriseEmail,responsibilities,practiceTarget,guardianName,guardianPhone,practiceDays,linkman,enterpriseName,companyIntroduction,accommodationStreet,accommodationLongitude,accommodationLatitude,internshipDestination,specialStatement,enterpriseStreet,insuranceName,insuranceFinancing,policyNumber,overtimeRemark,riskStatement,specialStatement",
        "referer": "https://servicewechat.com/wx9f1c2e0bbc10673c/534/page-frame.html",
        "m": header_token['m'],
        "s": header_token['s'],
        "t": header_token['t'],
        'user-agent': userAgent,
    }
    cookies = {
        "JSESSIONID": args['sessionId']
    }
    data = json.dumps(data, separators=(',', ':'))
    logger.info(f"url:{url}, headers: {headers}, cookies: {cookies}, data: {data}")
    response = requests.post(url, headers=headers, cookies=cookies, data=data)

    logging.info(f'{response} {response.text}')
    return response.json()['data']


def generate_qrcode(data, label):
    """
    生成并打印二维码的函数

    :param data: 二维码需要编码的内容
    :param label: 显示在二维码前的标签
    """
    logging.info(Fore.BLUE + label)
    qr = qrcode.QRCode(
        version=1,  # 控制二维码的大小，1表示最小
        error_correction=qrcode.constants.ERROR_CORRECT_L,  # 控制错误容忍度
        box_size=5,  # 每个点的像素大小
        border=2,  # 边框的宽度
    )
    qr.add_data(data)
    qr.make(fit=True)
    qr.print_ascii()


def show_qrcode():
    # 提示用户并等待输入
    input(
        Fore.BLUE + '开发不易，若能您对您有帮助，是我们的荣幸，若您手头有余，在自己有可乐喝的前提下，可以考虑请我喝瓶冰露，按回车显示二维码：\n')

    # 微信二维码
    url_wx = 'wxp://f2f01EiRAzk-cwnkJtbu5GMpj0Juf_dTWQr1DiUn5r25wlM'
    generate_qrcode(url_wx, '微信👇')

    # 支付宝二维码
    url_zfb = 'https://qr.alipay.com/fkx10780lnnieguozv3vhaa'
    generate_qrcode(url_zfb, '支付宝👇')


def get_sign_opt():
    sign_opt_map = {
        "0": {
            "action": "签到",
            "code": "2"
        },
        "1": {
            "action": "签退",
            "code": "1"
        }
    }

    while True:
        logger.info(f"请选择操作（0：签到，1：签退）：")
        input_str = input()
        if input_str in sign_opt_map:
            opt = sign_opt_map[input_str]
            logger.info(f"你选择了 {opt['code']}:{opt['action']}")
            return opt

        logger.warning("输入无效，请重新选择！")


def do_sign(config):
    ### 登录
    args = login(config=config)

    ### 获取实习信息
    userAgent = config['userAgent']
    location = config['location']
    device = config['device']

    plan_data = get_plan(userAgent=userAgent, args=args)

    ### 调用接口获取当前位置。todo：仅支持第一段实习
    traineeId = str(plan_data[0]['dateList'][0]['traineeId'])

    ### 调用高德地图逆解析
    geo = regeo(userAgent=userAgent, location=location)

    # 获取用户操作
    opt = get_sign_opt()

    ### 调用签到签退接口
    sign_in_or_out(args, device, geo, location, traineeId, userAgent, opt)


def sign_in_or_out(args, device, geo, location, traineeId, userAgent, opt):
    logging.info('正在调用签到接口进行签到...')
    url = "https://xcx.xybsyw.com/student/clock/Post.action".strip()
    data = {
        'punchInStatus': "0",
        # 2：签到，1：签退
        'clockStatus': str(opt['code']),
        'traineeId': traineeId,
        'adcode': geo['addressComponent']['adcode'],
        'model': device['model'],
        'brand': device['brand'],
        'platform': device['platform'],
        'system': device['system'],
        'openId': args['openId'],
        'unionId': args['unionId'],
        'lng': location['longitude'],
        'lat': location['latitude'],
        'address': geo['formatted_address'],
        'deviceName': device['model'],
    }
    header_token = get_header_token(data)
    headers = {
        'v': "1.6.39",
        'wechat': "1",
        'Referer': "https://servicewechat.com/wx9f1c2e0bbc10673c/534/page-frame.html",
        'User-Agent': userAgent,
        'n': "content,deviceName,keyWord,blogBody,blogTitle,getType,responsibilities,street,text,reason,searchvalue,key,answers,leaveReason,personRemark,selfAppraisal,imgUrl,wxname,deviceId,avatarTempPath,file,file,model,brand,system,deviceId,platform,code,openId,unionid,clockDeviceToken,clockDevice,address,name,enterpriseEmail,responsibilities,practiceTarget,guardianName,guardianPhone,practiceDays,linkman,enterpriseName,companyIntroduction,accommodationStreet,accommodationLongitude,accommodationLatitude,internshipDestination,specialStatement,enterpriseStreet,insuranceName,insuranceFinancing,policyNumber,overtimeRemark,riskStatement,specialStatement",
        'm': header_token['m'],
        's': header_token['s'],
        't': header_token['t'],
        'encryptvalue': args['encryptValue'],
        'devicecode': get_device_code(openId=args['openId'], device=device),
    }
    cookies = {
        "JSESSIONID": args['sessionId']
    }

    logger.info(f"url:{url}, headers: {headers}, cookies: {cookies}, data: {data}")

    response = requests.post(url, data=data, headers=headers, cookies=cookies)

    logging.info(f'{response} {response.text}')
    json = response.json()
    msg = json['msg']
    json_code = json['code']
    if json_code == "200":
        if msg == 'success':
            logging.info(f'✅ {opt['action']}成功！不要忘了为项目点上star，以便更新新内容哦！')
        elif msg == '已经签到':
            logging.info(f'✅ 已经{opt['action']}过了，明天再来吧！')
    elif json_code == "403":
        if msg == "当前实习任务无需下班打卡":
            logging.warning(f'{msg}')
    elif json_code == "202":
        raise RuntimeError("配置错误，请重新下载config.json模板文件，使用ai重新模拟您设备的device和userAgent参数，并重新填写。")
    else:
        raise RuntimeError('签到失败，请查看日志或联系开发者')


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


def rand_str(length=16, chars=string.ascii_letters + string.digits):
    return ''.join(random.choice(chars) for _ in range(length))


def get_device_code(openId, device):
    sm2_crypt = sm2.CryptSM2(
        public_key='04a3c35de075a2e86f28d52a41989a08e740a82fb96d43d9af8a5509e0a4e837ecb384c44fe1ee95f601ef36f3c892214d45c9b3f75b57556466876ad6052f0f1f',
        private_key=None,
        mode=1
    )

    device_code = sm2_crypt.encrypt(
        f'b|_{device['brand']},{device['model']},{device['system']},{device['platform']}aid|_wx9f1c2e0bbc10673ct|_{int(time.time() * 1000)}uid|_{rand_str()}oid|_{openId}'.encode()).hex().strip()
    logging.debug(f'device_code: {device_code}')
    return device_code


def get_resource_path(relative_path):
    """获取资源文件路径（支持打包和开发）"""
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(__file__)  # 脚本所在目录
    return os.path.join(base_path, relative_path)


def get_open_id(user_agent, device, code):
    logger.info("正在获取open_id...")
    headers = {
        "v": "1.6.39",
        "xweb_xhr": "1",
        "content-type": "application/x-www-form-urlencoded",
        "referer": "https://servicewechat.com/wx9f1c2e0bbc10673c/534/page-frame.html",
        'User-Agent': user_agent,
        "devicecode": get_device_code("", device),
    }

    # url = requote_uri("https://xcx.xybsyw.com/common/getOpenId.action".strip())
    url = "https://xcx.xybsyw.com/common/getOpenId.action".strip()
    data = {
        "code": code
    }
    logger.info(f"url:{url}, headers: {headers}, data: {data}")
    response = requests.post(url=url, headers=headers, data=data, allow_redirects=False)
    json = response.json()

    logging.info(f'{response} {response.text}')

    if json['code'] == '202':
        raise RuntimeError('参数code已失效（有效次数为一次），请重新配置！')

    return json['data']


def wx_login(user_agent, device, openIdData):
    logger.info("正在进行微信登录...")
    data = {
        "openId": openIdData['openId'],
        "unionId": openIdData['unionId']
    }
    header_token = get_header_token(data)
    headers = {
        "wechat": "1",
        "v": "1.6.39",
        "xweb_xhr": "1",
        "content-type": "application/x-www-form-urlencoded",
        "referer": "https://servicewechat.com/wx9f1c2e0bbc10673c/534/page-frame.html",
        "n": "content,deviceName,keyWord,blogBody,blogTitle,getType,responsibilities,street,text,reason,searchvalue,key,answers,leaveReason,personRemark,selfAppraisal,imgUrl,wxname,deviceId,avatarTempPath,file,file,model,brand,system,deviceId,platform,code,openId,unionid,clockDeviceToken,clockDevice,address,name,enterpriseEmail,responsibilities,practiceTarget,guardianName,guardianPhone,practiceDays,linkman,enterpriseName,companyIntroduction,accommodationStreet,accommodationLongitude,accommodationLatitude,internshipDestination,specialStatement,enterpriseStreet,insuranceName,insuranceFinancing,policyNumber,overtimeRemark,riskStatement,specialStatement",
        "devicecode": get_device_code(openId=openIdData['openId'], device=device),
        "encryptvalue": openIdData['encryptValue'],
        "m": header_token['m'],
        "s": header_token['s'],
        "t": header_token['t'],
        "user-agent": user_agent,

    }
    cookies = {
        "JSESSIONID": openIdData['sessionId'],
    }
    url = "https://xcx.xybsyw.com/login/login!wx.action".strip()

    logger.info(f"url:{url}, headers: {headers}, cookies: {cookies}, data: {data}")
    response = requests.post(url, headers=headers, cookies=cookies, data=data)

    logging.info(f'{response} {response.text}')
    return response.json()['data']


def validate_config(config, config_path, parent_key="", skip_keys=None):
    """
    递归校验配置是否完整
    :param config: 配置字典
    :param config_path: 配置文件路径（用于错误提示）
    :param parent_key: 父级路径（如 'user.account'）
    :param skip_keys: 需要跳过的字段（如 ['code']）
    """
    if skip_keys is None:
        skip_keys = ['code']

    if config is None or not isinstance(config, dict) or config == {}:
        raise RuntimeError(f"请创建配置文件，并重命名为 {config_path} 后再运行")

    for key, value in config.items():
        current_path = f"{parent_key}.{key}" if parent_key else key

        # 跳过指定字段
        if key in skip_keys:
            continue

        # 校验空字符串
        if value == '':
            raise RuntimeError(f"请对照教程填写配置 \"{current_path}\"")

        # 递归校验嵌套 dict
        if isinstance(value, dict):
            validate_config(value, config_path, current_path, skip_keys)


def get_config():
    config_path = get_config_path()
    # 读取配置文件
    config = read_config(config_path)
    inputConfig = config['input']

    validate_config(inputConfig, config_path)

    return inputConfig


def login(config):
    logging.info('正在执行登录流程')
    code = config['code']
    if code is None or code == '':
        raise RuntimeError('❌ 获取code失败！')

    userAgent = config['userAgent']
    device = config['device']

    ### 获取open_id、union_id等信息
    openIdData = get_open_id(user_agent=userAgent, device=device, code=code)
    openId = openIdData['openId']
    unionId = openIdData['unionId']

    ### 获取登录参数encryptValue、sessionId
    login_data = wx_login(user_agent=userAgent, device=device, openIdData=openIdData)
    encryptValue = login_data['encryptValue']
    sessionId = login_data['sessionId']

    return {
        'openId': openId,
        'unionId': unionId,
        'encryptValue': encryptValue,
        'sessionId': sessionId,
    }


# 检查文件是否存在
def check_file_exists(file_path):
    return os.path.isfile(file_path)


# 获取配置文件的路径
def get_config_path():
    config_file_path = 'config.json'
    if not check_file_exists(config_file_path):
        raise RuntimeError(f'未找到{config_file_path}文件，请检查或重新下载！')
    return config_file_path


def file_exists(file_path):
    return os.path.isfile(file_path)


def start_mitmdump(port):
    mitmdump_path = 'bin/mitmdump.exe'
    addons_path = 'bin/get_code.py'

    if is_port_in_use(port):
        logger.warning(f'端口{port}被占用，正在执行强制查杀')
        process = get_process_by_port(port)
        if not process:
            raise RuntimeError(f"未找到端口{port}的pid")
        kill_process_tree(process.pid)

    try:
        process = subprocess.Popen([
            mitmdump_path,
            "-p", str(port),
            "-s", addons_path,
            "--quiet"
        ])
        if not process:
            raise RuntimeError(f"❌ mitmdump 启动失败: {process}")

        logging.info(
            f"mitmdump 启动成功！mitmdump_path: {mitmdump_path}, addons_path: {addons_path}, pid: {process.pid}, port: {port}。")

        time.sleep(3)

        return process
    except Exception as e:
        raise RuntimeError(f"❌ mitmdump 启动失败: {e}")


def stop_mitmproxy(mitm_process, port):
    if not mitm_process:
        logging.warning('⚠️ mitmproxy未运行！')
        return  # 没启动就直接返回

    mitm_process.terminate()
    try:
        mitm_process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        mitm_process.kill()

    if not is_port_in_use(port):
        logging.info("停止mitmproxy成功")
        return

    process = get_process_by_port(port)

    if not process:
        raise RuntimeError(f"未找到端口{port}的pid")

    kill_process_tree(process.pid)


def detect_os():
    os_name = platform.system()

    if os_name == "Windows":
        logging.info("当前操作系统是 Windows")
    elif os_name == "Darwin":
        logging.info("当前操作系统是 macOS")
    else:
        logging.info(f"当前操作系统是 {os_name}")

    return os_name


def check_cert():
    try:
        # 使用 certutil 检查证书是否存在
        stdout = bash('certutil -user -store root | findstr mitmproxy')

        if not stdout or "mitmproxy" not in stdout:
            return False

        return True

    except Exception as e:
        logging.error(f"❌ 检测ssl证书时发生其他错误: {e}")
        return False


def download_cert(file_name, proxy):
    # 发送 GET 请求下载文件获取 .p12 格式的证书
    # response = requests.get('http://mitm.it/cert/p12')

    count = 3
    for i in range(count):
        try:
            response = requests.get('http://mitm.it/cert/pem', proxies={"http": proxy, "https": proxy})
            logger.info(f"正在下载证书... (第 {i + 1} 次尝试)")
            if response.status_code == 200:
                # 自动创建 cert/ 目录
                os.makedirs(os.path.dirname(file_name), exist_ok=True)
                # 保存文件到本地 .p12 格式
                with open(file_name, 'wb') as file:
                    file.write(response.content)
                logging.info(f'SSL证书下载成功，保存为 {file_name}')
                return file_name

            logging.error(f"❌ 下载失败，HTTP 状态码：{response.status_code}")
        except Exception as e:
            logging.error(f"❌ 下载失败，HTTP 状态码：{e}")

    raise RuntimeError(f"❌ 下载SSL证书失败！")


def install_cert(file_name):
    logging.info("正在安装证书，若出现弹窗请点击[确定]！")
    # 使用 certutil 安装证书到 Windows 系统中
    try:
        # 安装证书
        while True:
            stdout = bash(f'certutil -user -addstore Root "{file_name}"')
            # 再次检测
            if stdout and '命令成功完成' in stdout and check_cert():
                logger.info("安装成功")
                break

            logging.warning("⚠️请点击[确定]以同意安装ssl证书，否则将无法使用本程序！")

    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"❌ 安装证书时发生错误: {e}")


def do_cert(file_name, process, host, port):
    ### 检查是否安装证书

    if check_cert():
        logger.info("CA证书状态正常")
        return process

    logging.warning("证书未安装")

    ### 下载证书
    download_cert(file_name, f"{host}:{port}")

    ### 安装证书
    install_cert(file_name)

    # ### 关闭 mitmproxy
    # stop_mitmproxy(process)

    ### 重启 mitmproxy
    logging.info("🔰🔰🔰 正在重启 mitmdump 🔰🔰🔰")
    process = restart_mitmproxy(process, port)
    if not process:
        raise RuntimeError("mitmdump 重启失败")

    return process


def bash(command, encoding='gbk'):
    """
    执行命令并打印输出，支持指定编码格式。

    :param command: 要执行的命令（字符串类型）
    :param encoding: 命令输出的编码格式，默认为 'gbk'（Windows 默认编码）
    """
    logging.debug(f"💻 执行bash命令：{command}")
    try:
        # 使用 shell=True 让命令行中包含的引号能够正确处理
        result = subprocess.run(command, capture_output=True, text=True, encoding=encoding, shell=True)
        logging.debug(result)

        if not result:
            return result

        return result.stdout

    except subprocess.CalledProcessError as e:
        # 捕获并打印错误
        logging.error(f"执行命令出错: {e}")
        logging.error(f"错误输出: {e.stderr}")
    except Exception as e:
        logging.error(f"发生其他错误: {e}")


def reset_proxy(proxy, target_proxy):
    if proxy and proxy != '' and proxy != target_proxy:
        set_proxy(proxy)
    else:
        bash(
            r'reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyEnable /t REG_DWORD /d 0 /f >nul 2>nul')
        bash(
            r'reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyServer /d "" /f >nul 2>nul')
        logging.info('代理地址已重置')


def get_code(code_file):
    while True:
        try:
            code = None
            with open(code_file) as f:
                code = json.load(f)["code"].strip()

            if not code or code == '':
                time.sleep(1)
                continue

            logging.info(f"😍获取到 code:\"{code}\"")
            os.remove(code_file)
            return code
        except:
            time.sleep(1)


def get_system_proxy():
    stdout = bash(
        r'reg query "HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyServer')

    if not stdout or stdout.strip() == '':
        logging.info(f"未配置系统代理：{stdout}")
        return None

    match = re.search(r'ProxyServer\s+REG_SZ\s+(.+)', stdout)
    if not match or match == '':
        logging.info(f"未配置系统代理：{stdout}")
        return None

    # 提取代理地址
    proxy = match.group(1)
    if not proxy or proxy.strip() == '':
        logging.info(f"未配置系统代理：{stdout}")
        return None
    logging.info(f"检测到代理地址: {proxy}")
    return proxy


def set_proxy(proxy):
    # 获取系统代理
    origin_proxy = get_system_proxy()

    # 修改注册表
    if origin_proxy and origin_proxy == proxy:
        logging.info('系统代理无需设置，已跳过')
        return None

    bash(
        r'reg add "HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyEnable /t REG_DWORD /d 1 /f >nul 2>nul')
    bash(
        rf'reg add "HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyServer /d "{proxy}" /f >nul 2>nul')

    logging.info(f'代理地址设置为{proxy}')

    return origin_proxy


# ================== 工具函数 ==================

def get_process_by_port(port: int):
    """Windows 兼容 + 未来兼容：查找监听端口的进程"""
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            # 使用 net_connections()
            connections = proc.net_connections()
            for conn in connections:
                if getattr(conn.laddr, 'port', None) == port and conn.status == psutil.CONN_LISTEN:
                    return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, psutil.Error):
            continue
    return None


def is_port_in_use(port: int) -> bool:
    return get_process_by_port(port) is not None


def kill_process_tree(pid: int):
    """Windows 强制杀进程树"""
    try:
        os.system(f"taskkill /PID {pid} /F /T >nul 2>&1")
        logging.info(f"已强制终止进程树: {pid}")
    except:
        pass


def restart_mitmproxy(process, port):
    """热重启：stop + start"""
    stop_mitmproxy(process, port)
    time.sleep(1)  # 确保 TIME_WAIT 清理
    return start_mitmdump(port)


def main():
    target_host = "127.0.0.1"
    target_port = 13140
    target_proxy = f"{target_host}:{target_port}"
    origin_proxy = None

    try:
        ### 获取配置参数
        config = get_config()

        ### 设置系统代理
        logging.info('🔰🔰🔰 正在设置系统代理 🔰🔰🔰')
        origin_proxy = set_proxy(target_proxy)

        ### 启动 mitmproxy
        logging.info('🔰🔰🔰 正在启动 mitmdump 🔰🔰🔰')
        process = start_mitmdump(target_port)

        ### 操作ssl证书
        logging.info('🔰🔰🔰 正在检测CA证书 🔰🔰🔰')
        process = do_cert("cert/mitmproxy-ca-cert.p12", process, target_host, target_port)

        ### 正在获取code
        logging.info('🔰🔰🔰 正在获取code，请打开或重新进入小程序。 🔰🔰🔰')
        code = get_code("bin/code.json")

        ### 停止 mitmproxy
        logging.info('🔰🔰🔰 正在停止mitmproxy 🔰🔰🔰')
        stop_mitmproxy(process, target_port)

        # 重置代理
        logging.info('🔰🔰🔰 正在重置代理地址 🔰🔰🔰')
        reset_proxy(origin_proxy, target_proxy)

        config['code'] = code

        ### 开始执行签到签退流程
        logger.info("🔰🔰🔰 开始执行签到流程 🔰🔰🔰")
        do_sign(config=config)

        ### 显示付款码
        show_qrcode()

    except RuntimeError as ve:
        logging.error(Fore.LIGHTRED_EX + str(ve))
    except Exception as e:
        logging.error(f": {e}")
        logging.error(Fore.RED + f"系统异常: {str(e)}")
    finally:
        # 重置代理
        reset_proxy(origin_proxy, target_proxy)


if __name__ == '__main__':
    main()
    input(Fore.YELLOW + "程序已结束，按回车键退出...")
