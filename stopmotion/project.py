from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path


FRAME_PATTERN = "frame_*.jpg"


@dataclass
class StopMotionProject:
    root: Path

    @classmethod
    def open_default(cls, base_dir: Path | None = None) -> "StopMotionProject":
        root = (base_dir or Path.cwd()) / "projects" / "default"
        project = cls(root=root)
        project.ensure_folders()
        return project

    @property
    def frames_dir(self) -> Path:
        return self.root / "frames"

    @property
    def output_dir(self) -> Path:
        return self.root / "output"

    @property
    def render_temp_dir(self) -> Path:
        return self.root / "render_temp"

    @property
    def output_video_path(self) -> Path:
        return self.output_dir / "animation.mp4"

    def ensure_folders(self) -> None:
        self.frames_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def list_frames(self) -> list[Path]:
        self.ensure_folders()
        return sorted(self.frames_dir.glob(FRAME_PATTERN))

    def next_frame_path(self) -> Path:
        return self.frames_dir / f"frame_{len(self.list_frames()) + 1:04d}.jpg"

    def delete_frame(self, frame_path: Path) -> None:
        frame_path = frame_path.resolve()
        frames_dir = self.frames_dir.resolve()
        if frame_path.parent != frames_dir:
            raise ValueError("Кадр находится вне папки проекта.")
        if not frame_path.exists():
            raise FileNotFoundError(frame_path)

        backup_dir = self.root / "frames_backup"
        if backup_dir.exists():
            shutil.rmtree(backup_dir)

        try:
            shutil.copytree(self.frames_dir, backup_dir)
            frame_path.unlink()
            self.renumber_frames()
        except Exception:
            if self.frames_dir.exists():
                shutil.rmtree(self.frames_dir)
            shutil.copytree(backup_dir, self.frames_dir)
            raise
        finally:
            if backup_dir.exists():
                shutil.rmtree(backup_dir)

    def renumber_frames(self) -> None:
        frames = self.list_frames()
        temp_dir = self.root / "frames_renumbering"
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        temp_dir.mkdir(parents=True)

        try:
            for index, frame in enumerate(frames, start=1):
                shutil.copy2(frame, temp_dir / f"frame_{index:04d}.jpg")
            for frame in self.frames_dir.glob(FRAME_PATTERN):
                frame.unlink()
            for frame in sorted(temp_dir.glob(FRAME_PATTERN)):
                shutil.move(str(frame), self.frames_dir / frame.name)
        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)

    def prepare_render_frames(self) -> Path:
        if self.render_temp_dir.exists():
            shutil.rmtree(self.render_temp_dir)
        self.render_temp_dir.mkdir(parents=True)

        for index, frame in enumerate(self.list_frames(), start=1):
            shutil.copy2(frame, self.render_temp_dir / f"frame_{index:04d}.jpg")
        return self.render_temp_dir
