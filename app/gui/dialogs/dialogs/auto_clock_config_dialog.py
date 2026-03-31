import json
import os
from datetime import datetime

from PySide6.QtCore import QTime
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
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
        self.setWindowTitle("定时打卡配置 - 现代化试图")
        self.resize(760, 640)

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
            * {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
            }
            QDialog {
                background-color: #141827;
                color: #E2E8F0;
                font-size: 9pt;
            }
            /* 卡片背景 */
            #Card {
                background-color: #1E253C;
                border-radius: 8px;
                border: 1px solid #2D3748;
            }
            /* 标题样式 */
            #HeaderTitle {
                font-size: 14pt;
                color: #FFFFFF;
                font-weight: 600;
                letter-spacing: -0.3px;
            }
            #SubTitle {
                font-size: 9pt;
                color: #94A3B8;
                margin-bottom: 4px;
            }
            #SectionTitle {
                color: #FFFFFF;
                font-weight: 600;
                font-size: 10pt;
                padding-bottom: 2px;
            }
            /* 普通文本标签 */
            QLabel {
                color: #CBD5E1;
                font-size: 9pt;
            }
            /* 复选框增强 */
            QCheckBox {
                color: #E2E8F0;
                font-weight: 500;
                font-size: 9pt;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 4px;
                border: 1px solid #3B4252;
                background: #141827;
            }
            QCheckBox::indicator:hover {
                border-color: #6366F1;
            }
            QCheckBox::indicator:checked {
                background: #6366F1;
                border: 1px solid #6366F1;
            }
            
            /* 输入框、多选框、数字框 */
            QSpinBox, QLineEdit, QTimeEdit, QComboBox {
                background: #1A2035;
                border: 1px solid #2D3748;
                color: #E2E8F0;
                padding: 5px 10px;
                border-radius: 6px;
                font-family: Consolas, -apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei";
                font-size: 9pt;
            }
            QSpinBox:focus, QLineEdit:focus, QTimeEdit:focus, QComboBox:focus {
                border: 1px solid #6366F1;
                background: #1E253C;
            }
            QSpinBox::up-button, QSpinBox::down-button, QTimeEdit::up-button, QTimeEdit::down-button {
                width: 16px;
                background: transparent;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QComboBox::down-arrow {
                width: 10px;
                height: 10px;
            }
            QComboBox QAbstractItemView {
                background: #1E253C;
                border: 1px solid #2D3748;
                color: #E2E8F0;
                selection-background-color: #312E81;
                selection-color: #FFFFFF;
                border-radius: 6px;
                outline: none;
                padding: 4px;
            }

            /* 表格增强 */
            QTableWidget {
                background: #1A2035;
                border: 1px solid #2D3748;
                color: #E2E8F0;
                gridline-color: #2D3748;
                border-radius: 6px;
                outline: none;
                font-size: 9pt;
            }
            QTableWidget::item {
                padding: 6px;
                border-bottom: 1px solid #2D3748;
            }
            QTableWidget::item:selected {
                background: #312E81;
                color: #FFFFFF;
            }
            QHeaderView::section {
                background: #1E253C;
                color: #94A3B8;
                font-weight: 500;
                padding: 8px 10px;
                border: none;
                border-bottom: 1px solid #2D3748;
                border-right: 1px solid #2D3748;
                font-size: 8.5pt;
            }
            QHeaderView::section:last {
                border-right: none;
            }

            /* 按钮统一样式 */
            QPushButton {
                background: #1E253C;
                color: #E2E8F0;
                border: 1px solid #2D3748;
                padding: 6px 14px;
                border-radius: 6px;
                font-weight: 500;
                font-size: 9pt;
            }
            QPushButton:hover {
                background: #2D3748;
                border-color: #4A5568;
                color: #FFFFFF;
            }
            QPushButton:pressed {
                background: #1A2035;
            }
            
            /* 特殊按钮状态 */
            QPushButton#Primary {
                background: #6366F1;
                color: #FFFFFF;
                border: 1px solid #6366F1;
                font-weight: 600;
                border-radius: 6px;
                padding: 6px 20px;
            }
            QPushButton#Primary:hover {
                background: #4F46E5;
                border-color: #4F46E5;
            }
            QPushButton#Primary:pressed {
                background: #4338CA;
            }
            QPushButton#Danger {
                background: transparent;
                color: #F87171;
                border: 1px solid #7F1D1D;
            }
            QPushButton#Danger:hover {
                background: #4A1C1C;
                border-color: #DC2626;
                color: #FECACA;
            }
            QPushButton#AddBtn {
                background: transparent;
                color: #10B981;
                border: 1px solid #064E3B;
            }
            QPushButton#AddBtn:hover {
                background: #023628;
                border-color: #059669;
                color: #A7F3D0;
            }
            """
        )

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(16)

        # Header area
        header_layout = QVBoxLayout()
        header_layout.setSpacing(4)
        title = QLabel("定时打卡配置")
        title.setObjectName("HeaderTitle")
        subtitle = QLabel("每天只需固定时刻设置，无需手动操作即可签到。")
        subtitle.setObjectName("SubTitle")
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        root.addLayout(header_layout)

        # Settings Card
        settings_card = QFrame()
        settings_card.setObjectName("Card")
        settings_layout = QVBoxLayout(settings_card)
        settings_layout.setContentsMargins(16, 16, 16, 16)
        settings_layout.setSpacing(12)
        
        lbl_settings = QLabel("基本配置")
        lbl_settings.setObjectName("SectionTitle")
        settings_layout.addWidget(lbl_settings)

        top = QGridLayout()
        top.setHorizontalSpacing(10)
        top.setVerticalSpacing(8)

        self.enabled_cb = QCheckBox("启用定时打卡功能")
        self.poll_spin = QSpinBox()
        self.poll_spin.setRange(10, 300)
        self.poll_spin.setSuffix(" 秒")
        self.poll_spin.setValue(30)
        self.random_spin = QSpinBox()
        self.random_spin.setRange(0, 120)
        self.random_spin.setSuffix(" 分钟")
        self.random_spin.setValue(0)

        # Row 0
        top.addWidget(self.enabled_cb, 0, 0, 1, 4)
        
        # Row 1
        top.addWidget(QLabel("轮询间隔(秒):"), 1, 0)
        top.addWidget(self.poll_spin, 1, 1)
        top.addWidget(QLabel("随机延迟(分钟):"), 1, 2)
        top.addWidget(self.random_spin, 1, 3)

        settings_layout.addLayout(top)
        root.addWidget(settings_card)

        # Push Notification Card
        push_card = QFrame()
        push_card.setObjectName("Card")
        push_layout = QVBoxLayout(push_card)
        push_layout.setContentsMargins(16, 16, 16, 16)
        push_layout.setSpacing(12)

        lbl_push = QLabel("通知配置")
        lbl_push.setObjectName("SectionTitle")
        push_layout.addWidget(lbl_push)

        push_grid = QGridLayout()
        push_grid.setHorizontalSpacing(10)
        push_grid.setVerticalSpacing(8)

        self.pushplus_token_edit = QLineEdit()
        self.pushplus_token_edit.setPlaceholderText("PushPlus Token (用于结果推送，可为空)")
        
        push_grid.addWidget(QLabel("推送 Token:"), 0, 0)
        push_grid.addWidget(self.pushplus_token_edit, 0, 1, 1, 1)
        
        self.btn_test_push = QPushButton("测试推送")
        self.btn_test_push.setFixedWidth(100)
        self.btn_test_push.clicked.connect(self._test_pushplus)
        push_grid.addWidget(self.btn_test_push, 0, 2)
        
        push_layout.addLayout(push_grid)
        root.addWidget(push_card)

        # Task Table Card
        task_card = QFrame()
        task_card.setObjectName("Card")
        task_layout = QVBoxLayout(task_card)
        task_layout.setContentsMargins(16, 16, 16, 16)
        task_layout.setSpacing(12)

        task_header = QHBoxLayout()
        lbl_tasks = QLabel("打卡任务列表")
        lbl_tasks.setObjectName("SectionTitle")
        task_header.addWidget(lbl_tasks)
        task_header.addStretch()

        btn_add = QPushButton("新增任务")
        btn_add.setObjectName("AddBtn")
        btn_add.clicked.connect(lambda: self._add_task_row())
        
        btn_remove = QPushButton("删除所选")
        btn_remove.setObjectName("Danger")
        btn_remove.clicked.connect(self._remove_selected_rows)

        btn_pick = QPushButton("选择图片")
        btn_pick.clicked.connect(self._choose_image_for_selected_row)
        btn_pick.setToolTip("为所选拍照模式任务选择图片")

        task_header.addWidget(btn_add)
        task_header.addWidget(btn_remove)
        task_header.addWidget(btn_pick)
        task_layout.addLayout(task_header)

        self.table = QTableWidget(0, 3, self)
        self.table.setHorizontalHeaderLabels(["触发时间", "打卡模式", "图片路径(拍照模式必填)"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setDefaultSectionSize(36)
        self.table.setColumnWidth(0, 140)
        self.table.setColumnWidth(1, 140)
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(self.table.focusPolicy()) # To remove focus rect completely we can do CSS outline:none
        task_layout.addWidget(self.table)
        
        root.addWidget(task_card)

        # Bottom Buttons
        bottom = QHBoxLayout()
        btn_open = QPushButton("查看 config.json")
        btn_open.clicked.connect(self._open_config_file)
        bottom.addWidget(btn_open)
        bottom.addStretch()

        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        bottom.addWidget(btn_cancel)

        btn_save = QPushButton("保存配置")
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
            self._add_task_row({"time": "18:05", "mode": "out", "image_path": ""})

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
