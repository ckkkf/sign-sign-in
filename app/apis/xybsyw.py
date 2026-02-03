import logging

import requests

from app.config.common import XYB_VERSION
from app.utils.common import get_timestamp
from app.utils.files import get_img_file, clear_session_cache
from app.utils.params import get_header_token, get_device_code


def check_session_validity(response_json):
    """
    检查响应是否表示会话已失效
    当响应类似 {'code': '205', 'data': None, 'msg': '未登录', ...} 时返回True
    """
    if isinstance(response_json, dict):
        code = response_json.get('code')
        msg = response_json.get('msg', '')
        if code == '205' or (code == 205) or '未登录' in str(msg):
            return False
    return True


def handle_invalid_session():
    """处理失效的会话：清除缓存并提示"""
    clear_session_cache()
    logging.warning('❌ JSESSIONID已失效，已清除缓存，请重新获取code')


def regeo(userAgent, location):
    logging.info('正在调用高德地图解析经纬度...')
    url = "https://restapi.amap.com/v3/geocode/regeo"
    headers = {
        "xweb_xhr": "1", "Content-Type": "application/json",
        "Referer": "https://servicewechat.com/wx9f1c2e0bbc10673c/533/page-frame.html",
        "User-Agent": userAgent,
    }
    params = {
        "s": "rsx", "platform": "WXJS", "logversion": "2.0", "extensions": "all",
        "sdkversion": "1.2.0", "key": "c222383ff12d31b556c3ad6145bb95f4",
        "appname": "c222383ff12d31b556c3ad6145bb95f4",
        "location": f"{location['longitude']},{location['latitude']}",
    }
    try:
        logging.debug(f"🛩️ 准备发起请求。url:{url}, headers:{headers}, params:{params}")
        response = requests.get(url, headers=headers, params=params, timeout=5)
        logging.debug(f"📡 收到响应:{response} {response.text}")
        res = response.json()
        if 'regeocode' in res:
            logging.info(f"📍 解析位置: {res['regeocode']['formatted_address']}")
            return res['regeocode']
        else:
            raise RuntimeError(f"位置解析失败: {res}")
    except Exception as e:
        logging.error(f"高德接口请求失败: {e}")
        raise e


