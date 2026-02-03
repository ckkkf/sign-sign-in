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
            with open("debug_crash.txt", "a", encoding="utf-8") as f: f.write("THREAD STEP 1: Thread started\n")
            from app.apis.xybsyw import login, get_plan, load_blog_year

            # 尝试使用缓存的登录信息
            try:
                with open("debug_crash.txt", "a", encoding="utf-8") as f: f.write("THREAD STEP 2: Attempting login\n")
                login_args = login(self.config['input'], use_cache=True)
                with open("debug_crash.txt", "a", encoding="utf-8") as f: f.write("THREAD STEP 3: Login successful\n")
            except Exception as login_err:
                with open("debug_crash.txt", "a", encoding="utf-8") as f: f.write(f"THREAD ERROR: Login failed - {login_err}\n")
                self.error_signal.emit(f"使用缓存登录失败: {login_err}")
                return

            # 获取traineeId
            with open("debug_crash.txt", "a", encoding="utf-8") as f: f.write("THREAD STEP 4: Getting plan\n")
            plan_data = get_plan(userAgent=self.config['input']['userAgent'], args=login_args)
            with open("debug_crash.txt", "a", encoding="utf-8") as f: f.write("THREAD STEP 5: Plan got\n")
            
            trainee_id = None
            if plan_data and len(plan_data) > 0 and 'dateList' in plan_data[0] and len(plan_data[0]['dateList']) > 0:
                trainee_id = plan_data[0]['dateList'][0]['traineeId']
                login_args['traineeId'] = trainee_id
            
            with open("debug_crash.txt", "a", encoding="utf-8") as f: f.write(f"THREAD STEP 6: TraineeId extracted: {trainee_id}\n")

            # 加载年份数据
            with open("debug_crash.txt", "a", encoding="utf-8") as f: f.write("THREAD STEP 7: Loading year data\n")
            year_data = load_blog_year(login_args, self.config['input'])
            with open("debug_crash.txt", "a", encoding="utf-8") as f: f.write("THREAD STEP 8: Year data loaded\n")

            self.finished_signal.emit(login_args, str(trainee_id), year_data)
            with open("debug_crash.txt", "a", encoding="utf-8") as f: f.write("THREAD STEP 9: Finished signal emitted\n")
            
        except Exception as e:
            import traceback
            err_msg = traceback.format_exc()
            with open("debug_crash.txt", "a", encoding="utf-8") as f: f.write(f"THREAD CRASH: {e}\n{err_msg}\n")
            self.error_signal.emit(str(e))
