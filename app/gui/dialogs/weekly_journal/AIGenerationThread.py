from PySide6.QtCore import QThread, Signal

from app.apis.xybsyw import xyb_completion
from app.utils.model_client import ModelConfigurationError


class AIGenerationThread(QThread):
    """AI生成周记的异步线程"""
    delta_signal = Signal(str)
    finished_signal = Signal(str)
    error_signal = Signal(str, str)  # error_type, message

    def __init__(self, args, config, prompt, system_prompt):
        super().__init__()
        self.args = args
        self.config = config
        self.prompt = prompt
        self.system_prompt = system_prompt

    def run(self):
        try:
            def on_delta(delta: str):
                self.delta_signal.emit(delta)

            content = xyb_completion(
                args=self.args,
                config=self.config,
                prompt=self.prompt,
                on_delta=on_delta
            )

            self.finished_signal.emit(content)
        except ModelConfigurationError as e:
            self.error_signal.emit("config", str(e))
        except Exception as e:
            self.error_signal.emit("error", f"调用模型失败：{e}")
