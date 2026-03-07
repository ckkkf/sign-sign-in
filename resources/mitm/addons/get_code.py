import json
import urllib.request

from mitmproxy import http

CODE_RECEIVER_URL = "http://127.0.0.1:13141/code"

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

        # 3. 回传到主程序
        body = json.dumps({"code": code}).encode("utf-8")
        req = urllib.request.Request(
            CODE_RECEIVER_URL,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=2):
            pass
        print(f"[addon] ⚔️成功拦截code并回传到 {CODE_RECEIVER_URL}")

        # 关键：直接中断请求，不伪造响应
        flow.kill()


# 导出为 addon
addons = [GetCode()]
