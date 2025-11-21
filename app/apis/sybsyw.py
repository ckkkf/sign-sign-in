import logging

import requests

from app.utils.common import get_timestamp
from app.utils.files import get_img_file
from app.utils.params import get_header_token, get_device_code


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
        response = requests.get(url, headers=headers, params=params, timeout=5)
        json_data = response.json()
        if 'regeocode' in json_data:
            logging.info(f"📍 解析位置: {json_data['regeocode']['formatted_address']}")
            return json_data['regeocode']
        else:
            raise RuntimeError(f"位置解析失败: {json_data}")
    except Exception as e:
        logging.error(f"高德接口请求失败: {e}")
        raise e


def get_plan(userAgent, args):
    logging.info('正在获取实习计划...')
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

    try:
        response = requests.post(url, headers=headers, cookies=cookies, data=data, timeout=5)
        res = response.json()
        if 'data' in res and res['data']:
            return res['data']
        else:
            raise RuntimeError(f"获取计划失败: {res.get('msg', 'Unknown error')}")
    except Exception as e:
        raise RuntimeError(f"计划接口请求异常: {e}")


def get_open_id(config, code):
    logging.info("正在获取open_id...")
    headers = {
        "v": "1.6.39",
        "xweb_xhr": "1",
        "content-type": "application/x-www-form-urlencoded",
        "referer": "https://servicewechat.com/wx9f1c2e0bbc10673c/534/page-frame.html",
        'User-Agent': config['userAgent'],
        "devicecode": get_device_code("", config['device']),
    }
    url = "https://xcx.xybsyw.com/common/getOpenId.action"
    try:
        response = requests.post(url=url, headers=headers, data={"code": code}, allow_redirects=False, timeout=5)
        json_data = response.json()
        if json_data.get('code') == '202':
            raise RuntimeError('Code已失效，请重启小程序')
        return json_data['data']
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
        "v": "1.6.39",
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
        response = requests.post(url, headers=headers, cookies=cookies, data=data, timeout=5)
        return response.json()['data']
    except Exception as e:
        raise RuntimeError(f"登录失败: {e}")


def login(config):
    logging.info('正在执行登录流程...')
    code = config['code']
    if not code or code == '': raise RuntimeError('❌ Code为空，请重新获取！')

    ### 获取open_id、union_id等信息
    openIdData = get_open_id(config=config, code=code)

    ### 获取登录参数encryptValue、sessionId
    login_data = wx_login(config=config, openIdData=openIdData)

    return {
        'openId': openIdData['openId'],
        'unionId': openIdData['unionId'],
        'encryptValue': login_data['encryptValue'],
        'sessionId': login_data['sessionId'],
    }


# ------------------------------拍照签到----------------------------------------


def photo_sign_in_or_out(args, config, geo, traineeId, opt):
    # watermark_info(args=args, config=config, traineeId=traineeId)
    logging.info('正在执行拍照签到流程...')

    policyData = commonPostPolicy(args=args, config=config)

    timestamp = get_timestamp()

    files = get_img_file(timestamp)

    ossData = aliyun_OSS(files=files, timestamp=timestamp, policyData=policyData)

    post_new(args=args, config=config, traineeId=traineeId, geo=geo, imgUrl=ossData['key'])

    deliver_value(args=args, config=config, traineeId=traineeId)


def watermark_info(args, config, traineeId):
    url = "https://xcx.xybsyw.com/student/clock/postNew!watermarkInfo.action"

    data = {
        "traineeId": traineeId
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
        "v": "1.6.39",
        "wechat": "1",
        "xweb_xhr": "1"
    }
    cookies = {"JSESSIONID": args['sessionId']}

    response = requests.post(url, headers=headers, cookies=cookies, data=data)

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
        "v": "1.6.39",
        "wechat": "1",
        "xweb_xhr": "1"
    }
    cookies = {
        "JSESSIONID": args['sessionId']
    }

    response = requests.post(url, headers=headers, cookies=cookies, data=data)

    logging.info(f"{response} {response.text}")

    if response.status_code != 200 or response.json()['code'] != "200":
        raise RuntimeError(f"commonPostPolicy请求异常, {response} {response.text}")

    return response.json()['data']


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
    #     "v": "1.6.39",
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

    response = requests.post(url, data=data, files=files, headers=headers)

    logging.info(f"{response} {response.text}")

    if response.status_code != 200:
        raise RuntimeError(f"aliyun_OSS请求异常, {response} {response.text}")

    return response.json()['vo']


