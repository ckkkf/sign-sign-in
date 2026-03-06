import json
import logging
import math
import os
import random
import subprocess
import time

import requests
from PySide6.QtCore import QThread, Signal

from app.apis.xybsyw import login, get_plan, regeo, photo_sign_in_or_out, simple_sign_in_or_out
from app.config.common import CODE_FILE, CERT_FILE, MITM_PROXY
from app.utils.commands import get_system_proxy, set_proxy, check_port_listening, reset_proxy, check_cert, bash
from app.utils.files import read_config, check_img


class SignTaskThread(QThread):
    finished_signal = Signal(bool, str)

    def __init__(self, config_file, sign_option):
        super().__init__()
        self.config_file = config_file
        self.sign_option = sign_option
        self.mitm_process = None
        self.origin_proxy = None
        proxy_split = MITM_PROXY.split(':')
        self.target_host = proxy_split[0]
        self.target_port = proxy_split[1]
        self.code_file = CODE_FILE
        self.cert_file = CERT_FILE

    def run(self):
        try:
            self.check_stop()

            ### 获取配置文件相关
            # 读取并校验配置文件
            config = read_config(self.config_file)
            self._apply_location_jitter(config.get("input", {}))
            # 校验其他文件
            if "拍照" in self.sign_option['action']:
                check_img(self.sign_option.get("image_path"))

            # 检查是否有有效的session缓存，如果有就直接使用，不需要重新获取code
            from app.utils.files import get_valid_session_cache
            cached_session = get_valid_session_cache()

            if cached_session:
                logging.info("✅ 使用缓存的JSESSIONID，跳过获取code步骤")
                # 直接使用缓存的session执行逻辑
                # 需要将缓存的session信息合并到config中
                config['input'].update({
                    'openId': cached_session.get('openId'),
                    'unionId': cached_session.get('unionId'),
                    'encryptValue': cached_session.get('encryptValue'),
                    'sessionId': cached_session.get('sessionId')
                })
            else:
                # 没有有效缓存，需要获取code
                # 删除旧code文件
                if os.path.exists(self.code_file):
                    os.remove(self.code_file)

                ### 代理
                target_proxy = f"{self.target_host}:{self.target_port}"
                # 获取当前代理
                logging.info(f"🔍 检测代理... 当前: {get_system_proxy() or '直连'}")
                self.origin_proxy = set_proxy(target_proxy)

                ### mitmdump
                if not check_port_listening(self.target_host, int(self.target_port)):
                    # 不再在这里强行启动，让后台 MonitorThread 负责自启
                    raise RuntimeError("mitmdump未运行，请稍等几秒后重新点击开始（后台会自动尝试启动mitmdump）")
                else:
                    logging.info("🛡️ 代理服务正常")

                ### cert
                self.do_cert()

                logging.warning("⏳ 请重启校友邦小程序，以获取code...")

                code = self.wait_code(self.code_file, target_proxy)
                config['input']['code'] = code
                logging.info(f"✅ Code: {code}")

                logging.info("🛑 恢复网络...")
                reset_proxy(self.origin_proxy, target_proxy)

            self.check_stop()

            self.execute_logic(config['input'])

            self.finished_signal.emit(True, "执行完毕")

        except RuntimeError as e:
            msg = str(e)
            if msg == "用户停止执行":
                logging.info("🚫 任务手动停止")
                self.finished_signal.emit(False, "任务已停止")
            else:
                logging.error(f"❌ 错误: {msg}")
                self.finished_signal.emit(False, msg)
        except Exception as e:
            logging.error(f"❌ 异常: {e}")
            self.finished_signal.emit(False, str(e))
        finally:
            reset_proxy(self.origin_proxy, f"{self.target_host}:{self.target_port}")

    @staticmethod
    def _jitter_location(latitude: float, longitude: float, radius_meters: float) -> tuple[float, float]:
        """
        在给定半径内随机生成新坐标（米级抖动）。
        """
        # 使用 sqrt 保证在圆内均匀分布
        distance = radius_meters * math.sqrt(random.random())
        bearing = random.random() * 2 * math.pi

        earth_radius = 6378137.0
        lat1 = math.radians(latitude)
        lon1 = math.radians(longitude)
        ang_dist = distance / earth_radius

        lat2 = math.asin(
            math.sin(lat1) * math.cos(ang_dist)
            + math.cos(lat1) * math.sin(ang_dist) * math.cos(bearing)
        )
        lon2 = lon1 + math.atan2(
            math.sin(bearing) * math.sin(ang_dist) * math.cos(lat1),
            math.cos(ang_dist) - math.sin(lat1) * math.sin(lat2),
        )

        return math.degrees(lat2), math.degrees(lon2)

    def _apply_location_jitter(self, input_cfg: dict):
        location = input_cfg.get("location")
        if not isinstance(location, dict):
            return

        try:
            lon = float(location.get("longitude"))
            lat = float(location.get("latitude"))
        except (TypeError, ValueError):
            return

        # 允许在配置中覆盖抖动半径（米），默认 80 米
        radius = input_cfg.get("locationJitterMeters", 80)
        try:
            radius = float(radius)
        except (TypeError, ValueError):
            radius = 80.0
        radius = max(0.0, min(radius, 500.0))

        if radius <= 0:
            return

        new_lat, new_lon = self._jitter_location(lat, lon, radius)
        location["latitude"] = f"{new_lat:.6f}"
        location["longitude"] = f"{new_lon:.6f}"
        logging.info(
            f"📍 已应用位置抖动，半径≈{int(radius)}m，坐标更新为 {location['longitude']}, {location['latitude']}"
        )

    def check_stop(self):
        if self.isInterruptionRequested(): raise RuntimeError("用户停止执行")

    def wait_code(self, fpath, proxy):
        last = time.time()
        for _ in range(1200):
            self.check_stop()
            if time.time() - last > 1.0:
                if get_system_proxy() != proxy: set_proxy(proxy)
                last = time.time()
            if os.path.exists(fpath):
                try:
                    with open(fpath) as f:
                        d = json.load(f)
                        if d.get("code"): return d['code'].strip()
                except:
                    pass
            time.sleep(0.1)
        raise RuntimeError("获取 Code 超时")

    def execute_logic(self, config):
        logging.info("🚀 开始业务逻辑...")

        self.check_stop()
        # 使用缓存的登录信息，如果缓存过期则使用新获取的code
        args = login(config, use_cache=True)

        self.check_stop()
        plan_data = get_plan(userAgent=config['userAgent'], args=args)

        self.check_stop()
        geo = regeo(config['userAgent'], config['location'])

        self.check_stop()

        action = self.sign_option['action']
        if action in ['普通签到', '普通签退']:
            simple_sign_in_or_out(args=args, config=config, geo=geo, traineeId=plan_data[0]['dateList'][0]['traineeId'],
                                  opt=self.sign_option)
        elif action in ['拍照签到', '拍照签退']:
            photo_sign_in_or_out(args=args, config=config, geo=geo, traineeId=plan_data[0]['dateList'][0]['traineeId'],
                                 opt=self.sign_option)

    def do_cert(self):
        ### 检查是否安装证书
        if check_cert():
            logging.info("CA证书状态正常")
            return

        logging.warning("⚠️ 证书未安装")

        ### 下载证书
        self.download_cert(self.cert_file, MITM_PROXY)

        ### 安装证书
        self.install_cert(self.cert_file)

        # ### 关闭 mitmproxy
        # stop_mitmproxy(process)

        ### 重启 mitmproxy
        logging.info("🔰🔰🔰 证书安装完成，请稍等，后台将自动重启 mitmdump 🔰🔰🔰")

    def download_cert(self, file_name, proxy):
        # 发送 GET 请求下载文件获取 .p12 格式的证书
        # response = requests.get('http://mitm.it/cert/p12')

        count = 3
        for i in range(count):
            try:
                response = requests.get('http://mitm.it/cert/pem', proxies={"http": proxy, "https": proxy})
                logging.info(f"正在下载证书... (第 {i + 1} 次尝试)")
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

    def install_cert(self, file_name):
        logging.info("正在安装证书，若出现弹窗请点击[确定]！")
        # 使用 certutil 安装证书到 Windows 系统中
        try:
            # 安装证书
            while True:
                stdout = bash(f'certutil -user -addstore Root "{file_name}"')
                # 再次检测
                if stdout and '命令成功完成' in stdout and check_cert():
                    logging.info("安装成功")
                    break

                logging.warning("⚠️请点击[确定]以同意安装ssl证书，否则将无法使用本程序！")

        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"❌ 安装证书时发生错误: {e}")


