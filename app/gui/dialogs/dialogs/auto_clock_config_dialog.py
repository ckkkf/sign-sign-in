import json
import os
from datetime import datetime

from PySide6.QtCore import QTime, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHeaderView,
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
    QWidget,
)

from app.gui.components.no_wheel_combo import NoWheelComboBox
from app.gui.components.toast import ToastManager
from app.utils.files import read_config, save_json_file
from app.workers.pushplus_worker import PushplusWorker


PHOTO_MODES = {"photo_in", "photo_out"}


class NotificationChannelDialog(QDialog):
    def __init__(self, channel_options, channel=None, parent=None):
        super().__init__(parent)
        self.channel_options = channel_options
        self.result_data = None

        self.setWindowTitle("添加通知" if channel is None else "编辑通知")
        self.setFixedSize(430, 220)
        self.setModal(True)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        if parent is not None:
            self.setStyleSheet(parent.styleSheet())

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        card = QFrame()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel(self.windowTitle())
        title.setObjectName("SectionTitle")
        desc = QLabel("先选择通知方式，再填写对应参数；只有点击添加后才会写入列表。")
        desc.setObjectName("SectionDesc")
        desc.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(desc)

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)

        type_label = QLabel("通知方式")
        type_label.setObjectName("FieldLabel")
        self.type_combo = NoWheelComboBox()
        for label, value in self.channel_options:
            self.type_combo.addItem(label, value)
        grid.addWidget(type_label, 0, 0)
        grid.addWidget(self.type_combo, 0, 1)

        self.value_label = QLabel("PushPlus Token")
        self.value_label.setObjectName("FieldLabel")
        self.value_edit = QLineEdit()
        self.value_edit.setClearButtonEnabled(True)
        grid.addWidget(self.value_label, 1, 0)
        grid.addWidget(self.value_edit, 1, 1)
        layout.addLayout(grid)

        self.value_hint = QLabel()
        self.value_hint.setObjectName("InlineHint")
        self.value_hint.setWordWrap(True)
        layout.addWidget(self.value_hint)

        root.addWidget(card)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch()

        btn_cancel = QPushButton("取消")
        btn_cancel.setObjectName("Outline")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        btn_confirm = QPushButton("添加" if channel is None else "保存")
        btn_confirm.setObjectName("Primary")
        btn_confirm.setDefault(True)
        btn_confirm.clicked.connect(self.accept)
        btn_row.addWidget(btn_confirm)
        root.addLayout(btn_row)

        if channel:
            channel_type = str(channel.get("type", "") or "").strip().lower()
            idx = self.type_combo.findData(channel_type)
            self.type_combo.setCurrentIndex(idx if idx >= 0 else 0)
            self.value_edit.setText(str(channel.get("token", "") or ""))

        self.type_combo.currentIndexChanged.connect(self._update_form)
        self._update_form()

    def _update_form(self):
        channel_type = str(self.type_combo.currentData() or "").strip().lower()
        requires_token = channel_type == "pushplus"
        self.value_label.setText("PushPlus Token" if requires_token else "参数")
        self.value_edit.setEnabled(requires_token)
        self.value_edit.setPlaceholderText(
            "输入 PushPlus Token" if requires_token else "该通知方式无需额外参数"
        )
        self.value_hint.setText(
            "PushPlus 会向微信推送打卡结果。"
            if requires_token
            else "系统托盘会使用软件现有的托盘提醒能力。"
        )
        if not requires_token:
            self.value_edit.clear()

    def accept(self):
        channel_type = str(self.type_combo.currentData() or "").strip().lower()
        token = self.value_edit.text().strip()
        if channel_type == "pushplus" and not token:
            QMessageBox.warning(self, "提示", "PushPlus 通知必须填写 Token")
            return
        self.result_data = {"type": channel_type, "token": token}
        super().accept()


