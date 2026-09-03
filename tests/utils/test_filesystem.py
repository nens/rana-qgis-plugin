from pathlib import Path

from rana_qgis_plugin.utils.filesystem import ensure_writable_directory


def test_ensure_writable_directory_creates_directory(tmp_path):
    directory = tmp_path / "new" / "revision"

    assert ensure_writable_directory(directory) == (True, None)
    assert directory.is_dir()


def test_ensure_writable_directory_rejects_file(tmp_path):
    file_path = tmp_path / "not-a-directory"
    file_path.write_text("content")

    ok, error = ensure_writable_directory(file_path)

    assert not ok
    assert error