class GetCodeAndSessionThread(QThread):
    """获取Code和JSESSIONID的线程"""
    finished_signal = Signal(bool, str)

    def __init__(self, config_file):
        super().__init__()
        self.config_file = config_file
        self.origin_proxy = None
        proxy_split = MITM_PROXY.split(':')
        self.target_host = proxy_split[0]
        self.target_port = proxy_split[1]
        self.code_file = CODE_FILE
        self.cert_file = CERT_FILE

    def run(self):
        try:
            self.check_stop()

            ### 获取配置文件相关
            config = read_config(self.config_file)

            # 删除旧code文件
            if os.path.exists(self.code_file):
                os.remove(self.code_file)

            ### 代理
            target_proxy = f"{self.target_host}:{self.target_port}"
            logging.info(f"🔍 检测代理... 当前: {get_system_proxy() or '直连'}")
            self.origin_proxy = set_proxy(target_proxy)

            ### mitmdump
            if not check_port_listening(self.target_host, int(self.target_port)):
                raise RuntimeError("mitmdump未运行，请稍等几秒后重新点击（后台会自动尝试启动mitmdump）")
            else:
                logging.info("🛡️ 代理服务正常")

            ### cert
            self.do_cert()

            ### 唤起微信小程序
            weixin_url = "weixin://launchapplet/?app_id=wx9f1c2e0bbc10673c"
            try:
                os.startfile(weixin_url)
                logging.info("🌈 已发送唤醒指令到微信")
            except Exception as e:
                # 用户环境未注册 weixin:// 协议时，不中断流程，提示手动打开小程序
                logging.warning(f"⚠️ 自动唤起微信失败: {e}")
                logging.warning("👉 请手动启动【微信 -> 校友邦】小程序，然后保持页面操作以获取 code")

            logging.warning("⏳ 请重启校友邦小程序，以获取code...")

            code = self.wait_code(self.code_file, target_proxy)
            config['input']['code'] = code
            logging.info(f"✅ Code: {code}")

            logging.info("🛑 恢复网络...")
            reset_proxy(self.origin_proxy, target_proxy)

            self.check_stop()

            # 获取JSESSIONID
            logging.info("🔐 正在获取JSESSIONID...")
            args = login(config['input'], use_cache=False)
            logging.info(f"✅ JSESSIONID: {args['sessionId'][:20]}...")

            self.finished_signal.emit(True, "获取成功")

        except RuntimeError as e:
            msg = str(e)
            if msg == "用户停止执行":
                logging.info("🚫 任务手动停止")
                self.finished_signal.emit(False, "任务已停止")
            else:
                logging.error(f"❌ 错误: {msg}")
                self.finished_signal.emit(False, msg)
        except Exception as e:
            logging.error(f"❌ 异常: {e}")
            self.finished_signal.emit(False, str(e))
        finally:
            reset_proxy(self.origin_proxy, f"{self.target_host}:{self.target_port}")

    def check_stop(self):
        if self.isInterruptionRequested():
            raise RuntimeError("用户停止执行")

    def wait_code(self, fpath, proxy):
        last = time.time()
        for _ in range(1200):
            self.check_stop()
            if time.time() - last > 1.0:
                if get_system_proxy() != proxy:
                    set_proxy(proxy)
                last = time.time()
            if os.path.exists(fpath):
                try:
                    with open(fpath) as f:
                        d = json.load(f)
                        if d.get("code"):
                            return d['code'].strip()
                except:
                    pass
            time.sleep(0.1)
        raise RuntimeError("获取 Code 超时")

    def do_cert(self):
        if check_cert():
            logging.info("CA证书状态正常")
            return

        logging.warning("⚠️ 证书未安装")
        self.download_cert(self.cert_file, MITM_PROXY)
        self.install_cert(self.cert_file)
        logging.info("🔰🔰🔰 证书安装完成，请稍等，后台将自动重启 mitmdump 🔰🔰🔰")

    def download_cert(self, file_name, proxy):
        count = 3
        for i in range(count):
            try:
                response = requests.get('http://mitm.it/cert/pem', proxies={"http": proxy, "https": proxy})
                logging.info(f"正在下载证书... (第 {i + 1} 次尝试)")
                if response.status_code == 200:
                    os.makedirs(os.path.dirname(file_name), exist_ok=True)
                    with open(file_name, 'wb') as file:
                        file.write(response.content)
                    logging.info(f'SSL证书下载成功，保存为 {file_name}')
                    return file_name
                logging.error(f"❌ 下载失败，HTTP 状态码：{response.status_code}")
            except Exception as e:
                logging.error(f"❌ 下载失败: {e}")
        raise RuntimeError(f"❌ 下载SSL证书失败！")

    def install_cert(self, file_name):
        logging.info("正在安装证书，若出现弹窗请点击[确定]！")
        try:
            while True:
                stdout = bash(f'certutil -user -addstore Root "{file_name}"')
                if stdout and '命令成功完成' in stdout and check_cert():
                    logging.info("安装成功")
                    break
                logging.warning("⚠️请点击[确定]以同意安装ssl证书，否则将无法使用本程序！")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"❌ 安装证书时发生错误: {e}")
