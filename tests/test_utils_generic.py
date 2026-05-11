import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from rana_qgis_plugin.utils.generic import cleanup_folder


@pytest.fixture
def communication():
    return MagicMock()


@pytest.fixture
def tmp_cache_dir(tmp_path):
    """A temporary cache directory with some files and subdirs."""
    (tmp_path / "file1.txt").write_text("data")
    (tmp_path / "file2.txt").write_text("data")
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    (subdir / "nested.txt").write_text("nested")
    return tmp_path


def test_cleanup_folder(tmp_cache_dir, communication):
    """All files and subdirs inside the folder are removed."""
    cleanup_folder(tmp_cache_dir, communication)
    assert tmp_cache_dir.exists()
    assert list(tmp_cache_dir.iterdir()) == []
    communication.log_warn.assert_not_called()


def test_cleanup_folder_nonexistent_dir(communication):
    """If the folder does not exist, no error is raised."""
    cleanup_folder(Path("/nonexistent/path/rana_cache_test_xyz"), communication)
    communication.log_warn.assert_not_called()


def test_cleanup_folder_logs_warn_on_failure(tmp_cache_dir, communication):
    """If a deletion fails, log_warn is called and no exception is raised."""
    with pytest.MonkeyPatch().context() as mp:
        mp.setattr(
            shutil,
            "rmtree",
            lambda *a, **kw: (_ for _ in ()).throw(OSError("Permission denied")),
        )
        cleanup_folder(tmp_cache_dir, communication)

    assert communication.log_warn.called
