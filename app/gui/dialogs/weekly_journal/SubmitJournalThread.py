from PySide6.QtCore import QThread, Signal


class SubmitJournalThread(QThread):
    """提交周记的异步线程"""
    finished_signal = Signal(str)
    error_signal = Signal(str)

    def __init__(self, args, config, blog_title, blog_body, start_date, end_date, blog_open_type, trainee_id):
        super().__init__()
        self.args = args
        self.config = config
        self.blog_title = blog_title
        self.blog_body = blog_body
        self.start_date = start_date
        self.end_date = end_date
        self.blog_open_type = blog_open_type
        self.trainee_id = trainee_id
        self.content = blog_body

    def run(self):
        try:
            if self.isInterruptionRequested():
                return
            from app.apis.xybsyw import submit_blog
            submit_blog(
                args=self.args, config=self.config, blog_title=self.blog_title, blog_body=self.blog_body,
                start_date=self.start_date, end_date=self.end_date, blog_open_type=self.blog_open_type,
                trainee_id=self.trainee_id)
            if self.isInterruptionRequested():
                return
            self.finished_signal.emit("周记提交成功！")
        except Exception as e:
            self.error_signal.emit(str(e))
