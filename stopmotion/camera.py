from __future__ import annotations

import time
from typing import Any

import cv2
from PySide6.QtCore import QThread, Signal


def camera_capture_source(source: str) -> str | int:
    source = source.strip()
    if source.isdigit():
        return int(source)
    return source


def scan_usb_cameras(max_index: int = 6) -> list[tuple[int, str]]:
    cameras: list[tuple[int, str]] = []
    previous_log_level = None
    if hasattr(cv2, "getLogLevel") and hasattr(cv2, "setLogLevel"):
        previous_log_level = cv2.getLogLevel()
        cv2.setLogLevel(0)
    try:
        missed_after_found = 0
        for index in range(max_index):
            cap = cv2.VideoCapture(index)
            try:
                if not cap.isOpened():
                    if cameras:
                        missed_after_found += 1
                        if missed_after_found >= 2:
                            break
                    continue
                ok, frame = cap.read()
                if ok and frame is not None:
                    cameras.append((index, f"USB-камера {index}"))
                    missed_after_found = 0
                elif cameras:
                    missed_after_found += 1
                    if missed_after_found >= 2:
                        break
            finally:
                cap.release()
    finally:
        if previous_log_level is not None:
            cv2.setLogLevel(previous_log_level)
    return cameras


class CameraThread(QThread):
    frame_ready = Signal(object)
    error = Signal(str)
    connected = Signal()

    def __init__(self, source: str, parent: Any = None) -> None:
        super().__init__(parent)
        self.source = source.strip()
        self._running = False

    def run(self) -> None:
        capture_source = camera_capture_source(self.source)
        cap = cv2.VideoCapture(capture_source)
        if not cap.isOpened():
            self.error.emit("Не удалось подключиться к камере. Проверьте камеру, адрес и Wi-Fi.")
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
