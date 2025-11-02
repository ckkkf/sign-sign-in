import json
import time

from mitmproxy import http

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
        with open("code.json", "w", encoding="utf-8") as f:
            json.dump({"code": code, "ts": time.time()}, f, ensure_ascii=False, indent=2)
        print(f"[addon] ⚔️成功拦截并写入 code: {code}")

        # 关键：阻止请求继续发送
        flow.response = http.Response.make(
            200,  # 状态码
            b'{"msg": ""}',  # 响应体
            {"Content-Type": "application/json"}  # 响应头
        )


# 导出为 addon
addons = [GetCode()]