from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .project import StopMotionProject


class RenderError(RuntimeError):
    pass


class Renderer:
    def __init__(self, project: StopMotionProject) -> None:
        self.project = project

    def render(self, fps: int) -> Path:
        if shutil.which("ffmpeg") is None:
            raise RenderError("FFmpeg не найден. Установите FFmpeg и добавьте его в PATH.")

        frames = self.project.list_frames()
        if len(frames) < 2:
            raise RenderError("Нужно хотя бы 2 кадра, чтобы собрать мультфильм.")

        render_dir = self.project.prepare_render_frames()
        output_path = self.project.output_video_path
        output_path.parent.mkdir(parents=True, exist_ok=True)

        command = [
            "ffmpeg",
            "-y",
            "-framerate",
            str(fps),
            "-i",
            "frame_%04d.jpg",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(output_path.resolve()),
        ]

        completed = subprocess.run(
            command,
            cwd=render_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip()
            raise RenderError(f"FFmpeg не смог собрать видео.\n{detail}")
        return output_path

    @staticmethod
    def open_with_default_player(path: Path) -> None:
        if os.name == "nt":
            os.startfile(path)  # type: ignore[attr-defined]
            return
        if shutil.which("open"):
            subprocess.Popen(["open", str(path)])
            return
        if shutil.which("xdg-open"):
            subprocess.Popen(["xdg-open", str(path)])
            return
        raise RenderError(f"Видео готово: {path}")
