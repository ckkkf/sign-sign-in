class HttpWorker(QThread):
    result_signal = Signal(bool, str)

    def __init__(self, url, data):
        super().__init__()
        self.url = url
        self.data = data

    def run(self):
        try:
            response = requests.post(self.url, json=self.data, timeout=5)
            if response.status_code == 200:
                self.result_signal.emit(True, f"✅ 成功: {response.text[:200]}")
            else:
                self.result_signal.emit(False, f"❌ 状态码 {response.status_code}: {response.text[:200]}")
        except Exception as e:
            self.result_signal.emit(False, str(e))
