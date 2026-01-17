from PySide6.QtCore import QThread, Signal


class LoadYearDataThread(QThread):
    """加载年份数据的异步线程"""
    finished_signal = Signal(dict, str, list)  # login_args, trainee_id, year_data
    error_signal = Signal(str)

    def __init__(self, config):
        super().__init__()
        self.config = config

    def run(self):
        try:
            from app.apis.xybsyw import login, get_plan, load_blog_year

            # 尝试使用缓存的登录信息
            try:
                login_args = login(self.config['input'], use_cache=True)
            except Exception as login_err:
                self.error_signal.emit(f"使用缓存登录失败: {login_err}")
                return

            # 获取traineeId
            plan_data = get_plan(userAgent=self.config['input']['userAgent'], args=login_args)
            trainee_id = None
            if plan_data and len(plan_data) > 0 and 'dateList' in plan_data[0] and len(plan_data[0]['dateList']) > 0:
                trainee_id = plan_data[0]['dateList'][0]['traineeId']
                login_args['traineeId'] = trainee_id

            # 加载年份数据
            year_data = load_blog_year(login_args, self.config['input'])

            self.finished_signal.emit(login_args, trainee_id, year_data)
        except Exception as e:
            self.error_signal.emit(str(e))
