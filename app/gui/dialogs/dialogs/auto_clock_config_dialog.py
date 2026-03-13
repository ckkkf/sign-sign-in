import json
import os
from datetime import datetime

from PySide6.QtCore import QTime
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTimeEdit,
    QVBoxLayout,
)

from app.gui.components.toast import ToastManager
from app.utils.files import read_config, save_json_file
from app.workers.pushplus_worker import PushplusWorker


class AutoClockConfigDialog(QDialog):
    MODE_OPTIONS = [
        ("普通签到", "in"),
        ("普通签退", "out"),
        ("拍照签到", "photo_in"),
        ("拍照签退", "photo_out"),
    ]

    def __init__(self, config_path: str, parent=None):
        super().__init__(parent)
        self.config_path = config_path
        self.setWindowTitle("定时打卡配置")
        self.resize(760, 500)

        self.original_data = read_config(config_path)
        self.current_data = json.loads(json.dumps(self.original_data))
        self.current_data.setdefault("settings", {})
        self.current_data["settings"].setdefault("auto_clock", {})

        self.pushplus_worker = None

        self._setup_style()
        self._setup_ui()
        self._load_current_config()

    def _setup_style(self):
        self.setStyleSheet(
            """
            QDialog {
                background: #0F111A;
                color: #E6E9FF;
            }
            QLabel {
                color: #9AA4CF;
                font-weight: 600;
            }
            QCheckBox {
                color: #E6E9FF;
                spacing: 8px;
            }
            QSpinBox, QLineEdit, QTimeEdit, QComboBox {
                background: #1C2033;
                border: 1px solid #2F3654;
                color: #F5F6FF;
                padding: 6px 8px;
                border-radius: 8px;
            }
            QTableWidget {
                background: #151828;
                border: 1px solid #232841;
                color: #E6E9FF;
                gridline-color: #2A304A;
            }
            QHeaderView::section {
                background: #1B2033;
                color: #C8D0FF;
                padding: 6px;
                border: none;
                border-right: 1px solid #2A304A;
            }
            QPushButton {
                background: #1F2336;
                color: #D5D9FF;
                padding: 8px 14px;
                border: 1px solid #2F3452;
                border-radius: 10px;
                font-weight: 600;
            }
            QPushButton:hover {
                border-color: #7C89FF;
                color: white;
            }
            QPushButton#Primary {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4E8BFF, stop:1 #7A5BFF);
                color: white;
                border: none;
            }
            """
        )

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        header = QLabel("配置每天自动触发的打卡任务（同一任务每天只执行一次）")
        root.addWidget(header)

        top = QGridLayout()
        top.setHorizontalSpacing(12)
        top.setVerticalSpacing(8)

        self.enabled_cb = QCheckBox("启用定时打卡")
        self.poll_spin = QSpinBox()
        self.poll_spin.setRange(10, 300)
        self.poll_spin.setSuffix(" 秒")
        self.poll_spin.setValue(30)
        self.random_spin = QSpinBox()
        self.random_spin.setRange(0, 120)
        self.random_spin.setSuffix(" 分钟")
        self.random_spin.setValue(0)

        self.pushplus_token_edit = QLineEdit()
        self.pushplus_token_edit.setPlaceholderText("输入 PushPlus token（可为空）")

        top.addWidget(self.enabled_cb, 0, 0, 1, 2)
        top.addWidget(QLabel("轮询间隔"), 1, 0)
        top.addWidget(self.poll_spin, 1, 1)
        top.addWidget(QLabel("随机时间(±)"), 2, 0)
        top.addWidget(self.random_spin, 2, 1)
        top.addWidget(QLabel("PushPlus Token"), 3, 0)
        top.addWidget(self.pushplus_token_edit, 3, 1)
        root.addLayout(top)

        self.table = QTableWidget(0, 3, self)
        self.table.setHorizontalHeaderLabels(["时间", "模式", "拍照模式图片路径（可留空）"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 120)
        self.table.setColumnWidth(1, 140)
        root.addWidget(self.table)

        row_actions = QHBoxLayout()

        btn_add = QPushButton("新增任务")
        btn_add.clicked.connect(self._add_task_row)
        row_actions.addWidget(btn_add)

        btn_remove = QPushButton("删除所选")
        btn_remove.clicked.connect(self._remove_selected_rows)
        row_actions.addWidget(btn_remove)

        btn_pick = QPushButton("为所选任务选择图片")
        btn_pick.clicked.connect(self._choose_image_for_selected_row)
        row_actions.addWidget(btn_pick)

        self.btn_test_push = QPushButton("测试推送")
        self.btn_test_push.clicked.connect(self._test_pushplus)
        row_actions.addWidget(self.btn_test_push)

        row_actions.addStretch()
        root.addLayout(row_actions)

        bottom = QHBoxLayout()
        btn_open = QPushButton("打开 config.json")
        btn_open.clicked.connect(self._open_config_file)
        bottom.addWidget(btn_open)
        bottom.addStretch()

        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        bottom.addWidget(btn_cancel)

        btn_save = QPushButton("保存")
        btn_save.setObjectName("Primary")
        btn_save.clicked.connect(self._save)
        bottom.addWidget(btn_save)

        root.addLayout(bottom)

    def _load_current_config(self):
        settings = self.current_data.get("settings", {})
        auto_clock = settings.get("auto_clock", {})
        pushplus = settings.get("pushplus", {})

        self.enabled_cb.setChecked(bool(auto_clock.get("enabled", False)))
        self.poll_spin.setValue(int(auto_clock.get("poll_seconds", 30) or 30))
        self.random_spin.setValue(max(0, int(auto_clock.get("random_minutes", 0) or 0)))
        self.pushplus_token_edit.setText(str(pushplus.get("token", "") or ""))

        tasks = auto_clock.get("tasks", [])
        if isinstance(tasks, list):
            for task in tasks:
                if isinstance(task, dict):
                    self._add_task_row(task)

        if self.table.rowCount() == 0:
            self._add_task_row({"time": "08:55", "mode": "in", "image_path": ""})

    def _create_mode_combo(self, mode_value: str):
        combo = QComboBox()
        for label, value in self.MODE_OPTIONS:
            combo.addItem(label, value)
        idx = combo.findData(mode_value)
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        return combo

    def _add_task_row(self, task=None):
        task = task or {}
        row = self.table.rowCount()
        self.table.insertRow(row)

        time_str = str(task.get("time", "08:55")).strip() or "08:55"
        t = QTime.fromString(time_str, "HH:mm")
        if not t.isValid():
            t = QTime(8, 55)

        time_edit = QTimeEdit()
        time_edit.setDisplayFormat("HH:mm")
        time_edit.setTime(t)
        self.table.setCellWidget(row, 0, time_edit)

        mode = str(task.get("mode", "in")).strip().lower()
        self.table.setCellWidget(row, 1, self._create_mode_combo(mode))

        image_path = str(task.get("image_path", "") or "")
        self.table.setItem(row, 2, QTableWidgetItem(image_path))

    def _remove_selected_rows(self):
        rows = sorted({idx.row() for idx in self.table.selectedIndexes()}, reverse=True)
        for row in rows:
            self.table.removeRow(row)

    def _choose_image_for_selected_row(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "提示", "请先选择一行任务")
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择打卡图片",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp)",
        )
        if not file_path:
            return

        self.table.setItem(row, 2, QTableWidgetItem(file_path))

    def _open_config_file(self):
        try:
            os.startfile(os.path.abspath(self.config_path))
        except Exception as exc:
            QMessageBox.warning(self, "提示", f"打开配置文件失败: {exc}")

    def _collect_tasks(self):
        tasks = []
        for row in range(self.table.rowCount()):
            time_edit = self.table.cellWidget(row, 0)
            mode_combo = self.table.cellWidget(row, 1)
            image_item = self.table.item(row, 2)

            if not isinstance(time_edit, QTimeEdit) or not isinstance(mode_combo, QComboBox):
                continue

            task_time = time_edit.time().toString("HH:mm")
            mode = mode_combo.currentData()
            image_path = (image_item.text().strip() if image_item else "").strip()

            if mode in ("photo_in", "photo_out") and not image_path:
                raise RuntimeError(f"第 {row + 1} 行是拍照模式，必须配置图片路径")

            task = {"time": task_time, "mode": mode}
            if image_path:
                task["image_path"] = image_path
            tasks.append(task)

        return tasks

    def _test_pushplus(self):
        token = self.pushplus_token_edit.text().strip()
        if not token:
            QMessageBox.warning(self, "提示", "请先输入 PushPlus token")
            return

        title = "打卡推送测试"
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        content = f"这是一条测试推送，发送时间：{now}"

        self.btn_test_push.setEnabled(False)
        self.btn_test_push.setText("发送中...")

        self.pushplus_worker = PushplusWorker(token=token, title=title, content=content)
        self.pushplus_worker.result_signal.connect(self._on_test_push_result)
        self.pushplus_worker.start()

    def _on_test_push_result(self, success: bool, msg: str):
        self.btn_test_push.setEnabled(True)
        self.btn_test_push.setText("测试推送")

        if success:
            ToastManager.instance().show("PushPlus 测试推送成功", "success")
        else:
            QMessageBox.critical(self, "推送失败", msg)

    def _save(self):
        try:
            tasks = self._collect_tasks()
            settings = self.current_data.setdefault("settings", {})
            auto_clock = settings.setdefault("auto_clock", {})
            auto_clock["enabled"] = self.enabled_cb.isChecked()
            auto_clock["poll_seconds"] = int(self.poll_spin.value())
            auto_clock["random_minutes"] = int(self.random_spin.value())
            auto_clock["tasks"] = tasks

            settings["pushplus"] = {
                "token": self.pushplus_token_edit.text().strip()
            }

            save_json_file(self.config_path, self.current_data)
            ToastManager.instance().show("定时打卡配置已保存", "success")
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "保存失败", str(exc))
