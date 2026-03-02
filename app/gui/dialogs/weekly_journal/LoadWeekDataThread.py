from PySide6.QtCore import QThread, Signal
from app.apis.xybsyw import load_blog_date

class LoadWeekDataThread(QThread):
    finished_signal = Signal(list)
    error_signal = Signal(str)

    def __init__(self, args, config, year_id, month_id):
        super().__init__()
        self.args = args
        self.config = config
        self.year_id = year_id
        self.month_id = month_id

    def run(self):
        try:
            if self.isInterruptionRequested():
                return
            data = load_blog_date(self.args, self.config, self.year_id, self.month_id)
            if self.isInterruptionRequested():
                return
            self.finished_signal.emit(data)
        except Exception as e:
            self.error_signal.emit(str(e))
