# -*- coding: utf-8 -*-
import builtins
import hashlib
import json
import os
import platform
import random
import re
import string
import subprocess
import sys
import threading
import time
import traceback
import urllib
import urllib.parse
from time import sleep

import qrcode
import requests
from colorama import Fore
from gmssl import sm2

# 保存原始的 print 函数
original_print = builtins.print


# 自定义 print 函数
def custom_print(*args, **kwargs):
    # 获取当前的调用栈
    stack = traceback.extract_stack()
    # 获取当前栈帧的函数名
    method_name = stack[-2].name if len(stack) >= 2 else 'unknown'
    # 打印方法名和内容
    original_print(f"[{method_name}] ", *args, **kwargs)


# 替换全局的 print 函数
builtins.print = custom_print


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
        print(f"成功读取参数: {params}")
        return params
    except Exception as e:
        print(f"读取失败: {e}")
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
        print(f"参数已成功保存到 {file_path}")
    except Exception as e:
        print(f"保存失败: {e}")


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


def get_plan_detail(userAgent, encryptValue, sessionId, traineeId):
    url = "https://xcx.xybsyw.com/student/clock/GetPlan!detail.action"

    data = {
        "traineeId": str(traineeId)
    }
    header_token = get_header_token(data)
    headers = {
        "v": "1.6.39",
        "wechat": "1",
        "xweb_xhr": "1",
        "authority": "xcx.xybsyw.com",
        "content-type": "application/x-www-form-urlencoded",
        "referer": "https://servicewechat.com/wx9f1c2e0bbc10673c/533/page-frame.html",
        "n": "content,deviceName,keyWord,blogBody,blogTitle,getType,responsibilities,street,text,reason,searchvalue,key,answers,leaveReason,personRemark,selfAppraisal,imgUrl,wxname,deviceId,avatarTempPath,file,file,model,brand,system,deviceId,platform,code,openId,unionid,clockDeviceToken,clockDevice,address,name,enterpriseEmail,responsibilities,practiceTarget,guardianName,guardianPhone,practiceDays,linkman,enterpriseName,companyIntroduction,accommodationStreet,accommodationLongitude,accommodationLatitude,internshipDestination,specialStatement,enterpriseStreet,insuranceName,insuranceFinancing,policyNumber,overtimeRemark,riskStatement,specialStatement",
        "m": header_token['m'],
        "s": header_token['s'],
        "t": header_token['t'],
        "user-agent": userAgent,
        "encryptvalue": encryptValue,
    }
    cookies = {"JSESSIONID": sessionId}
    response = requests.post(url, headers=headers, cookies=cookies, data=data)

    print(response, response.text)


def regeo(userAgent, location):
    url = "https://restapi.amap.com/v3/geocode/regeo"
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
    response = requests.get(url, headers=headers, params=params)
    json = response.json()
    print(f'{response}  |  {response.json()['regeocode']['formatted_address']}  |  {response.json()}')
    return json['regeocode']


def get_plan(userAgent, args):
    url = "https://xcx.xybsyw.com/student/clock/GetPlan.action"
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
    response = requests.post(url, headers=headers, cookies=cookies, data=data)

    print(response, response.text)
    return response.json()['data']


def generate_qrcode(data, label):
    """
    生成并打印二维码的函数

    :param data: 二维码需要编码的内容
    :param label: 显示在二维码前的标签
    """
    print(Fore.BLUE + label)
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
    generate_qrcode(url_wx, '微信')

    # 支付宝二维码
    url_zfb = 'https://qr.alipay.com/fkx10780lnnieguozv3vhaa'
    generate_qrcode(url_zfb, '支付宝')


