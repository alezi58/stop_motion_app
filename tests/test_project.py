from __future__ import annotations

from pathlib import Path

from stopmotion.camera import camera_capture_source
from stopmotion.project import StopMotionProject


def write_frame(path: Path, marker: str) -> None:
    path.write_text(marker, encoding="utf-8")


def test_project_folder_creation(tmp_path: Path) -> None:
    project = StopMotionProject.open_default(tmp_path)

    assert project.frames_dir.exists()
    assert project.output_dir.exists()


def test_next_frame_path_and_ordering(tmp_path: Path) -> None:
    project = StopMotionProject.open_default(tmp_path)

    assert project.next_frame_path().name == "frame_0001.jpg"
    write_frame(project.next_frame_path(), "one")
    write_frame(project.next_frame_path(), "two")

    assert [path.name for path in project.list_frames()] == ["frame_0001.jpg", "frame_0002.jpg"]
    assert project.next_frame_path().name == "frame_0003.jpg"


def test_delete_frame_renumbers_remaining_frames(tmp_path: Path) -> None:
    project = StopMotionProject.open_default(tmp_path)
    first = project.next_frame_path()
    write_frame(first, "one")
    second = project.next_frame_path()
    write_frame(second, "two")
    third = project.next_frame_path()
    write_frame(third, "three")

    project.delete_frame(second)

    frames = project.list_frames()
    assert [path.name for path in frames] == ["frame_0001.jpg", "frame_0002.jpg"]
    assert frames[0].read_text(encoding="utf-8") == "one"
    assert frames[1].read_text(encoding="utf-8") == "three"


def test_prepare_render_frames_copies_sequential_order(tmp_path: Path) -> None:
    project = StopMotionProject.open_default(tmp_path)
    write_frame(project.next_frame_path(), "one")
    write_frame(project.next_frame_path(), "two")

    render_dir = project.prepare_render_frames()

    render_frames = sorted(render_dir.glob("frame_*.jpg"))
    assert [path.name for path in render_frames] == ["frame_0001.jpg", "frame_0002.jpg"]
    assert render_frames[0].read_text(encoding="utf-8") == "one"


def test_camera_source_setting_round_trip(tmp_path: Path) -> None:
    project = StopMotionProject.open_default(tmp_path)

    assert project.camera_source() == "0"

    project.save_camera_source("http://192.168.1.23:8080/video")

    assert project.camera_source() == "http://192.168.1.23:8080/video"


def test_create_new_project_uses_next_empty_project_folder(tmp_path: Path) -> None:
    first = StopMotionProject.create_new(tmp_path)
    write_frame(first.next_frame_path(), "one")
    second = StopMotionProject.create_new(tmp_path)

    assert first.root.name == "project_0001"
    assert second.root.name == "project_0002"
    assert second.list_frames() == []


def test_open_current_project_uses_saved_current_project(tmp_path: Path) -> None:
    project = StopMotionProject.create_new(tmp_path)
    project.save_as_current(tmp_path)

    reopened = StopMotionProject.open_current(tmp_path)

    assert reopened.root == project.root


def test_numeric_camera_source_becomes_usb_camera_index() -> None:
    assert camera_capture_source("0") == 0
    assert camera_capture_source("1") == 1


def test_url_camera_source_stays_string() -> None:
    source = "http://192.168.1.23:8080/video"

    assert camera_capture_source(source) == source