class TaskItemDialog(QDialog):
    def __init__(self, mode_options, task=None, parent=None):
        super().__init__(parent)
        self.mode_options = mode_options
        self.result_data = None

        self.setWindowTitle("添加任务" if task is None else "编辑任务")
        self.setFixedSize(500, 250)
        self.setModal(True)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        if parent is not None:
            self.setStyleSheet(parent.styleSheet())

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        card = QFrame()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel(self.windowTitle())
        title.setObjectName("SectionTitle")
        desc = QLabel("先设置任务参数，再点击添加；拍照模式必须选择图片。")
        desc.setObjectName("SectionDesc")
        desc.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(desc)

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)

        time_label = QLabel("触发时间")
        time_label.setObjectName("FieldLabel")
        self.time_edit = QTimeEdit()
        self.time_edit.setDisplayFormat("HH:mm")
        grid.addWidget(time_label, 0, 0)
        grid.addWidget(self.time_edit, 0, 1)

        mode_label = QLabel("打卡模式")
        mode_label.setObjectName("FieldLabel")
        self.mode_combo = NoWheelComboBox()
        for label, value in self.mode_options:
            self.mode_combo.addItem(label, value)
        grid.addWidget(mode_label, 1, 0)
        grid.addWidget(self.mode_combo, 1, 1)

        self.image_label = QLabel("图片路径")
        self.image_label.setObjectName("FieldLabel")
        self.image_row_widget = QWidget()
        image_row = QHBoxLayout(self.image_row_widget)
        image_row.setContentsMargins(0, 0, 0, 0)
        image_row.setSpacing(8)
        self.image_edit = QLineEdit()
        self.image_edit.setClearButtonEnabled(True)
        self.btn_browse = QPushButton("选择图片")
        self.btn_browse.setObjectName("Accent")
        self.btn_browse.clicked.connect(self._choose_image)
        image_row.addWidget(self.image_edit, 1)
        image_row.addWidget(self.btn_browse)
        grid.addWidget(self.image_label, 2, 0)
        grid.addWidget(self.image_row_widget, 2, 1)
        layout.addLayout(grid)

        self.image_hint = QLabel()
        self.image_hint.setObjectName("InlineHint")
        self.image_hint.setWordWrap(True)
        layout.addWidget(self.image_hint)

        root.addWidget(card)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch()

        btn_cancel = QPushButton("取消")
        btn_cancel.setObjectName("Outline")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        btn_confirm = QPushButton("添加" if task is None else "保存")
        btn_confirm.setObjectName("Primary")
        btn_confirm.setDefault(True)
        btn_confirm.clicked.connect(self.accept)
        btn_row.addWidget(btn_confirm)
        root.addLayout(btn_row)

        if task:
            time_value = QTime.fromString(str(task.get("time", "08:55") or "08:55"), "HH:mm")
            self.time_edit.setTime(time_value if time_value.isValid() else QTime(8, 55))
            mode = str(task.get("mode", "in") or "in").strip().lower()
            idx = self.mode_combo.findData(mode)
            self.mode_combo.setCurrentIndex(idx if idx >= 0 else 0)
            self.image_edit.setText(str(task.get("image_path", "") or ""))
        else:
            self.time_edit.setTime(QTime(8, 55))

        self.mode_combo.currentIndexChanged.connect(self._update_form)
        self._update_form()

    def _choose_image(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择打卡图片",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp)",
        )
        if file_path:
            self.image_edit.setText(file_path)

    def _update_form(self):
        mode = str(self.mode_combo.currentData() or "").strip().lower()
        needs_image = mode in PHOTO_MODES
        self.image_label.setVisible(needs_image)
        self.image_row_widget.setVisible(needs_image)
        self.image_hint.setVisible(needs_image)
        self.image_edit.setEnabled(needs_image)
        self.btn_browse.setEnabled(needs_image)
        self.image_edit.setPlaceholderText("选择拍照用图片")
        self.image_hint.setText("拍照模式必须配置图片路径。")
        self.setFixedHeight(250 if needs_image else 214)
        if not needs_image:
            self.image_edit.clear()

    def accept(self):
        task_time = self.time_edit.time().toString("HH:mm")
        mode = str(self.mode_combo.currentData() or "").strip().lower()
        image_path = self.image_edit.text().strip()
        if mode in PHOTO_MODES and not image_path:
            QMessageBox.warning(self, "提示", "拍照模式必须选择图片")
            return
        task = {"time": task_time, "mode": mode}
        if mode in PHOTO_MODES:
            task["image_path"] = image_path
        self.result_data = task
        super().accept()