def sign_in(config, args):
    ### 获取实习信息
    userAgent = config['userAgent']
    location = config['location']
    device = config['device']

    plan_data = get_plan(userAgent=userAgent, args=args)

    ### 调用接口获取当前位置。todo：仅支持第一段实习
    traineeId = str(plan_data[0]['dateList'][0]['traineeId'])
    get_plan_detail(userAgent=userAgent, encryptValue=args['encryptValue'], sessionId=args['sessionId'],
                    traineeId=traineeId)

    ### 调用高德地图逆解析
    geo = regeo(userAgent=userAgent, location=location)

    ### 调用签到接口
    url = "https://xcx.xybsyw.com/student/clock/Post.action"
    data = {
        'punchInStatus': "0",
        'clockStatus': "2",
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
    response = requests.post(url, data=data, headers=headers, cookies=cookies)

    print(response, response.text)
    json = response.json()
    msg = json['msg']
    data = json['data']
    signPersonNum = data['signPersonNum']

    print('\n\n---------------------------------------------------------\n')

    if msg == 'success' and signPersonNum is not None:
        print(Fore.GREEN + f'✅签到成功！！！签到成功！！！签到成功！！！')
    if msg == '已经签到' and signPersonNum is not None:
        print(Fore.GREEN + f'✅已经签到过了，明天再来吧！')
    else:
        raise ValueError('签到失败，请查看日志或联系开发者')


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
        f'b|_{device['brand']},{device['model']},{device['system']},{device['platform']}aid|_wx9f1c2e0bbc10673ct|_{int(time.time() * 1000)}uid|_{rand_str()}oid|_{openId}'.encode()).hex()
    print('device_code: ', device_code)
    return device_code


def get_base_path():
    # 获取当前程序目录
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后的路径
        return sys._MEIPASS
    else:
        # 正常开发时的路径
        return os.path.abspath(".")


def get_open_id(user_agent, device, code):
    headers = {
        "v": "1.6.39",
        "xweb_xhr": "1",
        "content-type": "application/x-www-form-urlencoded",
        "referer": "https://servicewechat.com/wx9f1c2e0bbc10673c/534/page-frame.html",
        'User-Agent': user_agent,
        "devicecode": get_device_code("", device),

    }

    url = "https://xcx.xybsyw.com/common/getOpenId.action"
    data = {
        "code": code
    }
    response = requests.post(url, headers=headers, data=data)
    json = response.json()

    print(response, response.text)

    if json['code'] == '202':
        raise ValueError('参数code已失效（有效次数为一次），请重新配置！')

    return json['data']


def wx_login(user_agent, device, openIdData):
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
    url = "https://xcx.xybsyw.com/login/login!wx.action"

    response = requests.post(url, headers=headers, cookies=cookies, data=data)

    print(response, response.text)
    return response.json()['data']


def loginByWechat(config, code):
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


def get_config():
    config_path = get_config_path()
    # 读取配置文件
    config = read_config(config_path)
    inputConfig = config['input']

    if inputConfig is None or inputConfig == {}:   raise ValueError(f'请创建配置文件，并重命名为{config_path}后再运行')

    for key in inputConfig.keys():
        # 兼容旧版本配置
        if inputConfig[key] == '' and key != 'code':
            raise ValueError(f"请对照教程填写配置\"{key}\"")

    return {**inputConfig}