def get_plan(userAgent, args):
    logging.info('正在获取实习计划...')
    url = "https://xcx.xybsyw.com/student/clock/GetPlan.action"
    data = {}
    header_token = get_header_token(data)
    headers = {
        "v": XYB_VERSION,
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

    try:
        logging.debug(f"🛩️ 准备发起请求。url:{url}, headers:{headers}, data:{data}, cookies:{cookies}")
        response = requests.post(url, headers=headers, cookies=cookies, data=data, timeout=5)
        logging.debug(f"📡 收到响应:{response} {response.text}")
        res = response.json()
        if not check_session_validity(res):
            handle_invalid_session()
            raise RuntimeError('❌ JSESSIONID已失效，请重新获取code')
        if 'data' in res and res['data']:
            return res['data']
        else:
            raise RuntimeError(f"获取计划失败: {res.get('msg', 'Unknown error')}")
    except Exception as e:
        raise RuntimeError(f"计划接口请求异常: {e}")


def get_open_id(config, code):
    logging.info("正在获取open_id...")
    headers = {
        "v": XYB_VERSION,
        "xweb_xhr": "1",
        "content-type": "application/x-www-form-urlencoded",
        "referer": "https://servicewechat.com/wx9f1c2e0bbc10673c/534/page-frame.html",
        'User-Agent': config['userAgent'],
        "devicecode": get_device_code("", config['device']),
    }
    url = "https://xcx.xybsyw.com/common/getOpenId.action"
    data = {"code": code}

    try:
        logging.debug(f"🛩️ 准备发起请求。url:{url}, headers:{headers}, data:{data}")
        response = requests.post(url=url, headers=headers, data=data, allow_redirects=False, timeout=5)
        logging.debug(f"📡 收到响应:{response} {response.text}")
        res = response.json()
        if res.get('code') == '202':
            raise RuntimeError(f'code已失效，请重启小程序。接口响应：{res}')
        return res['data']
    except Exception as e:
        raise RuntimeError(f"获取OpenID失败: {e}")


def wx_login(config, openIdData):
    logging.info("正在进行微信登录...")
    data = {
        "openId": openIdData['openId'],
        "unionId": openIdData['unionId']
    }
    header_token = get_header_token(data)
    headers = {
        "wechat": "1",
        "v": XYB_VERSION,
        "xweb_xhr": "1",
        "content-type": "application/x-www-form-urlencoded",
        "referer": "https://servicewechat.com/wx9f1c2e0bbc10673c/534/page-frame.html",
        "n": "content,deviceName,keyWord,blogBody,blogTitle,getType,responsibilities,street,text,reason,searchvalue,key,answers,leaveReason,personRemark,selfAppraisal,imgUrl,wxname,deviceId,avatarTempPath,file,file,model,brand,system,deviceId,platform,code,openId,unionid,clockDeviceToken,clockDevice,address,name,enterpriseEmail,responsibilities,practiceTarget,guardianName,guardianPhone,practiceDays,linkman,enterpriseName,companyIntroduction,accommodationStreet,accommodationLongitude,accommodationLatitude,internshipDestination,specialStatement,enterpriseStreet,insuranceName,insuranceFinancing,policyNumber,overtimeRemark,riskStatement,specialStatement",
        "devicecode": get_device_code(openId=openIdData['openId'], device=config['device']),
        "encryptvalue": openIdData['encryptValue'],
        "m": header_token['m'],
        "s": header_token['s'],
        "t": header_token['t'],
        "user-agent": config['userAgent'],
    }
    cookies = {"JSESSIONID": openIdData['sessionId']}
    url = "https://xcx.xybsyw.com/login/login!wx.action"
    try:
        logging.debug(f"🛩️ 准备发起请求。url:{url}, headers:{headers}, data:{data}, cookies:{cookies}")
        response = requests.post(url, headers=headers, cookies=cookies, data=data, timeout=5)
        logging.debug(f"📡 收到响应:{response} {response.text}")
        res = response.json()
        return res['data']
    except Exception as e:
        raise RuntimeError(f"登录失败: {e}")


def login(config, use_cache=True):
    """
    登录函数，支持JSESSIONID缓存
    :param config: 配置信息
    :param use_cache: 是否使用缓存，如果为True且缓存有效则直接返回缓存
    :return: 登录结果字典
    """
    from app.utils.files import get_valid_session_cache, save_session_cache

    # 尝试使用缓存
    if use_cache:
        cached = get_valid_session_cache()
        if cached:
            logging.info('✅ 使用缓存的JSESSIONID')
            return {
                'openId': cached['openId'],
                'unionId': cached['unionId'],
                'encryptValue': cached['encryptValue'],
                'sessionId': cached['sessionId'],
                'traineeId': cached.get('traineeId')
            }

    logging.info('正在执行登录流程...')
    code = config.get('code')
    if not code or code == '':
        raise RuntimeError('❌ Code为空，请重新获取！')

    ### 获取open_id、union_id等信息
    openIdData = get_open_id(config=config, code=code)

    ### 获取登录参数encryptValue、sessionId
    login_data = wx_login(config=config, openIdData=openIdData)

    result = {
        'openId': openIdData['openId'],
        'unionId': openIdData['unionId'],
        'encryptValue': login_data['encryptValue'],
        'sessionId': login_data['sessionId'],
    }

    # 保存到缓存
    save_session_cache(
        session_id=result['sessionId'],
        encrypt_value=result['encryptValue'],
        open_id=result['openId'],
        union_id=result['unionId'],
        trainee_id=result.get('traineeId')
    )
    logging.info('✅ 登录成功，已缓存JSESSIONID')

    return result


# ------------------------------拍照签到----------------------------------------


def photo_sign_in_or_out(args, config, geo, traineeId, opt):
    # watermark_info(args=args, config=config, traineeId=traineeId)
    logging.info('正在执行拍照签到流程...')

    policyData = commonPostPolicy(args=args, config=config)

    timestamp = get_timestamp()

    files = get_img_file(timestamp, opt.get('image_path'))
    try:
        ossData = aliyun_OSS(files=files, timestamp=timestamp, policyData=policyData)
        post_new(args=args, config=config, traineeId=traineeId, geo=geo, imgUrl=ossData['key'], opt=opt)
        # deliver_value(args=args, config=config, traineeId=traineeId)
    finally:
        file_obj = files.get("file", [None, None, None])[1]
        if file_obj:
            file_obj.close()


def watermark_info(args, config, traineeId):
    url = "https://xcx.xybsyw.com/student/clock/postNew!watermarkInfo.action"

    data = {
        "traineeId": str(traineeId)
    }

    header_token = get_header_token(data)

    headers = {
        "content-type": "application/x-www-form-urlencoded",
        "encryptvalue": args['encryptValue'],
        "m": header_token['m'],
        "n": "content,deviceName,keyWord,blogBody,blogTitle,getType,responsibilities,street,text,reason,searchvalue,key,answers,leaveReason,personRemark,selfAppraisal,imgUrl,wxname,deviceId,avatarTempPath,file,file,model,brand,system,deviceId,platform,code,openId,unionid,clockDeviceToken,clockDevice,address,name,enterpriseEmail,responsibilities,practiceTarget,guardianName,guardianPhone,practiceDays,linkman,enterpriseName,companyIntroduction,accommodationStreet,accommodationLongitude,accommodationLatitude,internshipDestination,specialStatement,enterpriseStreet,insuranceName,insuranceFinancing,policyNumber,overtimeRemark,riskStatement,specialStatement",
        "s": header_token['s'],
        "t": header_token['t'],
        "referer": "https://servicewechat.com/wx9f1c2e0bbc10673c/537/page-frame.html",
        "user-agent": config['userAgent'],
        "v": XYB_VERSION,
        "wechat": "1",
        "xweb_xhr": "1"
    }
    cookies = {"JSESSIONID": args['sessionId']}

    logging.debug(f"🛩️ 准备发起请求。url:{url}, headers:{headers}, data:{data}, cookies:{cookies}")
    response = requests.post(url, headers=headers, cookies=cookies, data=data)
    logging.debug(f"📡 收到响应:{response} {response.text}")

    logging.info(f"{response} {response.text}")


def commonPostPolicy(args, config):
    logging.info('正在获取上传凭证...')
    url = "https://xcx.xybsyw.com/uploadfile/commonPostPolicy.action"

    data = {
        "customerType": "STUDENT",
        "uploadType": "UPLOAD_STUDENT_CLOCK_IMGAGES",
        "publicRead": "true"
    }

    header_token = get_header_token(data)
    headers = {
        "content-type": "application/x-www-form-urlencoded",
        "devicecode": get_device_code(openId=args['openId'], device=config['device']),
        "encryptvalue": args['encryptValue'],
        "m": header_token['m'],
        "n": "content,deviceName,keyWord,blogBody,blogTitle,getType,responsibilities,street,text,reason,searchvalue,key,answers,leaveReason,personRemark,selfAppraisal,imgUrl,wxname,deviceId,avatarTempPath,file,file,model,brand,system,deviceId,platform,code,openId,unionid,clockDeviceToken,clockDevice,address,name,enterpriseEmail,responsibilities,practiceTarget,guardianName,guardianPhone,practiceDays,linkman,enterpriseName,companyIntroduction,accommodationStreet,accommodationLongitude,accommodationLatitude,internshipDestination,specialStatement,enterpriseStreet,insuranceName,insuranceFinancing,policyNumber,overtimeRemark,riskStatement,specialStatement",
        "referer": "https://servicewechat.com/wx9f1c2e0bbc10673c/537/page-frame.html",
        "s": header_token['s'],
        "t": header_token['t'],
        "user-agent": config['userAgent'],
        "v": XYB_VERSION,
        "wechat": "1",
        "xweb_xhr": "1"
    }
    cookies = {
        "JSESSIONID": args['sessionId']
    }

    logging.debug(f"🛩️ 准备发起请求。url:{url}, headers:{headers}, data:{data}, cookies:{cookies}")
    response = requests.post(url, headers=headers, cookies=cookies, data=data)
    logging.debug(f"📡 收到响应:{response} {response.text}")

    logging.info(f"{response} {response.text}")

    res = response.json()
    if response.status_code != 200 or res['code'] != "200":
        raise RuntimeError(f"commonPostPolicy请求异常, {response} {response.text}")

    return res['data']


def aliyun_OSS(files, timestamp, policyData):
    logging.info('正在上传至阿里云OSS...')

    # headers = {
    #     "Content-Type": "multipart/form-data;",
    #     "Referer": "https://servicewechat.com/wx9f1c2e0bbc10673c/537/page-frame.html",
    #     "User-Agent": config['userAgent'],
    #     "devicecode": get_device_code(openId=args['openId'], device=config['device']),
    #     "encryptValue": args['encryptValue'],
    #     "m": header_token['m'],
    #     "n": "content,deviceName,keyWord,blogBody,blogTitle,getType,responsibilities,street,text,reason,searchvalue,key,answers,leaveReason,personRemark,selfAppraisal,imgUrl,wxname,deviceId,avatarTempPath,file,file,model,brand,system,deviceId,platform,code,openId,unionid,clockDeviceToken,clockDevice,address,name,enterpriseEmail,responsibilities,practiceTarget,guardianName,guardianPhone,practiceDays,linkman,enterpriseName,companyIntroduction,accommodationStreet,accommodationLongitude,accommodationLatitude,internshipDestination,specialStatement,enterpriseStreet,insuranceName,insuranceFinancing,policyNumber,overtimeRemark,riskStatement,specialStatement",
    #     "s": header_token['s'],
    #     "t": header_token['t'],
    #     "v": XYB_VERSION,
    #     "wechat": "1",
    #     "xweb_xhr": "1"
    # }
    # cookies = {
    #     "JSESSIONID": args['sessionId']
    # }
    # url = "https://xyb001-new.oss-cn-hangzhou.aliyuncs.com/"
    # response = requests.post(url, headers=headers, files=files, cookies=cookies, data=data)

    url = policyData['host']

    headers = {
        "Referer": "https://servicewechat.com/wx9f1c2e0bbc10673c/537/page-frame.html",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI MiniProgramEnv/Windows WindowsWechat/WMPF WindowsWechat(0x63090a13) UnifiedPCWindowsWechat(0xf2541211) XWEB/16815",
    }

    key = f"{policyData['dir']}/{timestamp}.jpg"
    logging.info(f"key: {key}")

    data = {
        "key": key,
        "policy": policyData['policy'],
        "OSSAccessKeyId": policyData['accessid'],
        "signature": policyData['signature'],
        "success_action_status": "200",
        "customerType": policyData['customParams']['x:customer_type_key'],
        "uploadType": policyData['customParams']['x:upload_type_key'],
        "callback": policyData['callback'],
    }

    logging.debug(f"🛩️ 准备发起请求。url:{url}, headers:{headers}, data:{data}, files:{files}")
    response = requests.post(url, data=data, files=files, headers=headers)
    logging.debug(f"📡 收到响应:{response} {response.text}")

    if response.status_code != 200:
        raise RuntimeError(f"aliyun_OSS请求异常, {response} {response.text}")

    res = response.json()
    return res['vo']


def post_new(args, config, traineeId, geo, imgUrl, opt):
    url = "https://xcx.xybsyw.com/student/clock/PostNew.action"

    data = {
        "traineeId": str(traineeId),
        "adcode": geo['addressComponent']['adcode'],
        "lat": config['location']['latitude'],
        "lng": config['location']['longitude'],
        "address": geo['formatted_address'],
        "deviceName": config['device']['model'],
        # "punchInStatus": "1",
        "punchInStatus": "0",
        # 2：普通签到，1：普通签退
        # "clockStatus": "2",
        "clockStatus": str(opt['code']),
        # "imgUrl": "temp/20251119/school/14422/xcx/student/clock/11621617/1763557557282.jpg",
        "imgUrl": imgUrl,
        "reason": "",
        "addressId": "null"
    }

    header_token = get_header_token(data)
    headers = {
        "content-type": "application/x-www-form-urlencoded",
        "devicecode": get_device_code(openId=args['openId'], device=config['device']),
        "encryptvalue": args['encryptValue'],
        "m": header_token['m'],
        "n": "content,deviceName,keyWord,blogBody,blogTitle,getType,responsibilities,street,text,reason,searchvalue,key,answers,leaveReason,personRemark,selfAppraisal,imgUrl,wxname,deviceId,avatarTempPath,file,file,model,brand,system,deviceId,platform,code,openId,unionid,clockDeviceToken,clockDevice,address,name,enterpriseEmail,responsibilities,practiceTarget,guardianName,guardianPhone,practiceDays,linkman,enterpriseName,companyIntroduction,accommodationStreet,accommodationLongitude,accommodationLatitude,internshipDestination,specialStatement,enterpriseStreet,insuranceName,insuranceFinancing,policyNumber,overtimeRemark,riskStatement,specialStatement",
        "referer": "https://servicewechat.com/wx9f1c2e0bbc10673c/537/page-frame.html",
        "s": header_token['s'],
        "t": header_token['t'],
        "user-agent": config['userAgent'],
        "v": XYB_VERSION,
        "wechat": "1",
        "xweb_xhr": "1"
    }
    cookies = {"JSESSIONID": args['sessionId']}

    logging.debug(f"🛩️ 准备发起请求。url:{url}, headers:{headers}, data:{data}, cookies:{cookies}")
    response = requests.post(url, headers=headers, cookies=cookies, data=data)
    logging.debug(f"📡 收到响应:{response} {response.text}")

    res = response.json()
    if response.status_code != 200 or res['code'] != "200":
        raise RuntimeError(f"post_new请求异常, {response} {response.text}")


def deliver_value(args, config, traineeId):
    url = "https://xcx.xybsyw.com/student/DeliverValue!post.action"

    data = {
        "traineeId": str(traineeId)
    }

    header_token = get_header_token(data)
    headers = {
        "content-type": "application/x-www-form-urlencoded",
        "encryptvalue": args['encryptValue'],
        "m": header_token['m'],
        "n": "content,deviceName,keyWord,blogBody,blogTitle,getType,responsibilities,street,text,reason,searchvalue,key,answers,leaveReason,personRemark,selfAppraisal,imgUrl,wxname,deviceId,avatarTempPath,file,file,model,brand,system,deviceId,platform,code,openId,unionid,clockDeviceToken,clockDevice,address,name,enterpriseEmail,responsibilities,practiceTarget,guardianName,guardianPhone,practiceDays,linkman,enterpriseName,companyIntroduction,accommodationStreet,accommodationLongitude,accommodationLatitude,internshipDestination,specialStatement,enterpriseStreet,insuranceName,insuranceFinancing,policyNumber,overtimeRemark,riskStatement,specialStatement",
        "referer": "https://servicewechat.com/wx9f1c2e0bbc10673c/537/page-frame.html",
        "s": header_token['s'],
        "t": header_token['t'],
        "user-agent": config['userAgent'],
        "v": XYB_VERSION,
        "wechat": "1",
        "xweb_xhr": "1"
    }
    cookies = {"JSESSIONID": args['sessionId']}

    logging.debug(f"🛩️ 准备发起请求。url:{url}, headers:{headers}, data:{data}, cookies:{cookies}")
    response = requests.post(url, headers=headers, cookies=cookies, data=data)
    logging.debug(f"📡 收到响应:{response} {response.text}")

    res = response.json()
    if response.status_code != 200 or res['code'] != "200":
        raise RuntimeError(f"deliver_value请求异常, {response} {response.text}")


def simple_sign_in_or_out(args, geo, traineeId, config, opt):
    logging.info(f'正在调用接口进行: {opt["action"]}...')
    url = "https://xcx.xybsyw.com/student/clock/Post.action"
    device = config['device']
    data = {'punchInStatus': "0",  # 2：普通签到，1：普通签退
            'clockStatus': str(opt['code']), 'traineeId': str(traineeId),
            'adcode': geo['addressComponent']['adcode'],
            'model': device['model'], 'brand': device['brand'], 'platform': device['platform'],
            'system': device['system'], 'openId': args['openId'], 'unionId': args['unionId'],
            'lng': config['location']['longitude'], 'lat': config['location']['latitude'],
            'address': geo['formatted_address'], 'deviceName': device['model'], }
    header_token = get_header_token(data)
    headers = {'v': XYB_VERSION, 'wechat': "1",
               'Referer': "https://servicewechat.com/wx9f1c2e0bbc10673c/534/page-frame.html",
               'User-Agent': config['userAgent'],
               'n': "content,deviceName,keyWord,blogBody,blogTitle,getType,responsibilities,street,text,reason,searchvalue,key,answers,leaveReason,personRemark,selfAppraisal,imgUrl,wxname,deviceId,avatarTempPath,file,file,model,brand,system,deviceId,platform,code,openId,unionid,clockDeviceToken,clockDevice,address,name,enterpriseEmail,responsibilities,practiceTarget,guardianName,guardianPhone,practiceDays,linkman,enterpriseName,companyIntroduction,accommodationStreet,accommodationLongitude,accommodationLatitude,internshipDestination,specialStatement,enterpriseStreet,insuranceName,insuranceFinancing,policyNumber,overtimeRemark,riskStatement,specialStatement",
               'm': header_token['m'], 's': header_token['s'], 't': header_token['t'],
               'encryptvalue': args['encryptValue'],
               'devicecode': get_device_code(openId=args['openId'], device=config['device']), }
    cookies = {"JSESSIONID": args['sessionId']}

    try:
        logging.debug(f"🛩️ 准备发起请求。url:{url}, headers:{headers}, data:{data}, cookies:{cookies}")
        response = requests.post(url, data=data, headers=headers, cookies=cookies, timeout=5)
        logging.debug(f"📡 收到响应:{response} {response.text}")
        res = response.json()

        if not check_session_validity(res):
            handle_invalid_session()
            raise RuntimeError('❌ JSESSIONID已失效，请重新获取code')

        msg = res['msg']
        code = res['code']

        info = ''

        if code == "200":
            if msg == 'success':
                info = f'✅ {opt["action"]}成功！'
                logging.info(info)
            elif msg == '已经签到':
                info = f'✅ 已经{opt["action"]}过了。'
                logging.info(info)
        elif code == "403":
            logging.warning(f'⚠️ {msg}')
        elif code == "202":
            raise RuntimeError(f"配置错误，请检查device和userAgent参数 (Code 202): {msg}")
        else:
            raise RuntimeError(f'操作失败: {msg}')

        return info
    except Exception as e:
        raise RuntimeError(f"签到请求异常: {e}")


# ------------------------------周记相关接口----------------------------------------


def load_blog_year(args, config):
    """加载周记年份和月份"""
    logging.info('正在加载周记年份和月份...')
    url = "https://xcx.xybsyw.com/student/blog/LoadBlogDate!weekYear.action"

    data = {
        "traineeId": str(args.get('traineeId', ''))
    }

    header_token = get_header_token(data)
    headers = {
        "content-type": "application/x-www-form-urlencoded",
        "encryptvalue": args['encryptValue'],
        "m": header_token['m'],
        "n": "content,deviceName,keyWord,blogBody,blogTitle,getType,responsibilities,street,text,reason,searchvalue,key,answers,leaveReason,personRemark,selfAppraisal,imgUrl,wxname,deviceId,avatarTempPath,file,file,model,brand,system,deviceId,platform,code,openId,unionid,clockDeviceToken,clockDevice,address,name,enterpriseEmail,responsibilities,practiceTarget,guardianName,guardianPhone,practiceDays,linkman,enterpriseName,companyIntroduction,accommodationStreet,accommodationLongitude,accommodationLatitude,internshipDestination,specialStatement,enterpriseStreet,insuranceName,insuranceFinancing,policyNumber,overtimeRemark,riskStatement,specialStatement",
        "referer": "https://servicewechat.com/wx9f1c2e0bbc10673c/539/page-frame.html",
        "s": header_token['s'],
        "t": header_token['t'],
        "user-agent": config['userAgent'],
        "v": XYB_VERSION,
        "wechat": "1",
        "xweb_xhr": "1"
    }
    cookies = {
        "JSESSIONID": args['sessionId']
    }

    try:
        logging.debug(f"🛩️ 准备发起请求。url:{url}, headers:{headers}, data:{data}, cookies:{cookies}")
        response = requests.post(url, headers=headers, cookies=cookies, data=data, timeout=10)
        logging.debug(f"📡 收到响应:{response} {response.text}")
        res = response.json()

        if not check_session_validity(res):
            handle_invalid_session()
            raise RuntimeError('❌ JSESSIONID已失效，请重新获取code')

        logging.info(f'加载周记年份和月份：{res.get('data', 'Unknown error')}')
        if res.get('code') == '200' and 'data' in res:
            return res['data']
        else:
            raise RuntimeError(f"加载年份月份失败: {res.get('msg', 'Unknown error')}")
    except Exception as e:
        raise RuntimeError(f"加载年份月份请求异常: {e}")


def load_blog_date(args, config, year, month):
    """加载指定年月下的周信息"""
    logging.info(f'正在加载{year}年{month}月的周信息...')
    url = "https://xcx.xybsyw.com/student/blog/LoadBlogDate!week.action"

    data = {
        "year": str(year),
        "month": str(month),
        "traineeId": str(args.get('traineeId', '')),
        "id": ""
    }

    header_token = get_header_token(data)
    headers = {
        "content-type": "application/x-www-form-urlencoded",
        "encryptvalue": args['encryptValue'],
        "m": header_token['m'],
        "n": "content,deviceName,keyWord,blogBody,blogTitle,getType,responsibilities,street,text,reason,searchvalue,key,answers,leaveReason,personRemark,selfAppraisal,imgUrl,wxname,deviceId,avatarTempPath,file,file,model,brand,system,deviceId,platform,code,openId,unionid,clockDeviceToken,clockDevice,address,name,enterpriseEmail,responsibilities,practiceTarget,guardianName,guardianPhone,practiceDays,linkman,enterpriseName,companyIntroduction,accommodationStreet,accommodationLongitude,accommodationLatitude,internshipDestination,specialStatement,enterpriseStreet,insuranceName,insuranceFinancing,policyNumber,overtimeRemark,riskStatement,specialStatement",
        "referer": "https://servicewechat.com/wx9f1c2e0bbc10673c/539/page-frame.html",
        "s": header_token['s'],
        "t": header_token['t'],
        "user-agent": config['userAgent'],
        "v": XYB_VERSION,
        "wechat": "1",
        "xweb_xhr": "1"
    }
    cookies = {
        "JSESSIONID": args['sessionId']
    }

    try:
        logging.debug(f"🛩️ 准备发起请求。url:{url}, headers:{headers}, data:{data}, cookies:{cookies}")
        response = requests.post(url, headers=headers, cookies=cookies, data=data, timeout=10)
        logging.debug(f"📡 收到响应:{response} {response.text}")
        res = response.json()

        if not check_session_validity(res):
            handle_invalid_session()
            raise RuntimeError('❌ JSESSIONID已失效，请重新获取code')

        logging.info(f'加载周信息：{res.get('msg', 'Unknown error')}')
        if res.get('code') == '200' and 'data' in res:
            return res['data']
        else:
            raise RuntimeError(f"加载周信息失败: {res.get('msg', 'Unknown error')}")
    except Exception as e:
        raise RuntimeError(f"加载周信息请求异常: {e}")


def submit_blog(args, config, blog_title, blog_body, start_date, end_date, blog_open_type, trainee_id):
    """提交周记"""
    logging.info('正在提交周记...')
    url = "https://xcx.xybsyw.com/student/blog/Blog!save.action"

    data = {
        "blogType": "1",
        "blogTitle": blog_title,
        "blogBody": blog_body,
        "blogOpenType": str(blog_open_type),  # 查看权限：1-公开，2-仅自己
        "traineeId": str(trainee_id),
        "isDraft": "0",
        "startDate": start_date,
        "endDate": end_date,
        "backgroundTemplateId": "0",
        "fileJson": "[{\"fileName\":\"\"}]",
        "blogId": "undefined"
    }

    header_token = get_header_token(data)
    headers = {
        "content-type": "application/x-www-form-urlencoded",
        "devicecode": get_device_code(openId=args['openId'], device=config['device']),
        "encryptvalue": args['encryptValue'],
        "m": header_token['m'],
        "n": "content,deviceName,keyWord,blogBody,blogTitle,getType,responsibilities,street,text,reason,searchvalue,key,answers,leaveReason,personRemark,selfAppraisal,imgUrl,wxname,deviceId,avatarTempPath,file,file,model,brand,system,deviceId,platform,code,openId,unionid,clockDeviceToken,clockDevice,address,name,enterpriseEmail,responsibilities,practiceTarget,guardianName,guardianPhone,practiceDays,linkman,enterpriseName,companyIntroduction,accommodationStreet,accommodationLongitude,accommodationLatitude,internshipDestination,specialStatement,enterpriseStreet,insuranceName,insuranceFinancing,policyNumber,overtimeRemark,riskStatement,specialStatement",
        "referer": "https://servicewechat.com/wx9f1c2e0bbc10673c/539/page-frame.html",
        "s": header_token['s'],
        "t": header_token['t'],
        "user-agent": config['userAgent'],
        "v": XYB_VERSION,
        "wechat": "1",
        "xweb_xhr": "1"
    }
    cookies = {
        "JSESSIONID": args['sessionId']
    }

    try:
        logging.debug(f"🛩️ 准备发起请求。url:{url}, headers:{headers}, data:{data}, cookies:{cookies}")
        response = requests.post(url, headers=headers, cookies=cookies, data=data, timeout=10)
        logging.debug(f"📡 收到响应:{response} {response.text}")
        res = response.json()

        if not check_session_validity(res):
            handle_invalid_session()
            raise RuntimeError('❌ JSESSIONID已失效，请重新获取code')

        logging.info(f"提交周记结果: {res}")
        if res.get('code') == '200':
            logging.info(f"提交周记成功: {res.get('msg', 'Unknown error')}")
            return res.get('data')
        else:
            raise RuntimeError(f"提交周记失败: {res.get('msg', 'Unknown error')}")
    except Exception as e:
        raise RuntimeError(f"提交周记请求异常: {e}")


def xyb_completion(args, config, prompt, on_delta=None):
    """
    调用 AI 完成接口
    :param args: 登录参数
    :param config: 配置
    :param prompt: 提示词
    :param on_delta: 流式输出回调函数，接收每个文本片段
    :return: 完整的生成内容
    """
    data = {
        "processType": "0",
        "content": prompt,
        "questionType": "0",
        "type": "0",
        "aiSessionMsgType": "4"
    }
    header_token = get_header_token(data)
    headers = {
        "content-type": "application/x-www-form-urlencoded",
        "devicecode": get_device_code(openId=args['openId'], device=config['device']),
        "encryptvalue": args['encryptValue'],
        "m": header_token['m'],
        "n": "content,deviceName,keyWord,blogBody,blogTitle,getType,responsibilities,street,text,reason,searchvalue,key,answers,leaveReason,personRemark,selfAppraisal,imgUrl,wxname,deviceId,avatarTempPath,file,file,model,brand,system,deviceId,platform,code,openId,unionid,clockDeviceToken,clockDevice,address,name,enterpriseEmail,responsibilities,practiceTarget,guardianName,guardianPhone,practiceDays,linkman,enterpriseName,companyIntroduction,accommodationStreet,accommodationLongitude,accommodationLatitude,internshipDestination,specialStatement,enterpriseStreet,insuranceName,insuranceFinancing,policyNumber,overtimeRemark,riskStatement,specialStatement",
        "referer": "https://servicewechat.com/wx9f1c2e0bbc10673c/537/page-frame.html",
        "s": header_token['s'],
        "t": header_token['t'],
        "user-agent": config['userAgent'],
        "v": XYB_VERSION,
        "wechat": "1",
        "xweb_xhr": "1"
    }
    cookies = {
        "JSESSIONID": args['sessionId']
    }
    url = "https://xcx.xybsyw.com/careerplanning/saveSession.action"

    try:
        import json
        response = requests.post(url, data=data, headers=headers, cookies=cookies, timeout=60)
        res = response.json()

        if res.get('code') == '200' and 'data' in res:
            content = res['data'].get('content', '')
            if on_delta and content:
                # 模拟流式输出效果
                for char in content:
                    on_delta(char)
            return content
        else:
            raise RuntimeError(f"AI生成失败: {res.get('msg', 'Unknown error')}")
    except json.JSONDecodeError as e:
        logging.error(f"AI响应解析失败: {e}")
        raise RuntimeError(f"AI响应解析失败: {e}")
    except Exception as e:
        logging.error(f"AI生成请求异常: {e}")
        raise RuntimeError(f"AI生成请求异常: {e}")


def blog_list(args, config, page, blogType="1"):
    logging.info(f'正在加载第{page}页周记列表...')
    data = {
        "blogType": blogType,
        "planId": "",
        "reviewStatus": "null",
        "page": str(page)
    }
    header_token = get_header_token(data)
    headers = {
        "content-type": "application/x-www-form-urlencoded",
        "devicecode": get_device_code(openId=args['openId'], device=config['device']),
        "encryptvalue": args['encryptValue'],
        "m": header_token['m'],
        "n": "content,deviceName,keyWord,blogBody,blogTitle,getType,responsibilities,street,text,reason,searchvalue,key,answers,leaveReason,personRemark,selfAppraisal,imgUrl,wxname,deviceId,avatarTempPath,file,file,model,brand,system,deviceId,platform,code,openId,unionid,clockDeviceToken,clockDevice,address,name,enterpriseEmail,responsibilities,practiceTarget,guardianName,guardianPhone,practiceDays,linkman,enterpriseName,companyIntroduction,accommodationStreet,accommodationLongitude,accommodationLatitude,internshipDestination,specialStatement,enterpriseStreet,insuranceName,insuranceFinancing,policyNumber,overtimeRemark,riskStatement,specialStatement",
        "referer": "https://servicewechat.com/wx9f1c2e0bbc10673c/537/page-frame.html",
        "s": header_token['s'],
        "t": header_token['t'],
        "user-agent": config['userAgent'],
        "v": XYB_VERSION,
        "wechat": "1",
        "xweb_xhr": "1"
    }
    cookies = {
        "JSESSIONID": args['sessionId']
    }
    url = "https://xcx.xybsyw.com/student/blog/BlogList.action"

    try:
        logging.debug(f"🛩️ 准备发起请求。url:{url}, headers:{headers}, data:{data}, cookies:{cookies}")
        response = requests.post(url, headers=headers, cookies=cookies, data=data, timeout=10)
        logging.debug(f"📡 收到响应:{response} {response.text}")
        res = response.json()

        if not check_session_validity(res):
            handle_invalid_session()
            raise RuntimeError('❌ JSESSIONID已失效，请重新获取code')

        if res.get('code') == '200' and 'data' in res:
            return res['data']
        else:
            raise RuntimeError(f"获取周记列表失败: {res.get('msg', 'Unknown error')}")
    except Exception as e:
        raise RuntimeError(f"获取周记列表请求异常: {e}")
