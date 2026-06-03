from __future__ import annotations

import time
from typing import Any

import cv2
from PySide6.QtCore import QThread, Signal


class CameraThread(QThread):
    frame_ready = Signal(object)
    error = Signal(str)
    connected = Signal()

    def __init__(self, source: str, parent: Any = None) -> None:
        super().__init__(parent)
        self.source = source.strip()
        self._running = False

    def run(self) -> None:
        capture_source: str | int = 0 if self.source == "0" else self.source
        cap = cv2.VideoCapture(capture_source)
        if not cap.isOpened():
            self.error.emit("Не удалось подключиться к камере. Проверьте адрес и Wi-Fi.")
            return

        self._running = True
        self.connected.emit()
        while self._running:
            ok, frame = cap.read()
            if not ok or frame is None:
                self.error.emit("Камера перестала отдавать изображение.")
                break
            self.frame_ready.emit(frame)
            time.sleep(0.01)
        cap.release()

    def stop(self) -> None:
        self._running = False
        self.wait(1500)
