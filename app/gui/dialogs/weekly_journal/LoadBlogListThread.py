from PySide6.QtCore import QThread, Signal
from app.apis.xybsyw import blog_list

class LoadBlogListThread(QThread):
    finished_signal = Signal(dict)
    error_signal = Signal(str)

    def __init__(self, args, config, page=1):
        super().__init__()
        self.args = args
        self.config = config
        self.page = page

    def run(self):
        try:
            data = blog_list(self.args, self.config, self.page)
            self.finished_signal.emit(data)
        except Exception as e:
            self.error_signal.emit(str(e))