class AutoClockConfigDialog(QDialog):
    MODE_OPTIONS = [
        ("普通签到", "in"),
        ("普通签退", "out"),
        ("拍照签到", "photo_in"),
        ("拍照签退", "photo_out"),
    ]
    NOTIFICATION_OPTIONS = [
        ("PushPlus", "pushplus"),
        ("系统托盘", "tray"),
    ]

    def __init__(self, config_path: str, parent=None):
        super().__init__(parent)
        self.config_path = config_path
        self.task_data = []
        self.notification_data = []
        self.pushplus_worker = None

        self.setWindowTitle("定时打卡配置 by thirteen")
        self.setFixedSize(900, 540)
        self.setAttribute(Qt.WA_StyledBackground, True)

        self.original_data = read_config(config_path)
        self.current_data = json.loads(json.dumps(self.original_data))
        self.current_data.setdefault("settings", {})
        self.current_data["settings"].setdefault("auto_clock", {})

        self._setup_style()
        self._setup_ui()
        self._load_current_config()

    def _setup_style(self):
        self.setStyleSheet(
            """
            * {
                font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
            }
            QDialog {
                background: #0F111A;
                color: #D7DBFF;
                font-size: 9pt;
            }
            #SidePanel {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #151928, stop:1 #0E111C);
                border: 1px solid #202538;
                border-radius: 16px;
            }
            #ContentPanel {
                background: #11131D;
                border: 1px solid #1A1D2B;
                border-radius: 16px;
            }
            #HeaderEyebrow {
                color: #7FDBFF;
                font-family: Consolas;
                font-size: 8pt;
                font-weight: 700;
                letter-spacing: 1.2px;
            }
            #HeaderTitle {
                color: #F2F4FF;
                font-size: 18pt;
                font-weight: 700;
            }
            #HeaderState {
                padding: 6px 12px;
                border-radius: 14px;
                background: #101420;
                border: 1px solid #2A3150;
                color: #C9D1F0;
                font-size: 8.5pt;
                font-weight: 700;
            }
            #HeaderState[active="true"] {
                color: #EFFFF5;
                background: rgba(40, 167, 69, 0.14);
                border: 1px solid rgba(40, 167, 69, 0.42);
            }
            #SummaryChip {
                padding: 4px 10px;
                border-radius: 12px;
                background: #101420;
                border: 1px solid #2A3150;
                color: #C8D0F2;
                font-size: 8.2pt;
                font-weight: 700;
            }
            #SummaryChip[active="true"] {
                color: #E7FFF0;
                background: rgba(92, 124, 255, 0.16);
                border: 1px solid rgba(92, 124, 255, 0.42);
            }
            #Card {
                background: #151826;
                border: 1px solid #232841;
                border-radius: 16px;
            }
            #EnablePanel {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #181D2D, stop:1 #121726);
                border: 1px solid #2C3553;
                border-radius: 16px;
            }
            #EnablePanel[active="true"] {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(40,167,69,0.18), stop:1 rgba(18,23,38,0.95));
                border: 1px solid rgba(40, 167, 69, 0.46);
            }
            #EnableCheck {
                color: #F7F9FF;
                font-weight: 700;
                font-size: 11.5pt;
                spacing: 10px;
            }
            QCheckBox#EnableCheck::indicator {
                width: 20px;
                height: 20px;
                border-radius: 6px;
            }
            #NotifyToggle {
                color: #DDE5FF;
                font-size: 9pt;
                font-weight: 700;
            }
            #EnableDesc {
                color: #AAB3D5;
                font-size: 8.5pt;
            }
            #MetaLabel {
                color: #7D86A7;
                font-family: Consolas;
                font-size: 8.6pt;
                font-weight: 700;
            }
            #SectionTitle {
                color: #F3F6FF;
                font-size: 10.5pt;
                font-weight: 700;
            }
            #InlineHint {
                color: #AAB7E0;
                font-size: 8pt;
            }
            #FieldLabel {
                color: #F3F6FF;
                font-size: 8.8pt;
                font-weight: 600;
            }
            QLabel {
                color: #E7ECFF;
                font-size: 9pt;
            }
            QCheckBox {
                color: #F5F7FF;
                font-weight: 600;
                font-size: 9pt;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 4px;
                border: 2px solid #4F5675;
                background: #0F111A;
            }
            QCheckBox::indicator:hover {
                border-color: #7A89FF;
            }
            QCheckBox::indicator:checked {
                background: #5C7CFF;
                border: 2px solid #5C7CFF;
            }
            QSpinBox, QLineEdit, QTimeEdit, QComboBox {
                min-height: 30px;
                background: #0E1320;
                border: 1px solid #2A3150;
                color: #EEF2FF;
                padding: 0 10px;
                border-radius: 9px;
                font-family: Consolas, "Segoe UI", "PingFang SC", "Microsoft YaHei";
                font-size: 9pt;
            }
            QSpinBox:focus, QLineEdit:focus, QTimeEdit:focus, QComboBox:focus {
                border: 1px solid #7A89FF;
                background: #12182A;
            }
            QSpinBox::up-button, QSpinBox::down-button, QTimeEdit::up-button, QTimeEdit::down-button {
                width: 18px;
                background: transparent;
            }
            QComboBox::drop-down {
                border: none;
                width: 26px;
            }
            QComboBox QAbstractItemView {
                background: #151826;
                border: 1px solid #2A3150;
                color: #EEF2FF;
                selection-background-color: #25335C;
                selection-color: #FFFFFF;
                border-radius: 8px;
                outline: none;
            }
            QTableWidget {
                background: #101420;
                alternate-background-color: #121726;
                border: 1px solid #2A3150;
                color: #F0F4FF;
                gridline-color: transparent;
                border-radius: 12px;
                outline: none;
                font-size: 9pt;
            }
            QTableWidget::item {
                padding: 6px 8px;
                border-bottom: 1px solid #1D2336;
            }
            QTableWidget::item:selected {
                background: #21325C;
                color: #FFFFFF;
            }
            QHeaderView::section {
                background: #121726;
                color: #BAC4EA;
                font-weight: 700;
                padding: 7px 10px;
                border: none;
                border-bottom: 1px solid #2A3150;
                font-size: 8.3pt;
            }
            QTableCornerButton::section {
                background: #121726;
                border: none;
                border-bottom: 1px solid #2A3150;
            }
            QPushButton {
                min-height: 30px;
                background: #191B2A;
                color: #D0D5FF;
                border: 1px solid #22263A;
                padding: 0 12px;
                border-radius: 10px;
                font-weight: 600;
                font-size: 8.8pt;
            }
            QPushButton:hover {
                background: #1D2233;
                border-color: #4F6BFF;
                color: #FFFFFF;
            }
            QPushButton:pressed {
                background: #101521;
            }
            QPushButton#Primary {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3D7CFF, stop:1 #5865F2);
                color: #FFFFFF;
                border: 1px solid transparent;
                padding: 0 18px;
            }
            QPushButton#Primary:hover {
                border-color: #7A89FF;
            }
            QPushButton#Danger {
                background: rgba(192, 57, 43, 0.10);
                color: #FFB5B5;
                border: 1px solid rgba(192, 57, 43, 0.35);
            }
            QPushButton#Danger:hover {
                background: rgba(192, 57, 43, 0.18);
                border-color: #E57373;
                color: #FFF0F0;
            }
            QPushButton#RowEditBtn, QPushButton#RowTestBtn, QPushButton#RowDeleteBtn {
                min-height: 22px;
                min-width: 0;
                padding: 0 4px;
                border: none;
                border-radius: 0;
                background: transparent;
                font-size: 8.8pt;
                font-weight: 600;
            }
            QPushButton#RowEditBtn {
                color: #79CBFF;
            }
            QPushButton#RowEditBtn:hover {
                color: #D7F2FF;
            }
            QPushButton#RowTestBtn {
                color: #BFCBFF;
            }
            QPushButton#RowTestBtn:hover {
                color: #E0E6FF;
            }
            QPushButton#RowDeleteBtn {
                color: #FF9F9F;
            }
            QPushButton#RowDeleteBtn:hover {
                color: #FFD4D4;
            }
            QPushButton#AddBtn {
                background: rgba(40, 167, 69, 0.14);
                color: #B9FFD1;
                border: 1px solid rgba(40, 167, 69, 0.36);
            }
            QPushButton#AddBtn:hover {
                background: rgba(40, 167, 69, 0.22);
                border-color: #58D68D;
                color: #EBFFF2;
            }
            QPushButton#Accent {
                background: rgba(92, 124, 255, 0.12);
                color: #B8C1FF;
                border: 1px solid rgba(92, 124, 255, 0.32);
            }
            QPushButton#Accent:hover {
                background: rgba(92, 124, 255, 0.22);
                border-color: rgba(92, 124, 255, 0.46);
                color: #F2F4FF;
            }
            QPushButton#Ghost {
                background: transparent;
                color: #8E97BC;
                border: 1px solid #252D45;
            }
            QPushButton#Ghost:hover {
                color: #EEF2FF;
                border-color: #4C587F;
            }
            QPushButton#Outline {
                background: transparent;
                color: #C4CBE7;
                border: 1px solid #2B3453;
            }
            QPushButton#Outline:hover {
                border-color: #55638F;
                color: #F2F4FF;
            }
            #FooterBar {
                background: #101420;
                border: 1px solid #232841;
                border-radius: 14px;
            }
            """
        )

    def _setup_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        side_panel = QFrame()
        side_panel.setObjectName("SidePanel")
        side_panel.setFixedWidth(284)
        side_layout = QVBoxLayout(side_panel)
        side_layout.setContentsMargins(16, 18, 16, 16)
        side_layout.setSpacing(12)

        eyebrow = QLabel("AUTO CLOCK")
        eyebrow.setObjectName("HeaderEyebrow")
        side_layout.addWidget(eyebrow)

        title = QLabel("定时打卡配置")
        title.setObjectName("HeaderTitle")
        side_layout.addWidget(title)

        self.header_state = QLabel()
        self.header_state.setObjectName("HeaderState")
        self.header_state.setAlignment(Qt.AlignCenter)
        side_layout.addWidget(self.header_state)

        self.enable_panel = QFrame()
        self.enable_panel.setObjectName("EnablePanel")
        enable_layout = QVBoxLayout(self.enable_panel)
        enable_layout.setContentsMargins(14, 14, 14, 14)
        enable_layout.setSpacing(10)

        enable_top = QHBoxLayout()
        enable_top.setSpacing(10)

        enable_text = QVBoxLayout()
        enable_text.setSpacing(4)
        self.enabled_cb = QCheckBox("启用定时打卡")
        self.enabled_cb.setObjectName("EnableCheck")
        enable_text.addWidget(self.enabled_cb)

        enable_desc = QLabel("关闭后不会执行任务。")
        enable_desc.setObjectName("EnableDesc")
        enable_desc.setWordWrap(True)
        enable_text.addWidget(enable_desc)
        enable_top.addLayout(enable_text, 1)

        self.enabled_chip = self._create_summary_chip()
        enable_top.addWidget(self.enabled_chip, 0, Qt.AlignTop)
        enable_layout.addLayout(enable_top)
        side_layout.addWidget(self.enable_panel)

        strategy_card = QFrame()
        strategy_card.setObjectName("Card")
        strategy_layout = QVBoxLayout(strategy_card)
        strategy_layout.setContentsMargins(14, 14, 14, 14)
        strategy_layout.setSpacing(10)

        strategy_title = QLabel("运行策略")
        strategy_title.setObjectName("SectionTitle")
        strategy_layout.addWidget(strategy_title)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)

        poll_label = QLabel("轮询间隔")
        poll_label.setObjectName("FieldLabel")
        self.poll_spin = QSpinBox()
        self.poll_spin.setRange(10, 300)
        self.poll_spin.setSuffix(" 秒")
        self.poll_spin.setValue(30)

        random_label = QLabel("随机延迟")
        random_label.setObjectName("FieldLabel")
        self.random_spin = QSpinBox()
        self.random_spin.setRange(0, 120)
        self.random_spin.setSuffix(" 分钟")
        self.random_spin.setValue(0)

        grid.addWidget(poll_label, 0, 0)
        grid.addWidget(random_label, 0, 1)
        grid.addWidget(self.poll_spin, 1, 0)
        grid.addWidget(self.random_spin, 1, 1)
        strategy_layout.addLayout(grid)

        self.notify_enabled_cb = QCheckBox("启用通知")
        self.notify_enabled_cb.setObjectName("NotifyToggle")
        strategy_layout.addWidget(self.notify_enabled_cb)

        chip_row = QHBoxLayout()
        chip_row.setSpacing(6)
        self.task_chip = self._create_summary_chip()
        self.notify_chip = self._create_summary_chip()
        self.random_chip = self._create_summary_chip()
        chip_row.addWidget(self.task_chip)
        chip_row.addWidget(self.notify_chip)
        chip_row.addWidget(self.random_chip)
        strategy_layout.addLayout(chip_row)
        side_layout.addWidget(strategy_card)
        side_layout.addStretch(1)

        root.addWidget(side_panel)

        content_panel = QFrame()
        content_panel.setObjectName("ContentPanel")
        content_layout = QVBoxLayout(content_panel)
        content_layout.setContentsMargins(14, 14, 14, 14)
        content_layout.setSpacing(10)

        task_card = QFrame()
        task_card.setObjectName("Card")
        task_layout = QVBoxLayout(task_card)
        task_layout.setContentsMargins(14, 14, 14, 14)
        task_layout.setSpacing(8)

        task_header = QHBoxLayout()
        task_title = QLabel("打卡任务")
        task_title.setObjectName("SectionTitle")
        task_header.addWidget(task_title)
        task_header.addStretch()
        self.task_meta = QLabel()
        self.task_meta.setObjectName("MetaLabel")
        task_header.addWidget(self.task_meta)
        task_layout.addLayout(task_header)

        task_actions = QHBoxLayout()
        task_actions.setSpacing(6)
        btn_add_task = QPushButton("添加任务")
        btn_add_task.setObjectName("AddBtn")
        btn_add_task.clicked.connect(self._add_task)
        task_actions.addWidget(btn_add_task)
        task_actions.addStretch()
        task_layout.addLayout(task_actions)

        self.task_table = QTableWidget(0, 3, self)
        self.task_table.setHorizontalHeaderLabels(["时间", "任务内容", "操作"])
        self.task_table.verticalHeader().setVisible(False)
        self.task_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.task_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.task_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.task_table.setAlternatingRowColors(True)
        self.task_table.horizontalHeader().setStretchLastSection(False)
        self.task_table.horizontalHeader().setHighlightSections(False)
        self.task_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.task_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.task_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.task_table.verticalHeader().setDefaultSectionSize(32)
        self.task_table.setColumnWidth(0, 92)
        self.task_table.setColumnWidth(2, 126)
        self.task_table.setShowGrid(False)
        self.task_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.task_table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.task_table.itemDoubleClicked.connect(lambda *_: self._edit_selected_task())
        task_layout.addWidget(self.task_table)

        self.task_hint = QLabel()
        self.task_hint.setObjectName("InlineHint")
        self.task_hint.hide()
        task_layout.addWidget(self.task_hint)
        task_layout.addStretch(1)
        content_layout.addWidget(task_card, 1)

        self.notify_card = QFrame()
        self.notify_card.setObjectName("Card")
        notify_layout = QVBoxLayout(self.notify_card)
        notify_layout.setContentsMargins(14, 14, 14, 14)
        notify_layout.setSpacing(8)

        notify_header = QHBoxLayout()
        notify_title = QLabel("通知方式")
        notify_title.setObjectName("SectionTitle")
        notify_header.addWidget(notify_title)
        notify_header.addStretch()
        self.notify_meta = QLabel()
        self.notify_meta.setObjectName("MetaLabel")
        notify_header.addWidget(self.notify_meta)
        notify_layout.addLayout(notify_header)

        notify_actions = QHBoxLayout()
        notify_actions.setSpacing(6)
        btn_add_notify = QPushButton("添加通知")
        btn_add_notify.setObjectName("AddBtn")
        btn_add_notify.clicked.connect(self._add_notification)
        notify_actions.addWidget(btn_add_notify)

        self.btn_test_notify = QPushButton("测试所选")
        self.btn_test_notify.setObjectName("Accent")
        self.btn_test_notify.clicked.connect(self._test_selected_notification)
        notify_actions.addWidget(self.btn_test_notify)
        notify_actions.addStretch()
        notify_layout.addLayout(notify_actions)

        self.notification_table = QTableWidget(0, 2, self)
        self.notification_table.setHorizontalHeaderLabels(["通知方式", "操作"])
        self.notification_table.verticalHeader().setVisible(False)
        self.notification_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.notification_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.notification_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.notification_table.setAlternatingRowColors(True)
        self.notification_table.horizontalHeader().setStretchLastSection(False)
        self.notification_table.horizontalHeader().setHighlightSections(False)
        self.notification_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.notification_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.notification_table.verticalHeader().setDefaultSectionSize(32)
        self.notification_table.setColumnWidth(1, 188)
        self.notification_table.setShowGrid(False)
        self.notification_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.notification_table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.notification_table.itemDoubleClicked.connect(lambda *_: self._edit_selected_notification())
        notify_layout.addWidget(self.notification_table)

        self.notify_hint = QLabel()
        self.notify_hint.setObjectName("InlineHint")
        self.notify_hint.hide()
        notify_layout.addWidget(self.notify_hint)
        content_layout.addWidget(self.notify_card)

        footer_bar = QFrame()
        footer_bar.setObjectName("FooterBar")
        footer = QHBoxLayout(footer_bar)
        footer.setContentsMargins(10, 8, 10, 8)
        footer.setSpacing(6)

        btn_open = QPushButton("打开 config.json")
        btn_open.setObjectName("Ghost")
        btn_open.clicked.connect(self._open_config_file)
        footer.addWidget(btn_open)
        footer.addStretch()

        btn_cancel = QPushButton("取消")
        btn_cancel.setObjectName("Outline")
        btn_cancel.clicked.connect(self.reject)
        footer.addWidget(btn_cancel)

        btn_save = QPushButton("保存配置")
        btn_save.setObjectName("Primary")
        btn_save.setDefault(True)
        btn_save.clicked.connect(self._save)
        footer.addWidget(btn_save)
        content_layout.addWidget(footer_bar)

        root.addWidget(content_panel, 1)

        self._apply_styled_background(
            self,
            side_panel,
            content_panel,
            self.enable_panel,
            strategy_card,
            task_card,
            self.notify_card,
            footer_bar,
        )

        self.enabled_cb.stateChanged.connect(self._update_overview)
        self.notify_enabled_cb.stateChanged.connect(self._update_overview)
        self.poll_spin.valueChanged.connect(self._update_overview)
        self.random_spin.valueChanged.connect(self._update_overview)

    def _create_summary_chip(self):
        label = QLabel()
        label.setObjectName("SummaryChip")
        label.setAlignment(Qt.AlignCenter)
        return label

    def _set_summary_chip(self, label: QLabel, text: str, active: bool = False):
        label.setText(text)
        label.setProperty("active", active)
        self.style().unpolish(label)
        self.style().polish(label)
        label.update()

    @staticmethod
    def _make_table_item(text: str, tooltip: str = ""):
        item = QTableWidgetItem(text)
        item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        if tooltip:
            item.setToolTip(tooltip)
        return item

    def _fit_table_height(self, table: QTableWidget, min_rows: int = 1, max_rows: int = 4):
        visible_rows = max(min_rows, min(table.rowCount(), max_rows))
        header_height = table.horizontalHeader().height() or 32
        row_height = table.verticalHeader().defaultSectionSize()
        frame_height = table.frameWidth() * 2 + 10
        table.setFixedHeight(header_height + row_height * visible_rows + frame_height)

    def _apply_styled_background(self, *widgets):
        for widget in widgets:
            if widget is not None:
                widget.setAttribute(Qt.WA_StyledBackground, True)

    def _mode_label(self, mode: str) -> str:
        for label, value in self.MODE_OPTIONS:
            if value == mode:
                return label
        return mode or "-"

    def _notification_label(self, channel_type: str) -> str:
        for label, value in self.NOTIFICATION_OPTIONS:
            if value == channel_type:
                return label
        return channel_type or "-"

    @staticmethod
    def _mask_token(token: str) -> str:
        if len(token) <= 10:
            return token
        return f"{token[:6]}...{token[-4:]}"

    def _normalize_notification_channels(self, settings: dict):
        channels = []
        seen = set()
        allowed_types = {value for _, value in self.NOTIFICATION_OPTIONS}

        if not isinstance(settings, dict):
            return channels

        raw_channels = settings.get("notifications", [])
        if isinstance(raw_channels, list):
            for channel in raw_channels:
                if not isinstance(channel, dict):
                    continue
                channel_type = str(channel.get("type", "") or "").strip().lower()
                token = str(channel.get("token", "") or "").strip()
                if channel_type not in allowed_types or channel_type in seen:
                    continue
                if channel_type == "pushplus" and not token:
                    continue
                seen.add(channel_type)
                channels.append({"type": channel_type, "token": token})

        pushplus = settings.get("pushplus", {})
        if isinstance(pushplus, dict):
            legacy_token = str(pushplus.get("token", "") or "").strip()
            if legacy_token and "pushplus" not in seen:
                channels.append({"type": "pushplus", "token": legacy_token})

        return channels

    def _refresh_notification_table(self):
        self.notification_table.setRowCount(0)
        for channel in self.notification_data:
            row = self.notification_table.rowCount()
            self.notification_table.insertRow(row)

            channel_type = str(channel.get("type", "") or "").strip().lower()
            token = str(channel.get("token", "") or "").strip()
            if channel_type == "pushplus":
                text = f"{self._notification_label(channel_type)} · {self._mask_token(token)}"
                tip = token
            else:
                text = "系统托盘 · 应用内提醒"
                tip = "执行完成后显示系统托盘通知"

            self.notification_table.setItem(row, 0, self._make_table_item(text, tip))
            self.notification_table.setCellWidget(
                row,
                1,
                self._build_action_cell(
                    [
                        ("测试", "RowTestBtn", lambda _=False, r=row: self._test_notification_at(r)),
                        ("编辑", "RowEditBtn", lambda _=False, r=row: self._edit_notification_at(r)),
                        ("删除", "RowDeleteBtn", lambda _=False, r=row: self._remove_notification_at(r)),
                    ]
                ),
            )
        self._fit_table_height(self.notification_table, min_rows=2, max_rows=3)

    def _refresh_task_table(self):
        self.task_table.setRowCount(0)
        for task in self.task_data:
            row = self.task_table.rowCount()
            self.task_table.insertRow(row)

            mode = str(task.get("mode", "") or "").strip().lower()
            image_path = str(task.get("image_path", "") or "").strip()
            if mode in PHOTO_MODES:
                image_name = os.path.basename(image_path) if image_path else "未设置图片"
                task_text = f"{self._mode_label(mode)} · {image_name}"
                task_tip = image_path or "拍照模式必须配置图片"
            else:
                task_text = self._mode_label(mode)
                task_tip = "普通签到和普通签退不需要图片"

            self.task_table.setItem(row, 0, self._make_table_item(str(task.get("time", "") or "-")))
            self.task_table.setItem(row, 1, self._make_table_item(task_text, task_tip))
            self.task_table.setCellWidget(
                row,
                2,
                self._build_action_cell(
                    [
                        ("编辑", "RowEditBtn", lambda _=False, r=row: self._edit_task_at(r)),
                        ("删除", "RowDeleteBtn", lambda _=False, r=row: self._remove_task_at(r)),
                    ]
                ),
            )
        self._fit_table_height(self.task_table, min_rows=2, max_rows=4)

    def _build_action_cell(self, actions):
        wrapper = QWidget()
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignCenter)

        for text, object_name, handler in actions:
            btn = QPushButton(text)
            btn.setObjectName(object_name)
            btn.setFlat(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(handler)
            layout.addWidget(btn)

        return wrapper

    def _selected_rows(self, table: QTableWidget):
        return sorted({index.row() for index in table.selectedIndexes()})

    def _require_single_row(self, table: QTableWidget, empty_message: str):
        rows = self._selected_rows(table)
        if not rows:
            QMessageBox.warning(self, "提示", empty_message)
            return None
        if len(rows) > 1:
            QMessageBox.warning(self, "提示", "请只选择一条记录")
            return None
        return rows[0]

    def _select_row(self, table: QTableWidget, row: int):
        if 0 <= row < table.rowCount():
            table.clearSelection()
            table.selectRow(row)

    def _collect_tasks(self):
        tasks = []
        for index, task in enumerate(self.task_data, start=1):
            time_text = str(task.get("time", "") or "").strip()
            mode = str(task.get("mode", "") or "").strip().lower()
            image_path = str(task.get("image_path", "") or "").strip()
            if not time_text or not mode:
                raise RuntimeError(f"第 {index} 条任务配置不完整")
            if mode in PHOTO_MODES and not image_path:
                raise RuntimeError(f"第 {index} 条任务是拍照模式，必须配置图片")
            item = {"time": time_text, "mode": mode}
            if mode in PHOTO_MODES:
                item["image_path"] = image_path
            tasks.append(item)
        return tasks

    def _collect_notifications(self):
        channels = []
        seen = set()
        allowed_types = {value for _, value in self.NOTIFICATION_OPTIONS}
        for index, channel in enumerate(self.notification_data, start=1):
            channel_type = str(channel.get("type", "") or "").strip().lower()
            token = str(channel.get("token", "") or "").strip()
            if channel_type not in allowed_types:
                raise RuntimeError(f"第 {index} 条通知方式无效")
            if channel_type in seen:
                raise RuntimeError(f"通知方式 {channel_type} 只能配置一条")
            if channel_type == "pushplus" and not token:
                raise RuntimeError(f"第 {index} 条 PushPlus 通知未填写 Token")
            seen.add(channel_type)
            channels.append({"type": channel_type, "token": token})
        return channels

    def _load_current_config(self):
        settings = self.current_data.get("settings", {})
        auto_clock = settings.get("auto_clock", {})

        self.enabled_cb.setChecked(bool(auto_clock.get("enabled", False)))
        self.poll_spin.setValue(int(auto_clock.get("poll_seconds", 30) or 30))
        self.random_spin.setValue(max(0, int(auto_clock.get("random_minutes", 0) or 0)))

        self.notification_data = self._normalize_notification_channels(settings)
        self.notify_enabled_cb.setChecked(bool(settings.get("notifications_enabled", False)))

        tasks = auto_clock.get("tasks", [])
        if isinstance(tasks, list):
            for task in tasks:
                if not isinstance(task, dict):
                    continue
                time_text = str(task.get("time", "") or "").strip()
                mode = str(task.get("mode", "") or "").strip().lower()
                if not time_text or not mode:
                    continue
                item = {"time": time_text, "mode": mode}
                if mode in PHOTO_MODES:
                    image_path = str(task.get("image_path", "") or "").strip()
                    if image_path:
                        item["image_path"] = image_path
                self.task_data.append(item)

        if not self.task_data:
            self.task_data = [
                {"time": "08:55", "mode": "in"},
                {"time": "18:05", "mode": "out"},
            ]

        self._refresh_notification_table()
        self._refresh_task_table()
        self._update_overview()

    def _update_overview(self):
        task_count = len(self.task_data)
        notify_count = len(self.notification_data)
        photo_count = sum(1 for task in self.task_data if task.get("mode") in PHOTO_MODES)
        enabled = self.enabled_cb.isChecked()
        notify_enabled = self.notify_enabled_cb.isChecked()
        random_minutes = self.random_spin.value()

        self._set_summary_chip(self.enabled_chip, "运行中" if enabled else "已关闭", enabled)
        self._set_summary_chip(self.task_chip, f"任务 {task_count:02d}", task_count > 0)
        self._set_summary_chip(
            self.notify_chip,
            f"通知 {notify_count:02d}" if notify_enabled else "通知 关闭",
            notify_enabled and notify_count > 0,
        )
        self._set_summary_chip(
            self.random_chip,
            "随机 关闭" if random_minutes == 0 else f"随机 ±{random_minutes}m",
            random_minutes > 0,
        )

        notify_state = f"通知{notify_count}" if notify_enabled else "通知关"
        self.header_state.setText(f"{'已启用' if enabled else '未启用'} · {task_count}任务 · {notify_state}")
        self.header_state.setProperty("active", enabled)
        self.style().unpolish(self.header_state)
        self.style().polish(self.header_state)
        self.header_state.update()

        self.enable_panel.setProperty("active", enabled)
        self.style().unpolish(self.enable_panel)
        self.style().polish(self.enable_panel)
        self.enable_panel.update()

        self.task_meta.setText(f"共 {task_count} 项")
        self.notify_meta.setText(f"共 {notify_count} 项")
        self.btn_test_notify.setEnabled(notify_enabled and notify_count > 0)
        self.notify_card.setVisible(notify_enabled)

        if task_count == 0:
            self.task_hint.setText("当前没有任务；保存后不会触发自动打卡。")
        elif photo_count > 0:
            self.task_hint.setText(f"当前有 {photo_count} 条拍照任务，编辑时注意核对图片路径。")
        else:
            self.task_hint.setText("双击任务可直接编辑，列表里只展示时间和任务摘要。")

        if notify_count == 0:
            self.notify_hint.setText("当前没有通知方式；需要时点击“添加通知”后再配置。")
        elif notify_count == 1:
            self.notify_hint.setText("已配置 1 种通知方式；测试按钮只会发送到当前选中项。")
        else:
            self.notify_hint.setText(f"已配置 {notify_count} 种通知方式；保存后会按方式分别通知。")

    def _open_config_file(self):
        try:
            os.startfile(os.path.abspath(self.config_path))
        except Exception as exc:
            QMessageBox.warning(self, "提示", f"打开配置文件失败: {exc}")

    def _add_notification(self):
        dialog = NotificationChannelDialog(self.NOTIFICATION_OPTIONS, parent=self)
        if dialog.exec() != QDialog.Accepted or not dialog.result_data:
            return
        channel = dialog.result_data
        if any(item.get("type") == channel.get("type") for item in self.notification_data):
            QMessageBox.warning(self, "提示", "同一种通知方式只能添加一条")
            return
        self.notification_data.append(channel)
        self._refresh_notification_table()
        self._select_row(self.notification_table, len(self.notification_data) - 1)
        self._update_overview()

    def _edit_notification_at(self, row: int):
        self._select_row(self.notification_table, row)
        self._edit_selected_notification()

    def _remove_notification_at(self, row: int):
        if 0 <= row < len(self.notification_data):
            self.notification_data.pop(row)
            self._refresh_notification_table()
            self._update_overview()

    def _test_notification_at(self, row: int):
        self._select_row(self.notification_table, row)
        self._test_selected_notification()

    def _edit_selected_notification(self):
        row = self._require_single_row(self.notification_table, "请先选择一条通知方式")
        if row is None:
            return
        dialog = NotificationChannelDialog(
            self.NOTIFICATION_OPTIONS,
            channel=self.notification_data[row],
            parent=self,
        )
        if dialog.exec() != QDialog.Accepted or not dialog.result_data:
            return
        channel = dialog.result_data
        for index, item in enumerate(self.notification_data):
            if index != row and item.get("type") == channel.get("type"):
                QMessageBox.warning(self, "提示", "同一种通知方式只能保留一条")
                return
        self.notification_data[row] = channel
        self._refresh_notification_table()
        self._select_row(self.notification_table, row)
        self._update_overview()

    def _remove_selected_notifications(self):
        rows = self._selected_rows(self.notification_table)
        if not rows:
            QMessageBox.warning(self, "提示", "请先选择至少一条通知方式")
            return
        for row in reversed(rows):
            self.notification_data.pop(row)
        self._refresh_notification_table()
        self._update_overview()

    def _test_selected_notification(self):
        row = self._require_single_row(self.notification_table, "请先选择一条通知方式")
        if row is None:
            return

        channel = self.notification_data[row]
        channel_type = str(channel.get("type", "") or "").strip().lower()
        token = str(channel.get("token", "") or "").strip()

        if channel_type == "tray":
            if self.parent() and hasattr(self.parent(), "_show_tray_message"):
                self.parent()._show_tray_message("通知方式测试", "这是一条系统托盘测试消息。", True)
            else:
                ToastManager.instance().show("这是一条系统托盘测试消息。", "success")
            return

        if channel_type != "pushplus" or not token:
            QMessageBox.warning(self, "提示", "当前通知方式暂不支持测试")
            return

        title = "打卡推送测试"
        content = f"这是一条测试推送，发送时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        self.btn_test_notify.setEnabled(False)
        self.btn_test_notify.setText("发送中...")
        self.pushplus_worker = PushplusWorker(token=token, title=title, content=content)
        self.pushplus_worker.result_signal.connect(self._on_test_push_result)
        self.pushplus_worker.start()

    def _on_test_push_result(self, success: bool, msg: str):
        self.btn_test_notify.setEnabled(True)
        self.btn_test_notify.setText("测试所选")
        if success:
            ToastManager.instance().show("PushPlus 测试推送成功", "success")
        else:
            QMessageBox.critical(self, "推送失败", msg)

    def _add_task(self):
        dialog = TaskItemDialog(self.MODE_OPTIONS, parent=self)
        if dialog.exec() != QDialog.Accepted or not dialog.result_data:
            return
        self.task_data.append(dialog.result_data)
        self._refresh_task_table()
        self._select_row(self.task_table, len(self.task_data) - 1)
        self._update_overview()

    def _edit_task_at(self, row: int):
        self._select_row(self.task_table, row)
        self._edit_selected_task()

    def _remove_task_at(self, row: int):
        if 0 <= row < len(self.task_data):
            self.task_data.pop(row)
            self._refresh_task_table()
            self._update_overview()

    def _edit_selected_task(self):
        row = self._require_single_row(self.task_table, "请先选择一条任务")
        if row is None:
            return
        dialog = TaskItemDialog(self.MODE_OPTIONS, task=self.task_data[row], parent=self)
        if dialog.exec() != QDialog.Accepted or not dialog.result_data:
            return
        self.task_data[row] = dialog.result_data
        self._refresh_task_table()
        self._select_row(self.task_table, row)
        self._update_overview()

    def _remove_selected_tasks(self):
        rows = self._selected_rows(self.task_table)
        if not rows:
            QMessageBox.warning(self, "提示", "请先选择至少一条任务")
            return
        for row in reversed(rows):
            self.task_data.pop(row)
        self._refresh_task_table()
        self._update_overview()

    def _save(self):
        try:
            tasks = self._collect_tasks()
            notifications = self._collect_notifications()

            settings = self.current_data.setdefault("settings", {})
            auto_clock = settings.setdefault("auto_clock", {})
            auto_clock["enabled"] = self.enabled_cb.isChecked()
            auto_clock["poll_seconds"] = int(self.poll_spin.value())
            auto_clock["random_minutes"] = int(self.random_spin.value())
            auto_clock["tasks"] = tasks

            settings["notifications_enabled"] = self.notify_enabled_cb.isChecked()
            settings["notifications"] = notifications
            settings["pushplus"] = {
                "token": next(
                    (
                        channel["token"]
                        for channel in notifications
                        if channel.get("type") == "pushplus" and channel.get("token")
                    ),
                    "",
                )
            }

            save_json_file(self.config_path, self.current_data)
            ToastManager.instance().show("定时打卡配置已保存", "success")
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "保存失败", str(exc))