def post_new(args, config, traineeId, geo, imgUrl):
    url = "https://xcx.xybsyw.com/student/clock/PostNew.action"

    data = {
        "traineeId": traineeId,
        "adcode": geo['addressComponent']['adcode'],
        "lat": config['location']['latitude'],
        "lng": config['location']['longitude'],
        "address": geo['formatted_address'],
        "deviceName": config['device']['model'],
        # "punchInStatus": "1",
        "punchInStatus": "0",
        "clockStatus": "2",
        # "imgUrl": "temp/20251119/school/14422/xcx/student/clock/11621617/1763557557282.jpg",
        "imgUrl": imgUrl,
        "reason": "",
        "addressId": "null"
    }

    header_token = get_header_token(args)
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
        "v": "1.6.39",
        "wechat": "1",
        "xweb_xhr": "1"
    }
    cookies = {"JSESSIONID": args['sessionId']}

    response = requests.post(url, headers=headers, cookies=cookies, data=data)

    logging.info(f"{response} {response.text}")

    if response.status_code != 200 or response.json()['code'] != "200":
        raise RuntimeError(f"post_new请求异常, {response} {response.text}")


def deliver_value(args, config, traineeId):
    url = "https://xcx.xybsyw.com/student/DeliverValue!post.action"

    data = {
        "traineeId": traineeId
    }

    header_token = get_header_token(args)
    headers = {
        "content-type": "application/x-www-form-urlencoded",
        "encryptvalue": args['encryptValue'],
        "m": header_token['m'],
        "n": "content,deviceName,keyWord,blogBody,blogTitle,getType,responsibilities,street,text,reason,searchvalue,key,answers,leaveReason,personRemark,selfAppraisal,imgUrl,wxname,deviceId,avatarTempPath,file,file,model,brand,system,deviceId,platform,code,openId,unionid,clockDeviceToken,clockDevice,address,name,enterpriseEmail,responsibilities,practiceTarget,guardianName,guardianPhone,practiceDays,linkman,enterpriseName,companyIntroduction,accommodationStreet,accommodationLongitude,accommodationLatitude,internshipDestination,specialStatement,enterpriseStreet,insuranceName,insuranceFinancing,policyNumber,overtimeRemark,riskStatement,specialStatement",
        "referer": "https://servicewechat.com/wx9f1c2e0bbc10673c/537/page-frame.html",
        "s": header_token['s'],
        "t": header_token['t'],
        "user-agent": config['userAgent'],
        "v": "1.6.39",
        "wechat": "1",
        "xweb_xhr": "1"
    }
    cookies = {"JSESSIONID": args['sessionId']}

    response = requests.post(url, headers=headers, cookies=cookies, data=data)
    logging.info(f"{response} {response.text}")

    if response.status_code != 200 or response.json()['code'] != "200":
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
    headers = {'v': "1.6.39", 'wechat': "1",
               'Referer': "https://servicewechat.com/wx9f1c2e0bbc10673c/534/page-frame.html",
               'User-Agent': config['userAgent'],
               'n': "content,deviceName,keyWord,blogBody,blogTitle,getType,responsibilities,street,text,reason,searchvalue,key,answers,leaveReason,personRemark,selfAppraisal,imgUrl,wxname,deviceId,avatarTempPath,file,file,model,brand,system,deviceId,platform,code,openId,unionid,clockDeviceToken,clockDevice,address,name,enterpriseEmail,responsibilities,practiceTarget,guardianName,guardianPhone,practiceDays,linkman,enterpriseName,companyIntroduction,accommodationStreet,accommodationLongitude,accommodationLatitude,internshipDestination,specialStatement,enterpriseStreet,insuranceName,insuranceFinancing,policyNumber,overtimeRemark,riskStatement,specialStatement",
               'm': header_token['m'], 's': header_token['s'], 't': header_token['t'],
               'encryptvalue': args['encryptValue'],
               'devicecode': get_device_code(openId=args['openId'], device=config['device']), }
    cookies = {"JSESSIONID": args['sessionId']}

    try:
        response = requests.post(url, data=data, headers=headers, cookies=cookies, timeout=5)
        logging.info(f'📡 服务器响应: {response.text}')
        json_resp = response.json()
        msg = json_resp['msg']
        code = json_resp['code']

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
