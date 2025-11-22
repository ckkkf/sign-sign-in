import json
import os
import time

from mitmproxy import http

# code_file = sys.argv[4]

# 当前 addon 文件夹：app/mitm/addons
ADDON_DIR = os.path.dirname(os.path.abspath(__file__))

# 跳到 openSource（往上跳 3 层）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(ADDON_DIR)))

# resources/config/code.json
code_file = os.path.join(PROJECT_ROOT,"resources", "config", "code.json")

class GetCode:
    TARGET = "getOpenId.action"

    def request(self, flow: http.HTTPFlow):
        # 1. 精确匹配 URL
        if self.TARGET not in flow.request.pretty_url:
            return


        # 2. 提取 code
        code = flow.request.urlencoded_form.get("code")
        if not code:
            return

        # 3. 写入文件
        with open(code_file, "w", encoding="utf-8") as f:
            json.dump({"code": code, "ts": time.time()}, f, ensure_ascii=False, indent=2)
        print(f"[addon] ⚔️成功拦截code: {code}并写入{code_file} ")

        # 关键：阻止请求继续发送
        flow.response = http.Response.make(
            200,  # 状态码
            b'{"msg": ""}',  # 响应体
            {"Content-Type": "application/json"}  # 响应头
        )


# 导出为 addon
addons = [GetCode()]