def loginByUsername(config):
    data = {
        "picCode": "132",
        "username": "31312312",
        "password": "2467d3744600858cc9026d5ac6005305",
        "openId": "ooru94khFi-GQMq4EnD0SCrrU4HU",
        "unionId": "oHY-uwXrJTDlphny7GEDohWJG6wA",
        "model": "microsoft",
        "brand": "microsoft",
        "platform": "windows",
        "system": "Windows Unknown x64",
        "deviceId": ""
    }
    header_token = get_header_token(data)
    headers = {
        "v": "1.6.39",
        "wechat": "1",
        "xweb_xhr": "1",
        "content-type": "application/x-www-form-urlencoded",
        "referer": "https://servicewechat.com/wx9f1c2e0bbc10673c/534/page-frame.html",
        "n": "content,deviceName,keyWord,blogBody,blogTitle,getType,responsibilities,street,text,reason,searchvalue,key,answers,leaveReason,personRemark,selfAppraisal,imgUrl,wxname,deviceId,avatarTempPath,file,file,model,brand,system,deviceId,platform,code,openId,unionid,clockDeviceToken,clockDevice,address,name,enterpriseEmail,responsibilities,practiceTarget,guardianName,guardianPhone,practiceDays,linkman,enterpriseName,companyIntroduction,accommodationStreet,accommodationLongitude,accommodationLatitude,internshipDestination,specialStatement,enterpriseStreet,insuranceName,insuranceFinancing,policyNumber,overtimeRemark,riskStatement,specialStatement",
        # "devicecode": "70c44ba290d2d467e2a996c918a5ddf714d72da863919ac9b821cd4d87c19c19401bb9688de31e8dbbb9bc0a42749667b6be857a456e73a8ea7dd64c17149aab806ab3669aa48bada4468845257b08d7913cf64fa2d92b9647cd15fdef79d9efc89a2c5c63c49fd0ad5ffaed8f1fd062d41137fd67a792036ac6f5cf26a4689a94c72eac6ca8ffa5a1fb819692d2fc6ee3c05c7c7ccad4cfed478ae79c8face98f7d008ed9a17583539fbd5f47c5a0ee654dfff03aac5c1537b6fae2c2453b32a2d87115872857d1d7649e3530bc157bf7d7d47ce63a1f7dc67e738f966be89e4ad679772a53550418ae31ecdb8328",
        # "encryptvalue": "b20f0974689202bf2f1591dceb79a34953b0a979897f17acb4ac5a9975042da6066339a92b6e12fff6de3bb6801faae3ebdb6d449fc60f981e1b50dd706dcd9bc1d699a55558461d5ee744841f2e12aeca78a75d7a2bb6e958389ed870937c2afb299f894f5b9c27b676ae0dc1e1a93670c23f18eaefc6752314b487887cd7da60039d4fe99c4f8fbd2db5b3a3ef54460a098c904a1923a2f3812cc09b5dead9488d4f51ffdfde9702c299ac41d596a4f7903df1c7399107a438d42c4fba9fba1a820d26adbe7875e64c25264d1a4bece257da60a30ced377c5e1e5dfa6d368ca9bd85fbe5c3846cbd9546b21c4de5b35b02490c5459008b0560f77eba5e214697b81a48cf57fe7b5acf89d2e21d3440df720ecba21ca33301e2c3abd03db2e4fe26405c4b47624744d48faaaea37c9a45ba8deb4052ce647bc74144251f9b2bcce139cadc3358ed4a278b92184ac149a032194a9b0a17f0b3ce6fdf3aaa8120f35c443beb92589819dd91e1b44bda51e4f0fc23ed",
        "m": header_token['m'],
        "s": header_token['s'],
        "t": header_token['t'],
        "user-agent": config['userAgent'],
    }
    cookies = {
        # "JSESSIONID": "7E4D106786F898E028A0459482335C7F"
    }
    url = "https://xcx.xybsyw.com/login/login.action"

    response = requests.post(url, headers=headers, cookies=cookies, data=data)

    print(response.text)
    print(response)


def login(config):
    code = config['code']
    if code is None or code == '':
        raise ValueError('请下载软件Reqable，按照教程获取code参数并配置到配置文件中')

    # 微信登录
    return loginByWechat(config=config, code=code)


# 检查文件是否存在
def check_file_exists(file_path):
    return os.path.isfile(file_path)


# 获取配置文件的路径
def get_config_path():
    config_file_path = 'config.json'
    if not check_file_exists(config_file_path):
        raise ValueError(f'未找到{config_file_path}文件，请检查或重新下载！')
    return config_file_path


mitm_process = None


