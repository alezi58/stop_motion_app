from __future__ import annotations

from pathlib import Path

import cv2
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .camera import CameraThread
from .project import StopMotionProject
from .renderer import RenderError, Renderer
from .ui_helpers import cv_frame_to_pixmap, image_path_to_thumbnail


class StopMotionWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Стоп-моушен студия")
        self.resize(1120, 760)

        self.project = StopMotionProject.open_default(Path(__file__).resolve().parents[1])
        self.renderer = Renderer(self.project)
        self.camera_thread: CameraThread | None = None
        self.current_frame = None

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Адрес камеры, например http://192.168.1.23:8080/video или 0")
        self.url_input.setText("0")

        self.connect_button = QPushButton("Подключить камеру")
        self.connect_button.clicked.connect(self.connect_camera)

        self.preview = QLabel("Введите адрес камеры и нажмите «Подключить камеру»")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(640, 420)
        self.preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.preview.setStyleSheet("background: #202124; color: white; border-radius: 8px; font-size: 20px;")

        self.capture_button = QPushButton("Снять кадр")
        self.capture_button.setMinimumHeight(56)
        self.capture_button.clicked.connect(self.capture_frame)

        self.render_button = QPushButton("Собрать и посмотреть")
        self.render_button.setMinimumHeight(44)
        self.render_button.clicked.connect(self.render_and_play)

        self.delete_button = QPushButton("Удалить выбранный кадр")
        self.delete_button.setMinimumHeight(44)
        self.delete_button.clicked.connect(self.delete_selected_frame)

        self.fps_combo = QComboBox()
        for fps in [4, 6, 8, 10, 12, 15, 24]:
            self.fps_combo.addItem(f"{fps} кадр/с", fps)
        self.fps_combo.setCurrentIndex(2)

        self.thumbnail_list = QListWidget()
        self.thumbnail_list.setViewMode(QListWidget.ViewMode.IconMode)
        self.thumbnail_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.thumbnail_list.setMovement(QListWidget.Movement.Static)
        self.thumbnail_list.setIconSize(QSize(96, 96))
        self.thumbnail_list.setMinimumHeight(132)
        self.thumbnail_list.setSpacing(8)

        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setStyleSheet("font-size: 15px; color: #2f3a45;")

        self._build_layout()
        self._add_shortcuts()
        self.reload_thumbnails()
        self.set_status("Готово. Можно подключить камеру или оставить 0 для веб-камеры.")

    def _build_layout(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        camera_row = QHBoxLayout()
        camera_row.addWidget(QLabel("Камера:"))
        camera_row.addWidget(self.url_input, 1)
        camera_row.addWidget(self.connect_button)

        controls = QHBoxLayout()
        controls.addWidget(self.capture_button, 2)
        controls.addWidget(QLabel("Скорость:"))
        controls.addWidget(self.fps_combo)
        controls.addWidget(self.render_button)
        controls.addWidget(self.delete_button)

        root.addLayout(camera_row)
        root.addWidget(self.preview, 1)
        root.addLayout(controls)
        root.addWidget(QLabel("Кадры:"))
        root.addWidget(self.thumbnail_list)
        root.addWidget(self.status)
        self.setCentralWidget(central)

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

    def connect_camera(self) -> None:
        self.stop_camera()
        source = self.url_input.text().strip()
        if not source:
            self.set_status("Введите адрес камеры. Для проверки можно написать 0.")
            return

        self.set_status("Подключаюсь к камере...")
        self.connect_button.setEnabled(False)
        self.camera_thread = CameraThread(source)
        self.camera_thread.frame_ready.connect(self.show_frame)
        self.camera_thread.error.connect(self.handle_camera_error)
        self.camera_thread.connected.connect(lambda: self.set_status("Камера подключена. Можно снимать кадры!"))
        self.camera_thread.finished.connect(lambda: self.connect_button.setEnabled(True))
        self.camera_thread.start()

    def stop_camera(self) -> None:
        if self.camera_thread and self.camera_thread.isRunning():
            self.camera_thread.stop()
        self.camera_thread = None
        self.connect_button.setEnabled(True)

    def show_frame(self, frame) -> None:
        self.current_frame = frame.copy()
        pixmap = cv_frame_to_pixmap(frame, self.preview.width(), self.preview.height())
        self.preview.setPixmap(pixmap)

    def capture_frame(self) -> None:
        if self.current_frame is None:
            self.set_status("Сначала подключите камеру, чтобы увидеть картинку.")
            return
        frame_path = self.project.next_frame_path()
        try:
            ok = cv2.imwrite(str(frame_path), self.current_frame)
            if not ok:
                raise OSError("OpenCV не смог сохранить файл.")
        except Exception as exc:
            self.set_status(f"Не получилось сохранить кадр: {exc}")
            return
        self.reload_thumbnails(select_path=frame_path)
        self.set_status(f"Кадр сохранен. Всего кадров: {len(self.project.list_frames())}.")

    def reload_thumbnails(self, select_path: Path | None = None) -> None:
        self.thumbnail_list.clear()
        frames = self.project.list_frames()
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
            self.set_status("Выберите кадр в ленте, который нужно удалить.")
            return
        frame_path = Path(item.data(Qt.ItemDataRole.UserRole))
        try:
            self.project.delete_frame(frame_path)
        except Exception as exc:
            self.set_status(f"Не получилось удалить кадр: {exc}")
            return
        self.reload_thumbnails()
        self.set_status(f"Кадр удален. Осталось кадров: {len(self.project.list_frames())}.")

    def render_and_play(self) -> None:
        fps = int(self.fps_combo.currentData())
        self.set_status("Собираю мультфильм...")
        self.render_button.setEnabled(False)
        try:
            output_path = self.renderer.render(fps)
            self.renderer.open_with_default_player(output_path)
        except RenderError as exc:
            self.set_status(str(exc))
        except Exception as exc:
            self.set_status(f"Видео готово, но открыть его не получилось: {exc}")
        else:
            self.set_status(f"Готово! Видео сохранено: {output_path}")
        finally:
            self.render_button.setEnabled(True)

    def handle_camera_error(self, message: str) -> None:
        self.set_status(message)
        self.connect_button.setEnabled(True)

    def set_status(self, message: str) -> None:
        self.status.setText(message)

    def closeEvent(self, event) -> None:
        self.stop_camera()
        super().closeEvent(event)
