import os

from PySide6.QtCore import Qt, QSize, QUrl
from PySide6.QtGui import QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QHBoxLayout,
    QPushButton,
    QFileDialog,
    QWidget,
    QSpacerItem,
    QSizePolicy,
    QMessageBox,
)

from app.config.common import IMAGE_DIR
from app.gui.components.toast import ToastManager
from app.utils.files import list_images, import_image, delete_image


class ImageManagerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("图片管理")
        self.resize(720, 480)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self._setup_style()
        self._setup_ui()
        self._load_images()

    def _setup_style(self):
        self.setStyleSheet("""
            QDialog {
                background: #101014;
                color: #EAEAEA;
            }
            QListWidget {
                background: #16161C;
                border: 1px solid #23232A;
                border-radius: 12px;
                padding: 12px;
            }
            QListWidget::item {
                padding: 12px 6px;
                margin: 4px;
                border-radius: 10px;
            }
            QListWidget::item:selected {
                background: #3F72FF;
                color: white;
            }
            QLabel {
                color: #9FA4B8;
            }
            QPushButton {
                background: #1F1F27;
                border: 1px solid #2C2C36;
                border-radius: 18px;
                padding: 8px 18px;
                color: #E0E0E6;
                font-weight: bold;
            }
            QPushButton:hover {
                border-color: #5C6BFF;
                color: white;
            }
            #PrimaryBtn {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #5568FE, stop:1 #8E4BFF);
                border: none;
            }
            #PrimaryBtn:hover {
                opacity: 0.9;
            }
        """)

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        self.list_widget = QListWidget()
        self.list_widget.setViewMode(QListWidget.IconMode)
        self.list_widget.setIconSize(QSize(120, 120))
        self.list_widget.setResizeMode(QListWidget.Adjust)
        self.list_widget.setSpacing(10)
        self.list_widget.setSelectionMode(QListWidget.SingleSelection)
        self.list_widget.itemSelectionChanged.connect(self._update_preview)
        layout.addWidget(self.list_widget, 1)

        preview_box = QWidget()
        preview_layout = QVBoxLayout(preview_box)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        self.preview_label = QLabel("请选择一张图片预览")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("color: #CCCCCC; border: 1px dashed #444; min-height: 160px;")
        preview_layout.addWidget(self.preview_label)
        layout.addWidget(preview_box)

        btn_row = QHBoxLayout()
        btn_import = QPushButton("导入图片")
        btn_import.clicked.connect(self._import_image)
        btn_delete = QPushButton("删除图片")
        btn_delete.clicked.connect(self._delete_image)
        btn_refresh = QPushButton("刷新列表")
        btn_refresh.clicked.connect(self._load_images)
        btn_open_dir = QPushButton("打开目录")
        btn_open_dir.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.abspath(IMAGE_DIR))))

        for btn in (btn_import, btn_delete, btn_refresh, btn_open_dir):
            btn_row.addWidget(btn)
        btn_row.addItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        layout.addLayout(btn_row)

    def _load_images(self):
        self.list_widget.clear()
        paths = list_images()
        for path in paths:
            icon = QIcon(path)
            item = QListWidgetItem(icon, os.path.basename(path))
            item.setData(Qt.UserRole, path)
            self.list_widget.addItem(item)
        if not paths:
            self.preview_label.setText("图片目录为空，点击“导入图片”上传。")
            ToastManager.instance().show("图片库为空，请先导入", "info")
        else:
            self.preview_label.setText("请选择一张图片预览")

    def _current_image(self):
        items = self.list_widget.selectedItems()
        if not items:
            return None
        return items[0].data(Qt.UserRole)

    def _update_preview(self):
        path = self._current_image()
        if not path:
            self.preview_label.setText("请选择一张图片预览")
            self.preview_label.setPixmap(QPixmap())
            return
        pixmap = QPixmap(path)
        if pixmap.isNull():
            self.preview_label.setText("无法加载图片")
            return
        scaled = pixmap.scaled(360, 220, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.preview_label.setPixmap(scaled)

    def _import_image(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择图片", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp)")
        if not file_path:
            ToastManager.instance().show("已取消导入", "info")
            return
        try:
            new_path = import_image(file_path)
            ToastManager.instance().show(f"已导入 {os.path.basename(new_path)}", "success")
            self._load_images()
        except Exception as exc:
            ToastManager.instance().show(str(exc), "error")

    def _delete_image(self):
        path = self._current_image()
        if not path:
            ToastManager.instance().show("请选择要删除的图片", "warning")
            return
        reply = QMessageBox.question(self, "确认删除", f"确认删除 {os.path.basename(path)} 吗？", QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        try:
            delete_image(path)
            ToastManager.instance().show("图片已删除", "success")
            self._load_images()
        except Exception as exc:
            ToastManager.instance().show(str(exc), "error")