def start_mitmproxy():
    print('🔰🔰🔰开始运行mitmproxy🔰🔰🔰')
    # bash("mitmweb  --listen-port 13140 --web-port 52000 -s interceptor.py")
    global mitm_process
    # web_port = 52000
    # mitm_process = subprocess.Popen(f'mitmweb  --listen-port 13140 --web-port {web_port} -s getCode.py')
    # mitm_process = subprocess.Popen(f'mitmdump --p 13140 -s {__file__} --quiet')
    # mitm_process = subprocess.Popen(f'mitmdump --p 13140 -s {__file__}')
    # print(f"mitmweb 启动: http://127.0.0.1:{web_port}, listen-port: 13140")

    mitm_process = subprocess.Popen([
        'mitmdump',
        '-p', '13140',  # 代理端口
        '-s', get_base_path() + '\\get_code.py',  # 当前文件作为 addon
        '--quiet',  # 静默
        '--set', 'web_port=0'  # 关键：禁用 Web UI，避免 Python 3.13 模板错误
    ])


def stop_mitmproxy():
    global mitm_process
    if mitm_process:
        mitm_process.terminate()
        mitm_process.wait(timeout=3)
        print("mitmweb 已停止")
        mitm_process = None


def detect_os():
    os_name = platform.system()

    if os_name == "Windows":
        print("当前操作系统是 Windows")
    elif os_name == "Darwin":
        print("当前操作系统是 macOS")
    else:
        print(f"当前操作系统是 {os_name}")

    return os_name


def get_download_info(file_name):
    print('🔰🔰🔰开始下载SSL证书🔰🔰🔰')
    # 发送 GET 请求下载文件获取 .p12 格式的证书
    # response = requests.get('http://mitm.it/cert/p12')
    response = requests.get('http://mitm.it/cert/pem')

    if response.status_code == 200:
        # 保存文件到本地 .p12 格式
        with open(file_name, 'wb') as file:
            file.write(response.content)
        print(f'SSL证书下载成功，保存为 {file_name}')
        return file_name
    else:
        raise ValueError(f"下载失败，HTTP 状态码：{response.status_code}")


def check_cert_installed_windows():
    print('🔰🔰🔰开始检测ssl证书🔰🔰🔰')
    try:
        # 使用 certutil 检查证书是否存在
        stdout = bash('certutil -user -store root | findstr mitmproxy')

        if "mitmproxy" in stdout:
            print("证书已成功安装！")
            return True
        else:
            print("证书未安装或未正确安装。")
            return False

    except Exception as e:
        print(f"发生其他错误: {e}")
        return False


def install_cert(file_name):
    # 使用 certutil 安装证书到 Windows 系统中
    print('🔰🔰🔰正在安装证书🔰🔰🔰')
    try:
        # 安装证书
        print('❗正在安装抓取https包所需的ssl证书，若出现弹窗请点击确定。')

        while True:
            stdout = bash(f'certutil -user -addstore Root "{file_name}"')
            if not stdout:
                print("⚠️请点击确定以同意安装ssl证书，否则将无法使用本程序！")
                continue

            sleep(0.5)

            # 再次检测
            if not check_cert_installed_windows():
                continue

            break

        if "命令成功完成" not in stdout:
            raise ValueError(f"安装证书时发生错误: {stdout}")

    except subprocess.CalledProcessError as e:
        raise ValueError(f"安装证书时发生错误: {e}")


def do_cert():
    file_name = 'mitmproxy-ca-cert.p12'

    ### 检查是否安装证书
    if check_cert_installed_windows():
        return

    ### 下载证书
    get_download_info(file_name)

    ### 安装证书
    install_cert(file_name)


def bash(command, encoding='gbk'):
    """
    执行命令并打印输出，支持指定编码格式。

    :param command: 要执行的命令（字符串类型）
    :param encoding: 命令输出的编码格式，默认为 'gbk'（Windows 默认编码）
    """
    print(f"💻执行bash命令：{command}")
    try:
        # 使用 shell=True 让命令行中包含的引号能够正确处理
        result = subprocess.run(command, capture_output=True, text=True, check=True, encoding=encoding, shell=True)
        print(result)
        return result.stdout

    except subprocess.CalledProcessError as e:
        # 捕获并打印错误
        print(f"执行命令出错: {e}")
        print(f"错误输出: {e.stderr}")
    except Exception as e:
        print(f"发生其他错误: {e}")


