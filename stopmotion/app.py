from __future__ import annotations

import sys
from pathlib import Path

import cv2
from PySide6.QtCore import QRect, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QColor, QKeySequence, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSlider,
    QStackedWidget,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from .camera import CameraThread
from .project import StopMotionProject
from .renderer import RenderError, Renderer
from .ui_helpers import cv_frame_to_pixmap, image_path_to_thumbnail


def app_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


class CameraPreview(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("preview")
        self.setMinimumSize(700, 440)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._frame_pixmap = QPixmap()
        self._previous_pixmap = QPixmap()
        self._message = "Камера пока не подключена"
        self._grid_mode = "off"
        self._onion_enabled = True

    def set_frame_pixmap(self, pixmap: QPixmap) -> None:
        self._frame_pixmap = pixmap
        self._message = ""
        self.update()

    def set_message(self, message: str) -> None:
        self._message = message
        self.update()

    def set_previous_frame(self, path: Path | None) -> None:
        if path and path.exists():
            self._previous_pixmap = QPixmap(str(path))
        else:
            self._previous_pixmap = QPixmap()
        self.update()

    def set_grid_mode(self, mode: str) -> None:
        self._grid_mode = mode
        self.update()

    def set_onion_enabled(self, enabled: bool) -> None:
        self._onion_enabled = enabled
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.fillRect(self.rect(), QColor("#111827"))

        content_rect = self._content_rect()
        if not self._frame_pixmap.isNull():
            painter.drawPixmap(content_rect, self._frame_pixmap)
            if self._onion_enabled and not self._previous_pixmap.isNull():
                painter.setOpacity(0.38)
                painter.drawPixmap(content_rect, self._previous_pixmap)
                painter.setOpacity(1.0)
            self._draw_grid(painter, content_rect)
            return

        painter.setPen(QColor("#ffffff"))
        painter.drawText(
            self.rect().adjusted(24, 24, -24, -24),
            Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
            self._message,
        )

    def _content_rect(self) -> QRect:
        if self._frame_pixmap.isNull():
            return self.rect()

        scaled_size = QSize(self._frame_pixmap.size())
        scaled_size.scale(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
        left = (self.width() - scaled_size.width()) // 2
        top = (self.height() - scaled_size.height()) // 2
        return QRect(left, top, scaled_size.width(), scaled_size.height())

    def _draw_grid(self, painter: QPainter, rect: QRect) -> None:
        if self._grid_mode == "off":
            return

        if self._grid_mode == "thirds":
            ratios = [1 / 3, 2 / 3]
            pen = QPen(QColor(255, 255, 255, 175), 2)
        else:
            ratios = [0.382, 0.618]
            pen = QPen(QColor(250, 204, 21, 195), 2)

        painter.setPen(pen)
        for ratio in ratios:
            x = rect.left() + round(rect.width() * ratio)
            y = rect.top() + round(rect.height() * ratio)
            painter.drawLine(x, rect.top(), x, rect.bottom())
            painter.drawLine(rect.left(), y, rect.right(), y)


class VideoPlaybackView(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("videoView")
        self.setMinimumSize(700, 440)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._frame_pixmap = QPixmap()
        self._message = "Мультфильм появится здесь"

    def set_frame_pixmap(self, pixmap: QPixmap) -> None:
        self._frame_pixmap = pixmap
        self._message = ""
        self.update()

    def set_message(self, message: str) -> None:
        self._message = message
        self._frame_pixmap = QPixmap()
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.fillRect(self.rect(), QColor("#111827"))

        if not self._frame_pixmap.isNull():
            content_rect = self._content_rect()
            painter.drawPixmap(content_rect, self._frame_pixmap)
            return

        painter.setPen(QColor("#ffffff"))
        painter.drawText(
            self.rect().adjusted(24, 24, -24, -24),
            Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
            self._message,
        )

    def _content_rect(self) -> QRect:
        scaled_size = QSize(self._frame_pixmap.size())
        scaled_size.scale(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
        left = (self.width() - scaled_size.width()) // 2
        top = (self.height() - scaled_size.height()) // 2
        return QRect(left, top, scaled_size.width(), scaled_size.height())


class CameraDialog(QDialog):
    def __init__(self, last_source: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Камера")
        self.setModal(True)
        self.setMinimumWidth(440)

        self.source_combo = QComboBox()
        self.source_combo.addItem("Веб-камера 0", "0")
        self.source_combo.addItem("Веб-камера 1", "1")
        self.source_combo.addItem("Веб-камера 2", "2")
        self.source_combo.addItem("Веб-камера 3", "3")
        self.source_combo.addItem("IP-камера", "ip")

        self.source_input = QLineEdit()
        self.source_input.setPlaceholderText("http://192.168.1.23:8080/video")

        self.error_label = QLabel()
        self.error_label.setObjectName("dialogError")
        self.error_label.setWordWrap(True)
        self.error_label.hide()

        if last_source in {"0", "1", "2", "3"}:
            self.source_combo.setCurrentIndex(int(last_source))
        else:
            self.source_combo.setCurrentIndex(4)
            self.source_input.setText(last_source)

        self.source_combo.currentIndexChanged.connect(self._update_source_input)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Подключить")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Отмена")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        title = QLabel("Выберите камеру")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)
        layout.addWidget(self.source_combo)
        layout.addWidget(self.source_input)
        layout.addWidget(self.error_label)
        layout.addWidget(buttons)

        self._update_source_input()

    def selected_source(self) -> str:
        if self.source_combo.currentData() == "ip":
            return self.source_input.text().strip()
        return str(self.source_combo.currentData())

    def accept(self) -> None:
        if not self.selected_source():
            self.error_label.setText("Введите адрес IP-камеры.")
            self.error_label.show()
            return
        super().accept()

    def _update_source_input(self) -> None:
        is_ip_camera = self.source_combo.currentData() == "ip"
        self.source_input.setVisible(is_ip_camera)
        self.error_label.hide()


class StopMotionWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Моя мультистудия")
        self.resize(1180, 780)

        self.base_dir = app_base_dir()
        self.project = StopMotionProject.open_current(self.base_dir)
        self.renderer = Renderer(self.project)
        self.camera_thread: CameraThread | None = None
        self.camera_source = self.project.camera_source()
        self.camera_state = "disconnected"
        self.camera_connected_once = False
        self.current_frame = None
        self.video_capture = None
        self.last_video_path: Path | None = None
        self.playback_fps = 8

        self.title_label = QLabel("Моя мультистудия")
        self.title_label.setObjectName("titleLabel")

        self.frame_count_label = QLabel("Кадров: 0")
        self.frame_count_label.setObjectName("frameCountLabel")

        self.new_project_button = QPushButton("Новый мульт")
        self.new_project_button.setObjectName("newProjectButton")
        self.new_project_button.setMinimumWidth(160)
        self.new_project_button.clicked.connect(self.create_new_project)

        self.connect_button = QPushButton("Выбрать камеру")
        self.connect_button.setObjectName("connectButton")
        self.connect_button.setMinimumWidth(178)
        self.connect_button.clicked.connect(self.choose_camera)

        self.preview = CameraPreview()
        self.video_view = VideoPlaybackView()
        self.video_page = self._build_video_page()
        self.preview_stack = QStackedWidget()
        self.preview_stack.addWidget(self.preview)
        self.preview_stack.addWidget(self.video_page)

        self.playback_timer = QTimer(self)
        self.playback_timer.timeout.connect(self.show_next_video_frame)

        self.capture_button = QPushButton("Снять кадр")
        self.capture_button.setObjectName("captureButton")
        self.capture_button.setMinimumHeight(74)
        self.capture_button.setEnabled(False)
        self.capture_button.clicked.connect(self.capture_frame)

        self.fps_value_label = QLabel("8 кадр/с")
        self.fps_value_label.setObjectName("fpsValueLabel")

        self.fps_slider = QSlider(Qt.Orientation.Horizontal)
        self.fps_slider.setObjectName("fpsSlider")
        self.fps_slider.setRange(4, 25)
        self.fps_slider.setValue(8)
        self.fps_slider.setTickInterval(1)
        self.fps_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.fps_slider.valueChanged.connect(self.update_fps_label)

        self.grid_combo = QComboBox()
        self.grid_combo.setObjectName("gridCombo")
        self.grid_combo.addItem("Без сетки", "off")
        self.grid_combo.addItem("Сетка 3 x 3", "thirds")
        self.grid_combo.addItem("Золотое сечение", "golden")
        self.grid_combo.currentIndexChanged.connect(self.change_grid)

        self.onion_checkbox = QCheckBox("Показать прошлый кадр")
        self.onion_checkbox.setObjectName("onionCheckbox")
        self.onion_checkbox.setChecked(True)
        self.onion_checkbox.toggled.connect(self.preview.set_onion_enabled)

        self.render_button = QPushButton("Собрать и проиграть")
        self.render_button.setObjectName("renderButton")
        self.render_button.setMinimumHeight(46)
        self.render_button.clicked.connect(self.render_and_play)

        self.delete_button = QPushButton("Удалить кадр")
        self.delete_button.setObjectName("deleteButton")
        self.delete_button.setMinimumHeight(46)
        self.delete_button.clicked.connect(self.delete_selected_frame)

        self.thumbnail_list = QListWidget()
        self.thumbnail_list.setViewMode(QListWidget.ViewMode.IconMode)
        self.thumbnail_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.thumbnail_list.setMovement(QListWidget.Movement.Static)
        self.thumbnail_list.setFlow(QListWidget.Flow.LeftToRight)
        self.thumbnail_list.setWrapping(False)
        self.thumbnail_list.setUniformItemSizes(True)
        self.thumbnail_list.setIconSize(QSize(112, 82))
        self.thumbnail_list.setGridSize(QSize(128, 116))
        self.thumbnail_list.setMinimumHeight(148)
        self.thumbnail_list.setSpacing(10)

        self.status = QLabel()
        self.status.setObjectName("statusLabel")
        self.status.setWordWrap(True)
        self.status.hide()

        self._setup_icons()
        self._build_layout()
        self._add_shortcuts()
        self._apply_style()
        self.set_camera_state("disconnected")
        self.reload_thumbnails()

    def _build_video_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("videoPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.replay_button = QPushButton("Еще раз")
        self.replay_button.setObjectName("smallPlayerButton")
        self.replay_button.clicked.connect(self.replay_video)

        self.back_to_camera_button = QPushButton("К камере")
        self.back_to_camera_button.setObjectName("smallPlayerButton")
        self.back_to_camera_button.clicked.connect(self.return_to_camera)

        controls = QHBoxLayout()
        controls.addStretch(1)
        controls.addWidget(self.replay_button)
        controls.addWidget(self.back_to_camera_button)

        layout.addWidget(self.video_view, 1)
        layout.addLayout(controls)
        return page

    def _build_layout(self) -> None:
        central = QWidget()
        central.setObjectName("appRoot")
        root = QVBoxLayout(central)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(16)

        header = QHBoxLayout()
        header.addWidget(self.title_label, 1)
        header.addWidget(self.frame_count_label)
        header.addWidget(self.new_project_button)
        header.addWidget(self.connect_button)

        work_area = QHBoxLayout()
        work_area.setSpacing(16)

        preview_panel = QFrame()
        preview_panel.setObjectName("previewPanel")
        preview_layout = QVBoxLayout(preview_panel)
        preview_layout.setContentsMargins(12, 12, 12, 12)
        preview_layout.addWidget(self.preview_stack)

        side_panel = QFrame()
        side_panel.setObjectName("sidePanel")
        side_panel.setMinimumWidth(280)
        side_panel.setMaximumWidth(320)
        side_layout = QVBoxLayout(side_panel)
        side_layout.setContentsMargins(16, 16, 16, 16)
        side_layout.setSpacing(14)

        speed_row = QHBoxLayout()
        speed_label = QLabel("Скорость")
        speed_label.setObjectName("fieldLabel")
        speed_row.addWidget(speed_label)
        speed_row.addStretch(1)
        speed_row.addWidget(self.fps_value_label)

        helper_label = QLabel("Помощь для кадра")
        helper_label.setObjectName("fieldLabel")

        side_layout.addWidget(self.capture_button)
        side_layout.addSpacing(4)
        side_layout.addLayout(speed_row)
        side_layout.addWidget(self.fps_slider)
        side_layout.addSpacing(4)
        side_layout.addWidget(helper_label)
        side_layout.addWidget(self.grid_combo)
        side_layout.addWidget(self.onion_checkbox)
        side_layout.addSpacing(4)
        side_layout.addWidget(self.render_button)
        side_layout.addWidget(self.delete_button)
        side_layout.addStretch(1)
        side_layout.addWidget(self.status)

        work_area.addWidget(preview_panel, 1)
        work_area.addWidget(side_panel)

        frames_header = QHBoxLayout()
        frames_label = QLabel("Лента кадров")
        frames_label.setObjectName("sectionLabel")
        frames_header.addWidget(frames_label)
        frames_header.addStretch(1)

        root.addLayout(header)
        root.addLayout(work_area, 1)
        root.addLayout(frames_header)
        root.addWidget(self.thumbnail_list)
        self.setCentralWidget(central)

    def _setup_icons(self) -> None:
        icon_size = QSize(22, 22)
        self.new_project_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
        self.connect_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))
        self.capture_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))
        self.render_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.delete_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon))
        self.replay_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self.back_to_camera_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowBack))
        for button in [
            self.new_project_button,
            self.connect_button,
            self.capture_button,
            self.render_button,
            self.delete_button,
            self.replay_button,
            self.back_to_camera_button,
        ]:
            button.setIconSize(icon_size)

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            #appRoot {
                background: #f7fafc;
                color: #14213d;
                font-family: "Segoe UI", Tahoma, Verdana, Arial, sans-serif;
                font-size: 16px;
            }
            #titleLabel {
                color: #14213d;
                font-size: 32px;
                font-weight: 800;
            }
            #frameCountLabel {
                background: #e0f2fe;
                border: 2px solid #38bdf8;
                border-radius: 16px;
                color: #075985;
                font-size: 18px;
                font-weight: 700;
                padding: 8px 16px;
            }
            #previewPanel,
            #sidePanel {
                background: #ffffff;
                border: 2px solid #dbeafe;
                border-radius: 8px;
            }
            #fieldLabel,
            #sectionLabel {
                color: #334155;
                font-size: 17px;
                font-weight: 700;
            }
            #sectionLabel {
                font-size: 19px;
            }
            QLineEdit,
            QComboBox {
                background: #ffffff;
                border: 2px solid #cbd5e1;
                border-radius: 8px;
                color: #0f172a;
                min-height: 40px;
                padding: 4px 12px;
            }
            QLineEdit:focus,
            QComboBox:focus {
                border-color: #14b8a6;
            }
            QPushButton {
                border: none;
                border-radius: 8px;
                color: #ffffff;
                font-size: 16px;
                font-weight: 800;
                min-height: 42px;
                padding: 8px 14px;
            }
            QPushButton:disabled {
                background: #94a3b8;
                color: #e2e8f0;
            }
            #connectButton[cameraState="disconnected"] {
                background: #2563eb;
            }
            #newProjectButton {
                background: #7c3aed;
            }
            #newProjectButton:hover {
                background: #6d28d9;
            }
            #connectButton[cameraState="connecting"] {
                background: #f59e0b;
            }
            #connectButton[cameraState="connected"] {
                background: #16a34a;
            }
            #connectButton[cameraState="error"] {
                background: #dc2626;
            }
            #connectButton[cameraState="disconnected"]:hover {
                background: #1d4ed8;
            }
            #connectButton[cameraState="connected"]:hover {
                background: #15803d;
            }
            #connectButton[cameraState="error"]:hover {
                background: #b91c1c;
            }
            #captureButton {
                background: #f97316;
                font-size: 20px;
                min-height: 74px;
            }
            #captureButton:hover {
                background: #ea580c;
            }
            #renderButton {
                background: #0f766e;
            }
            #renderButton:hover {
                background: #0d9488;
            }
            #deleteButton {
                background: #64748b;
            }
            #deleteButton:hover {
                background: #dc2626;
            }
            #smallPlayerButton {
                background: #2563eb;
                min-width: 118px;
            }
            #preview,
            #videoPage,
            #videoView {
                background: #111827;
                border-radius: 8px;
                color: #ffffff;
                font-size: 22px;
                font-weight: 700;
            }
            #statusLabel {
                border-radius: 8px;
                font-size: 16px;
                font-weight: 650;
                padding: 12px;
            }
            #statusLabel[kind="info"] {
                background: #fef3c7;
                border: 2px solid #f59e0b;
                color: #78350f;
            }
            #statusLabel[kind="error"] {
                background: #fee2e2;
                border: 2px solid #ef4444;
                color: #7f1d1d;
            }
            QCheckBox {
                color: #334155;
                font-size: 16px;
                font-weight: 650;
                spacing: 8px;
            }
            QCheckBox::indicator {
                height: 22px;
                width: 22px;
            }
            QSlider::groove:horizontal {
                background: #dbeafe;
                border-radius: 6px;
                height: 12px;
            }
            QSlider::sub-page:horizontal {
                background: #38bdf8;
                border-radius: 6px;
            }
            QSlider::handle:horizontal {
                background: #f97316;
                border: 2px solid #ffffff;
                border-radius: 10px;
                height: 24px;
                margin: -7px 0;
                width: 24px;
            }
            QListWidget {
                background: #ffffff;
                border: 2px solid #dbeafe;
                border-radius: 8px;
                color: #14213d;
                font-size: 16px;
                font-weight: 700;
                outline: none;
                padding: 10px;
            }
            QListWidget::item {
                background: #f8fafc;
                border: 2px solid #e2e8f0;
                border-radius: 8px;
                margin: 2px;
                padding: 6px;
            }
            QListWidget::item:selected {
                background: #dcfce7;
                border: 3px solid #22c55e;
                color: #14532d;
            }
            QScrollBar:horizontal {
                background: #e2e8f0;
                border-radius: 6px;
                height: 12px;
                margin: 0;
            }
            QScrollBar::handle:horizontal {
                background: #38bdf8;
                border-radius: 6px;
                min-width: 36px;
            }
            CameraDialog {
                background: #f8fafc;
            }
            #dialogTitle {
                color: #14213d;
                font-size: 22px;
                font-weight: 800;
            }
            #dialogError {
                color: #b91c1c;
                font-size: 14px;
                font-weight: 650;
            }
            """
        )

    def _add_shortcuts(self) -> None:
        capture_action = QAction(self)
        capture_action.setShortcut(QKeySequence(Qt.Key.Key_Space))
        capture_action.triggered.connect(self.capture_frame)
        self.addAction(capture_action)

        delete_action = QAction(self)
        delete_action.setShortcut(QKeySequence(Qt.Key.Key_Delete))
        delete_action.triggered.connect(self.delete_selected_frame)
        self.addAction(delete_action)

        render_action = QAction(self)
        render_action.setShortcut(QKeySequence("Ctrl+P"))
        render_action.triggered.connect(self.render_and_play)
        self.addAction(render_action)

        new_project_action = QAction(self)
        new_project_action.setShortcut(QKeySequence("Ctrl+N"))
        new_project_action.triggered.connect(self.create_new_project)
        self.addAction(new_project_action)

    def create_new_project(self) -> None:
        if self.project.list_frames():
            answer = QMessageBox.question(
                self,
                "Новый мульт",
                "Начать новый мульт?\n\nТекущие кадры останутся в старой папке, а лента станет пустой.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        self.stop_video_playback()
        self.preview_stack.setCurrentWidget(self.preview)
        self.project = StopMotionProject.create_new(self.base_dir)
        self.project.save_as_current(self.base_dir)
        self.project.save_camera_source(self.camera_source)
        self.renderer = Renderer(self.project)
        self.last_video_path = None
        self.reload_thumbnails()
        self.update_capture_enabled()
        self.show_message("Новый мульт начат. Лента кадров пустая.", kind="info")

    def choose_camera(self) -> None:
        if self.camera_state == "connecting":
            return
        dialog = CameraDialog(self.camera_source, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.camera_source = dialog.selected_source()
        self.project.save_camera_source(self.camera_source)
        self.start_camera(self.camera_source)

    def start_camera(self, source: str) -> None:
        self.stop_camera(update_state=False)
        if not source:
            self.choose_camera()
            return

        self.camera_connected_once = False
        self.hide_message()
        self.set_camera_state("connecting")
        self.capture_button.setEnabled(False)
        self.preview_stack.setCurrentWidget(self.preview)
        self.stop_video_playback()

        self.camera_thread = CameraThread(source)
        self.camera_thread.frame_ready.connect(self.show_frame)
        self.camera_thread.error.connect(self.handle_camera_error)
        self.camera_thread.connected.connect(self.handle_camera_connected)
        self.camera_thread.finished.connect(self.handle_camera_finished)
        self.camera_thread.start()

    def stop_camera(self, update_state: bool = True) -> None:
        if self.camera_thread and self.camera_thread.isRunning():
            self.camera_thread.stop()
        self.camera_thread = None
        self.connect_button.setEnabled(True)
        if update_state:
            self.set_camera_state("disconnected")
            self.capture_button.setEnabled(False)

    def handle_camera_connected(self) -> None:
        self.camera_connected_once = True
        self.set_camera_state("connected")
        self.hide_message()
        self.update_capture_enabled()

    def handle_camera_finished(self) -> None:
        self.connect_button.setEnabled(True)
        if self.camera_state == "connecting":
            self.set_camera_state("error")

    def handle_camera_error(self, message: str) -> None:
        self.set_camera_state("error")
        self.capture_button.setEnabled(False)
        self.preview.set_message("Камеру не видно")
        self.show_message(message, kind="error")
        if not self.camera_connected_once:
            QTimer.singleShot(250, self.choose_camera)

    def set_camera_state(self, state: str) -> None:
        self.camera_state = state
        labels = {
            "disconnected": "Выбрать камеру",
            "connecting": "Подключаюсь...",
            "connected": "Камера готова",
            "error": "Камеру не видно",
        }
        self.connect_button.setText(labels[state])
        self.connect_button.setEnabled(True)
        self.connect_button.setProperty("cameraState", state)
        self.connect_button.style().unpolish(self.connect_button)
        self.connect_button.style().polish(self.connect_button)

    def update_capture_enabled(self) -> None:
        is_camera_view = self.preview_stack.currentWidget() == self.preview
        self.capture_button.setEnabled(self.camera_state == "connected" and is_camera_view)

    def show_frame(self, frame) -> None:
        self.current_frame = frame.copy()
        pixmap = cv_frame_to_pixmap(frame, self.preview.width(), self.preview.height())
        self.preview.set_frame_pixmap(pixmap)

    def capture_frame(self) -> None:
        if self.current_frame is None:
            self.show_message("Сначала подключите камеру.", kind="info")
            return
        frame_path = self.project.next_frame_path()
        try:
            ok = cv2.imwrite(str(frame_path), self.current_frame)
            if not ok:
                raise OSError("OpenCV не смог сохранить файл.")
        except Exception as exc:
            self.show_message(f"Не получилось сохранить кадр: {exc}", kind="error")
            return
        self.reload_thumbnails(select_path=frame_path)
        self.hide_message()

    def reload_thumbnails(self, select_path: Path | None = None) -> None:
        self.thumbnail_list.clear()
        frames = self.project.list_frames()
        self.frame_count_label.setText(f"Кадров: {len(frames)}")
        self.onion_checkbox.setEnabled(bool(frames))
        self.preview.set_previous_frame(frames[-1] if frames else None)
        for index, frame in enumerate(frames, start=1):
            item = QListWidgetItem(f"{index}")
            item.setData(Qt.ItemDataRole.UserRole, str(frame))
            item.setIcon(image_path_to_thumbnail(frame))
            item.setToolTip(frame.name)
            self.thumbnail_list.addItem(item)
            if select_path and frame.resolve() == select_path.resolve():
                self.thumbnail_list.setCurrentItem(item)
        if not frames:
            self.thumbnail_list.clearSelection()

    def delete_selected_frame(self) -> None:
        item = self.thumbnail_list.currentItem()
        if item is None:
            self.show_message("Выберите кадр в ленте, который нужно удалить.", kind="info")
            return
        frame_path = Path(item.data(Qt.ItemDataRole.UserRole))
        try:
            self.project.delete_frame(frame_path)
        except Exception as exc:
            self.show_message(f"Не получилось удалить кадр: {exc}", kind="error")
            return
        self.reload_thumbnails()
        self.hide_message()

    def update_fps_label(self, value: int) -> None:
        self.fps_value_label.setText(f"{value} кадр/с")

    def change_grid(self) -> None:
        self.preview.set_grid_mode(str(self.grid_combo.currentData()))

    def render_and_play(self) -> None:
        fps = int(self.fps_slider.value())
        self.hide_message()
        self.render_button.setEnabled(False)
        self.render_button.setText("Собираю...")
        try:
            output_path = self.renderer.render(fps)
            self.play_video(output_path, fps)
        except RenderError as exc:
            self.show_message(str(exc), kind="error")
        except Exception as exc:
            self.show_message(f"Видео готово, но проиграть его не получилось: {exc}", kind="error")
        finally:
            self.render_button.setEnabled(True)
            self.render_button.setText("Собрать и проиграть")

    def play_video(self, output_path: Path, fps: int) -> None:
        self.last_video_path = output_path
        self.playback_fps = fps
        self.stop_video_playback(clear_frame=False)
        capture = cv2.VideoCapture(str(output_path))
        if not capture.isOpened():
            raise RenderError("Видео собрано, но встроенный просмотр не смог его открыть.")
        self.video_capture = capture
        self.preview_stack.setCurrentWidget(self.video_page)
        self.update_capture_enabled()
        self.show_next_video_frame()
        self.playback_timer.start(max(1, round(1000 / fps)))

    def replay_video(self) -> None:
        if self.last_video_path:
            self.play_video(self.last_video_path, self.playback_fps)

    def return_to_camera(self) -> None:
        self.stop_video_playback()
        self.preview_stack.setCurrentWidget(self.preview)
        self.update_capture_enabled()

    def show_next_video_frame(self) -> None:
        if self.video_capture is None:
            self.playback_timer.stop()
            return

        ok, frame = self.video_capture.read()
        if not ok or frame is None:
            self.playback_timer.stop()
            return

        pixmap = cv_frame_to_pixmap(frame, self.video_view.width(), self.video_view.height())
        self.video_view.set_frame_pixmap(pixmap)

    def stop_video_playback(self, clear_frame: bool = True) -> None:
        self.playback_timer.stop()
        if self.video_capture is not None:
            self.video_capture.release()
            self.video_capture = None
        if clear_frame:
            self.video_view.set_message("Мультфильм появится здесь")

    def show_message(self, message: str, kind: str = "info") -> None:
        self.status.setText(message)
        self.status.setProperty("kind", kind)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
        self.status.show()

    def hide_message(self) -> None:
        self.status.clear()
        self.status.hide()

    def closeEvent(self, event) -> None:
        self.stop_video_playback()
        self.stop_camera()
        super().closeEvent(event)
