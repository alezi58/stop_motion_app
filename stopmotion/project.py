from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path


FRAME_PATTERN = "frame_*.jpg"


@dataclass
class StopMotionProject:
    root: Path

    @staticmethod
    def projects_dir(base_dir: Path | None = None) -> Path:
        return (base_dir or Path.cwd()) / "projects"

    @staticmethod
    def app_settings_path(base_dir: Path | None = None) -> Path:
        return StopMotionProject.projects_dir(base_dir) / "app_settings.json"

    @classmethod
    def open_default(cls, base_dir: Path | None = None) -> "StopMotionProject":
        root = cls.projects_dir(base_dir) / "default"
        project = cls(root=root)
        project.ensure_folders()
        return project

    @classmethod
    def open_current(cls, base_dir: Path | None = None) -> "StopMotionProject":
        settings_path = cls.app_settings_path(base_dir)
        if settings_path.exists():
            try:
                settings = json.loads(settings_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                settings = {}
            project_name = settings.get("current_project")
            if isinstance(project_name, str):
                root = cls.projects_dir(base_dir) / project_name
                if root.exists():
                    project = cls(root=root)
                    project.ensure_folders()
                    return project
        return cls.open_default(base_dir)

    @classmethod
    def create_new(cls, base_dir: Path | None = None) -> "StopMotionProject":
        projects_dir = cls.projects_dir(base_dir)
        projects_dir.mkdir(parents=True, exist_ok=True)

        index = 1
        while True:
            root = projects_dir / f"project_{index:04d}"
            if not root.exists():
                project = cls(root=root)
                project.ensure_folders()
                return project
            index += 1

    def save_as_current(self, base_dir: Path | None = None) -> None:
        settings_path = self.app_settings_path(base_dir)
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(
            json.dumps({"current_project": self.root.name}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

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
    def settings_path(self) -> Path:
        return self.root / "settings.json"

    @property
    def output_video_path(self) -> Path:
        return self.output_dir / "animation.mp4"

    def ensure_folders(self) -> None:
        self.frames_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def load_settings(self) -> dict:
        self.ensure_folders()
        if not self.settings_path.exists():
            return {}
        try:
            data = json.loads(self.settings_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def save_settings(self, settings: dict) -> None:
        self.ensure_folders()
        self.settings_path.write_text(
            json.dumps(settings, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def camera_source(self) -> str:
        source = self.load_settings().get("camera_source", "0")
        return str(source).strip() or "0"

    def save_camera_source(self, source: str) -> None:
        settings = self.load_settings()
        settings["camera_source"] = source.strip() or "0"
        self.save_settings(settings)

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