def bash_new(command, encoding='gbk'):
    """
    在新的控制台窗口中执行命令。

    :param command: 要执行的命令（字符串类型）
    :param encoding: 命令输出的编码格式，默认为 'gbk'（Windows 默认编码）
    """
    print(f"💻 开启新控制台并执行命令：{command}")
    try:
        # 使用 start 命令打开新的命令行窗口并执行传入的命令
        subprocess.Popen(['start', 'cmd', '/K', command], shell=True, encoding=encoding, text=True)

    except subprocess.CalledProcessError as e:
        # 捕获并打印错误
        print(f"执行命令出错: {e}")
    except Exception as e:
        print(f"发生其他错误: {e}")


def reset_proxy():
    bash(
        r'reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyEnable /t REG_DWORD /d 0 /f >nul 2>nul')
    bash(
        r'reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyServer /d "" /f >nul 2>nul')


def get_code():
    print('🔰🔰🔰开始获取code，请打开或重新进入小程序。🔰🔰🔰')
    """
    循环等待并获取 code（每次收到一个就打印并继续等下一个）。
    按 Ctrl+C 或程序结束可退出循环。
    """
    # 全局队列：addon → 主线程

    while True:
        try:
            code = None
            with open("code.json") as f:
                code = json.load(f)["code"]

            if not code or code == '':
                time.sleep(1)
                continue

            print("😍主程序收到 code:", code)
            os.remove("code.json")
            return code
        except:
            time.sleep(1)


def set_proxy():
    print('🔰🔰🔰开始设置系统代理🔰🔰🔰')

    # 获取系统代理
    before_proxy = get_system_proxy()

    # 修改注册表
    host = "127.0.0.1"
    port = 13140
    if not before_proxy or before_proxy != f"{host}:{port}":
        bash(
            r'reg add "HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyEnable /t REG_DWORD /d 1 /f >nul 2>nul')
        bash(
            rf'reg add "HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyServer /d "{host}:{port}" /f >nul 2>nul')
        print('系统代理设置完成！')
    else:
        print('✔️系统代理无需设置，已跳过')


def get_system_proxy():
    stdout = bash(
        r'reg query "HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyServer')

    if not stdout or stdout == '':
        print(f"未配置系统代理：{stdout}")
        return None

    match = re.search(r'ProxyServer\s+REG_SZ\s+(.+)', stdout)
    if not match or match == '':
        print(f"未配置系统代理：{stdout}")
        return None

    # 提取代理地址
    proxy = match.group(1)
    print(f"代理服务器地址: {proxy}")
    return proxy


def main():
    try:
        ### 设置系统代理
        set_proxy()

        ### 开启 mitmproxy
        threading.Thread(target=start_mitmproxy).start()
        sleep(1)

        ### 操作ssl证书
        do_cert()

        ### 关闭 mitmproxy
        stop_mitmproxy()

        ### 开启 mitmproxy
        threading.Thread(target=start_mitmproxy).start()
        sleep(1)

        ### 开始抓包获取code
        code = get_code()

        ### 关闭 mitmproxy
        stop_mitmproxy()

        # 重置代理
        reset_proxy()

        ### 获取配置参数
        config = get_config()
        config['code'] = code

        ### 登录
        args = login(config=config)

        ### 调用签到接口
        sign_in(config=config, args=args)

        ### 显示付款码
        show_qrcode()

        input(Fore.YELLOW + "感谢您的支持，程序已结束，按回车键退出...")

    except ValueError as ve:
        print('\n\n---------------------------------------------------------')
        print(Fore.LIGHTRED_EX + str(ve))
    except Exception as e:
        print(f": {e}")
        print('\n\n---------------------------------------------------------')
        print(Fore.RED + f"系统异常: {str(e)}")
    # finally:
    # 重置代理
    # reset_proxy()


if __name__ == '__main__':
    main()
