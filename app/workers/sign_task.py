import json
import logging
import os
import subprocess
import time

import requests
from PySide6.QtCore import QThread, Signal

from app.apis.sybsyw import login, get_plan, regeo, photo_sign_in_or_out
from app.sign_flow import simple_sign_in_or_out
from app.utils.commands import get_system_proxy, set_proxy, check_port_listening, reset_proxy, kill_process_tree, \
    get_process_by_port, check_cert, bash
from app.utils.files import read_and_varify_config, check_img


class SignTaskThread(QThread):
    finished_signal = Signal(bool, str)

    def __init__(self, config_file, sign_option):
        super().__init__()
        self.config_file = config_file
        self.sign_option = sign_option
        self.mitm_process = None
        self.origin_proxy = None
        self.target_port = 13140
        self.target_host = "127.0.0.1"
        self.code_file = "bin/code.json"
        self.cert_file = "cert/mitmproxy-ca-cert.p12"

    def run(self):
        try:
            self.check_stop()

            ### 获取配置文件相关
            # 读取并校验配置文件
            config = read_and_varify_config(self.config_file)
            # 校验其他文件
            if self.sign_option['action'] == "拍照签到":
                check_img()
            # 删除旧code文件
            if os.path.exists(self.code_file):
                os.remove(self.code_file)

            ### 代理
            target_proxy = f"{self.target_host}:{self.target_port}"
            # 获取当前代理
            logging.info(f"🔍 检测代理... 当前: {get_system_proxy() or '直连'}")
            self.origin_proxy = set_proxy(target_proxy)

            ### mitmdump
            if not check_port_listening(self.target_host, self.target_port):
                logging.warning("⚠️ 服务未响应，尝试重启...")
                self.start_mitm()
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
            reset_proxy(self.origin_proxy, f"127.0.0.1:{self.target_port}")

    def check_stop(self):
        if self.isInterruptionRequested(): raise RuntimeError("用户停止执行")

    def start_mitm(self):
        path = 'bin/mitmdump.exe'
        script = 'bin/get_code.py'
        if check_port_listening("127.0.0.1", 13140, 0.1):
            proc = get_process_by_port(13140)
            if proc: kill_process_tree(proc.pid)
        subprocess.Popen([path, "-p", "13140", "-s", script, "--quiet"], creationflags=subprocess.CREATE_NO_WINDOW)
        time.sleep(2)

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
        args = login(config)

        self.check_stop()
        plan_data = get_plan(userAgent=config['userAgent'], args=args)

        self.check_stop()
        geo = regeo(config['userAgent'], config['location'])

        self.check_stop()

        action = self.sign_option['action']
        if action in ['普通签到', '普通签退']:
            simple_sign_in_or_out(args=args, config=config, geo=geo, traineeId=plan_data[0]['dateList'][0]['traineeId'],
                                  opt=self.sign_option)
        elif action == '拍照签到':
            photo_sign_in_or_out(args=args, config=config, geo=geo, traineeId=plan_data[0]['dateList'][0]['traineeId'],
                                 opt=self.sign_option)

    def do_cert(self, process, host, port):
        ### 检查是否安装证书
        if check_cert():
            logger.info("CA证书状态正常")
            return process

        logging.warning("⚠️ 证书未安装")

        ### 下载证书
        self.download_cert(self.cert_file, f"{host}:{port}")

        ### 安装证书
        self.install_cert(self.cert_file)

        # ### 关闭 mitmproxy
        # stop_mitmproxy(process)

        ### 重启 mitmproxy
        logging.info("🔰🔰🔰 正在重启 mitmdump 🔰🔰🔰")
        process = self.restart_mitmproxy(process, port)
        if not process:
            raise RuntimeError("mitmdump 重启失败")

        return process

    def download_cert(self, file_name, proxy):
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

    def install_cert(self, file_name):
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
