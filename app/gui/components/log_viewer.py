import logging

from PySide6.QtCore import Signal, QObject


class QTextEditLogger(logging.Handler, QObject):
    append_signal = Signal(str, str)

    def __init__(self, widget):
        super().__init__()
        QObject.__init__(self)
        self.widget = widget
        self.append_signal.connect(self.append_text)

    def emit(self, record):
        msg = self.format(record)
        self.append_signal.emit(record.levelname, msg)

    def append_text(self, level, msg):
        color = "#E0E0E0"
        if level == "INFO":
            color = "#58D68D"
        elif level == "WARNING":
            color = "#F4D03F"
        elif level == "ERROR":
            color = "#EC7063"
        elif level == "DEBUG":
            color = "#888888"

        sb = self.widget.verticalScrollBar()
        at_bottom = sb.value() >= (sb.maximum() - 10)
        self.widget.append(f'<span style="color:{color}; font-family:Consolas; font-size:10pt;">{msg}</span>')
        if at_bottom: sb.setValue(sb.maximum())
