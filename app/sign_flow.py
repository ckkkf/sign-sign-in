

def simple_sign_in_or_out(args, geo, traineeId, config, opt):
    logging.info(f'正在调用接口进行: {opt["action"]}...')
    url = "https://xcx.xybsyw.com/student/clock/Post.action"
    device = config['device']
    data = {'punchInStatus': "0",  # 2：普通签到，1：普通签退
            'clockStatus': str(opt['code']), 'traineeId': str(traineeId), 'adcode': geo['addressComponent']['adcode'],
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

        if code == "200":
            if msg == 'success':
                logging.info(f'✅ {opt["action"]}成功！')
            elif msg == '已经签到':
                logging.info(f'✅ 已经{opt["action"]}过了。')
        elif code == "403":
            logging.warning(f'⚠️ {msg}')
        elif code == "202":
            raise RuntimeError("配置错误，请检查device和userAgent参数 (Code 202)")
        else:
            raise RuntimeError(f'操作失败: {msg}')
    except Exception as e:
        raise RuntimeError(f"签到请求异常: {e}")
