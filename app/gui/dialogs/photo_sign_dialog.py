import os
import random

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QHBoxLayout,
    QFileDialog,
    QMessageBox,
    QDialogButtonBox,
)

from app.gui.components.toast import ToastManager
from app.gui.dialogs.image_manager_dialog import ImageManagerDialog
from app.utils.files import list_images, import_image


class PhotoSignDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("拍照签到")
        self.resize(640, 520)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.selected_image = None
        self._setup_ui()
        self._load_images()
        self._select_random_image()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        self.preview = QLabel("加载中...")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setStyleSheet("border: 1px dashed #555; min-height: 220px; color: #BBB;")
        layout.addWidget(self.preview)

        self.list_widget = QListWidget()
        self.list_widget.setIconSize(QSize(96, 96))
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.list_widget, 1)

        btn_row = QHBoxLayout()
        btn_random = QPushButton("随机一张")
        btn_random.clicked.connect(self._select_random_image)
        btn_import = QPushButton("从本地导入")
        btn_import.clicked.connect(self._import_image)
        btn_manager = QPushButton("打开图片管理")
        btn_manager.clicked.connect(self._open_manager)
        btn_server = QPushButton("从服务器获取（预留）")
        btn_server.clicked.connect(lambda: QMessageBox.information(self, "提示", "该功能预留，敬请期待！"))

        for btn in (btn_random, btn_import, btn_manager, btn_server):
            btn_row.addWidget(btn)
        layout.addLayout(btn_row)

        self.info_label = QLabel("请确认用于本次签到的图片。")
        self.info_label.setStyleSheet("color: #999;")
        layout.addWidget(self.info_label)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_images(self):
        self.list_widget.clear()
        self._images = list_images()
        for path in self._images:
            item = QListWidgetItem(os.path.basename(path))
            pixmap = QPixmap(path).scaled(96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            item.setIcon(QIcon(pixmap))
            item.setData(Qt.UserRole, path)
            self.list_widget.addItem(item)
        if not self._images:
            self.preview.setText("图片目录为空，请先导入图片。")
            self.selected_image = None

    def _set_preview(self, path: str):
        if not path:
            self.preview.setText("请选择图片")
            self.preview.setPixmap(QPixmap())
            return
        pixmap = QPixmap(path)
        if pixmap.isNull():
            self.preview.setText("无法加载图片")
            return
        scaled = pixmap.scaled(360, 240, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.preview.setPixmap(scaled)
        self.selected_image = path

    def _on_item_clicked(self, item: QListWidgetItem):
        self._set_preview(item.data(Qt.UserRole))

    def _select_random_image(self):
        if not getattr(self, "_images", None):
            self.preview.setText("图片目录为空，请先导入图片。")
            self.selected_image = None
            return
        path = random.choice(self._images)
        self.selected_image = path
        self._set_preview(path)
        items = self.list_widget.findItems(os.path.basename(path), Qt.MatchExactly)
        if items:
            self.list_widget.setCurrentItem(items[0])

    def _import_image(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择图片", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp)")
        if not file_path:
            return
        try:
            new_path = import_image(file_path)
            ToastManager.instance().show("图片导入成功", "success")
            self._load_images()
            self._set_preview(new_path)
        except Exception as exc:
            QMessageBox.critical(self, "导入失败", str(exc))

    def _open_manager(self):
        dialog = ImageManagerDialog(self)
        dialog.exec()
        self._load_images()
        if self._images:
            self._select_random_image()

    def _accept(self):
        if not self.selected_image:
            QMessageBox.warning(self, "提示", "请选择一张用于签到的图片")
            return
        self.accept()

