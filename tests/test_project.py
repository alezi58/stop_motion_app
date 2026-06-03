from __future__ import annotations

from pathlib import Path

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
