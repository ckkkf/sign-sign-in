# -*- coding: utf-8 -*-
import builtins
import hashlib
import json
import random
import re
import subprocess
import time
import traceback
import urllib
import urllib.parse

import requests

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
        'charset': "utf-8",
        'Accept-Encoding': "gzip,compress,br,deflate",
        'Referer': "https://servicewechat.com/wx9f1c2e0bbc10673c/534/page-frame.html",
        'User-Agent': userAgent,
        'n': "content,deviceName,keyWord,blogBody,blogTitle,getType,responsibilities,street,text,reason,searchvalue,key,answers,leaveReason,personRemark,selfAppraisal,imgUrl,wxname,deviceId,avatarTempPath,file,file,model,brand,system,deviceId,platform,code,openId,unionid,clockDeviceToken,clockDevice,address,name,enterpriseEmail,responsibilities,practiceTarget,guardianName,guardianPhone,practiceDays,linkman,enterpriseName,companyIntroduction,accommodationStreet,accommodationLongitude,accommodationLatitude,internshipDestination,specialStatement,enterpriseStreet,insuranceName,insuranceFinancing,policyNumber,overtimeRemark,riskStatement,specialStatement",
        'm': header_token['m'],
        's': header_token['s'],
        't': header_token['t'],
        'encryptvalue': args['encryptValue'],
        'devicecode': get_device_code(device),
    }

    cookies = {
        "JSESSIONID": args['sessionId']
    }
    response = requests.post(url, data=data, headers=headers, cookies=cookies)

    print(response.text)


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


def get_device_code(device):
    result = subprocess.run(
        ["node", "device_code.js"],
        input=json.dumps(device),
        capture_output=True,
        text=True,
        encoding="utf-8"
    )

    print("JS 输出：", result.stdout.strip())
    return result.stdout.strip()


def get_open_id(user_agent, device, code):
    headers = {
        "v": "1.6.39",
        "xweb_xhr": "1",
        "content-type": "application/x-www-form-urlencoded",
        "referer": "https://servicewechat.com/wx9f1c2e0bbc10673c/534/page-frame.html",
        'User-Agent': user_agent,
        "devicecode": get_device_code(device),

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
        "devicecode": get_device_code(device),
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


def loginByWechat(config, fileName, code):
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

    update_config(fileName, {
        'system': {
            'openId': openId,
            'unionId': unionId,
            'sessionId': sessionId
        }
    })

    return {
        'openId': openId,
        'unionId': unionId,
        'encryptValue': encryptValue,
        'sessionId': sessionId,
    }


def get_config(fileName):
    config = read_config(fileName)
    inputConfig = config['input']
    systemConfig = config['system']

    if inputConfig is None or inputConfig == {}:   raise ValueError(f'请创建配置文件，并重命名为{fileName}后再运行')

    for key in inputConfig.keys():
        if inputConfig[key] == '':
            raise ValueError(f"请对照教程填写配置\"{key}\"")

    return {**inputConfig, **systemConfig}


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


def login(config, fileName):
    code = config['code']
    if code is None or code == '':
        raise ValueError('请下载软件Reqable，按照教程获取code参数并配置到配置文件中')

    # 微信登录
    return loginByWechat(config=config, fileName=fileName, code=code)


def main():
    fileName = 'config.json'

    ### 获取配置参数
    config = get_config(fileName)

    ### 登录
    args = login(config=config, fileName=fileName)

    ### 调用签到接口
    sign_in(config=config, args=args)


if __name__ == '__main__':
    main()
