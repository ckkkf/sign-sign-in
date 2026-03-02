from PySide6.QtCore import QThread, Signal
from app.apis.xybsyw import blog_list

class LoadBlogListThread(QThread):
    # blog_list 可能返回 dict 或 list，统一用 object 避免信号类型不匹配
    finished_signal = Signal(object)
    error_signal = Signal(str)

    def __init__(self, args, config, page=1):
        super().__init__()
        self.args = args
        self.config = config
        self.page = page

    def run(self):
        try:
            if self.isInterruptionRequested():
                return
            data = blog_list(self.args, self.config, self.page)
            if self.isInterruptionRequested():
                return
            self.finished_signal.emit(data)
        except Exception as e:
            self.error_signal.emit(str(e))
