import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import rana_qgis_plugin.utils.generic as utils


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
    utils.cleanup_folder(tmp_cache_dir, communication)
    assert tmp_cache_dir.exists()
    assert list(tmp_cache_dir.iterdir()) == []
    communication.log_warn.assert_not_called()


def test_cleanup_folder_nonexistent_dir(communication):
    """If the folder does not exist, no error is raised."""
    utils.cleanup_folder(Path("/nonexistent/path/rana_cache_test_xyz"), communication)
    communication.log_warn.assert_not_called()


def test_cleanup_folder_logs_warn_on_failure(tmp_cache_dir, communication):
    """If a deletion fails, log_warn is called and no exception is raised."""
    with pytest.MonkeyPatch().context() as mp:
        mp.setattr(
            shutil,
            "rmtree",
            lambda *a, **kw: (_ for _ in ()).throw(OSError("Permission denied")),
        )
        utils.cleanup_folder(tmp_cache_dir, communication)

    assert communication.log_warn.called


@pytest.mark.parametrize(
    "input_bytes, expected_output",
    [
        (0, "0 Byte"),
        (1, "1.0 Bytes"),
        (1023, "1023.0 Bytes"),
        (1024, "1.0 KB"),
        (2048, "2.0 KB"),
        (1048576, "1.0 MB"),
        (1073741824, "1.0 GB"),
        (pow(1024, 4), "1.0 TB"),  # 1 Terabyte
        (123456789, "117.74 MB"),
    ],
)
def test_display_bytes(input_bytes, expected_output):
    assert utils.display_bytes(input_bytes) == expected_output


@pytest.mark.parametrize(
    "url",
    [
        "/tenant/something/project",
        "/tenant/something/project/somethingelse",
        "/tenant/something/project/somethingelse/file.txt",
    ],
)
def test_parse_url_no_query(url):
    # ensure the correct elements are extracted from the path
    path_params, query_params = utils.parse_url(url)
    assert path_params == {"tenant_id": "tenant", "project_id": "project"}


def test_parse_url_with_query():
    # just ensure that query_parmas are returned, no need to test urllib
    url = "/tenant/something/project?param1=value1"
    path_params, query_params = utils.parse_url(url)
    assert query_params == {"param1": ["value1"]}
