from PySide6.QtCore import QThread, Signal

from app.utils.pushplus import notify_pushplus


class PushplusWorker(QThread):
    result_signal = Signal(bool, str)

    def __init__(self, token: str, title: str, content: str):
        super().__init__()
        self.token = token
        self.title = title
        self.content = content

    def run(self):
        try:
            text = notify_pushplus(
                title=self.title,
                content=self.content,
                token=self.token,
            )
            self.result_signal.emit(True, text[:200] or "success")
        except Exception as exc:
            self.result_signal.emit(False, str(exc))
