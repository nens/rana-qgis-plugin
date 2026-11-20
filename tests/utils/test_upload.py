import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from rana_qgis_plugin.workers import upload as upload_module
from rana_qgis_plugin.workers.upload import (
    FileUploadTask,
    UploadJob,
    prepare_existing_file_upload,
    prepare_new_file_upload,
)


def make_job(tmp_path: Path) -> UploadJob:
    local_path = tmp_path / "file.tif"
    local_path.write_bytes(b"data")
    return UploadJob("project", local_path, "https://upload", {"path": "file.tif"})


def make_task(jobs: list[UploadJob]) -> FileUploadTask:
    return FileUploadTask(jobs)


def test_prepare_new_file_without_conflict(tmp_path):
    local_path = tmp_path / "file.tif"
    local_path.write_bytes(b"data")
    with (
        patch(
            "rana_qgis_plugin.workers.upload.get_tenant_project_file", return_value=None
        ),
        patch(
            "rana_qgis_plugin.workers.upload.start_file_upload",
            return_value=({"urls": ["https://upload"]}, None),
        ),
        patch(
            "rana_qgis_plugin.workers.upload.get_tenant_file_descriptor",
            return_value=None,
        ),
    ):
        prep_result = prepare_new_file_upload("project", local_path, "folder")
    assert prep_result.job == UploadJob(
        "project", local_path, "https://upload", {"urls": ["https://upload"]}
    )


def test_prepare_new_file_includes_message(tmp_path):
    local_path = tmp_path / "file.tif"
    local_path.write_bytes(b"data")
    with (
        patch(
            "rana_qgis_plugin.workers.upload.get_tenant_project_file", return_value=None
        ),
        patch(
            "rana_qgis_plugin.workers.upload.start_file_upload",
            return_value=({"urls": ["https://upload"]}, None),
        ),
    ):
        prep_result = prepare_new_file_upload(
            "project", local_path, "folder", message="Upload roads"
        )
    assert prep_result.job is not None
    assert prep_result.job.payload["message"] == "Upload roads"


def test_prepare_new_file_exact_conflict(tmp_path):
    local_path = tmp_path / "file.tif"
    with (
        patch(
            "rana_qgis_plugin.workers.upload.get_tenant_project_file",
            return_value={"id": "folder/file.tif"},
        ),
        patch("rana_qgis_plugin.workers.upload.start_file_upload") as start_upload,
    ):
        prep_result = prepare_new_file_upload("project", local_path, "folder")
    assert prep_result.job == None
    assert prep_result.error is not None
    assert prep_result.exact_conflict is True
    start_upload.assert_not_called()


def test_prepare_new_file_case_conflict_retry(tmp_path):
    local_path = tmp_path / "file.tif"
    with (
        patch(
            "rana_qgis_plugin.workers.upload.get_tenant_project_file", return_value=None
        ),
        patch(
            "rana_qgis_plugin.workers.upload.start_file_upload",
            side_effect=[
                (None, {"detail": [{"ctx": {"path": "folder/FILE.tif"}}]}),
                ({"urls": ["https://upload"]}, None),
            ],
        ) as start_upload,
    ):
        prep_result = prepare_new_file_upload(
            "project", local_path, "folder", overwrite_case=True
        )
    assert prep_result.job is not None
    assert start_upload.call_args_list[1].args == (
        "project",
        {"path": "folder/FILE.tif"},
    )


def test_prepare_new_file_malformed_conflict(tmp_path):
    local_path = tmp_path / "file.tif"
    with (
        patch(
            "rana_qgis_plugin.workers.upload.get_tenant_project_file", return_value=None
        ),
        patch(
            "rana_qgis_plugin.workers.upload.start_file_upload",
            return_value=(None, {"error": "invalid"}),
        ),
    ):
        prep_result = prepare_new_file_upload(
            "project", local_path, "folder", overwrite_case=True
        )
    assert prep_result.job is None
    assert prep_result.error is not None


def test_prepare_new_file_failed_initiation(tmp_path):
    local_path = tmp_path / "file.tif"
    with (
        patch(
            "rana_qgis_plugin.workers.upload.get_tenant_project_file", return_value=None
        ),
        patch(
            "rana_qgis_plugin.workers.upload.start_file_upload",
            return_value=(None, None),
        ),
    ):
        prep_result = prepare_new_file_upload("project", local_path, "folder")
    assert prep_result.job is None
    assert prep_result.error is not None


@pytest.mark.parametrize("commit_message", ["foo", None])
def test_prepare_existing_file_timestamp_match(commit_message):
    project = {"id": "project", "slug": "slug", "name": "Project"}
    file = {"id": "folder/file.tif", "descriptor_id": "descriptor"}
    with (
        patch(
            "rana_qgis_plugin.workers.upload.get_tenant_project_file",
            return_value={"last_modified": "same"},
        ),
        patch("rana_qgis_plugin.workers.upload.QSettings.value", return_value="same"),
        patch(
            "rana_qgis_plugin.workers.upload.start_file_upload",
            return_value=({"urls": ["https://upload"]}, None),
        ),
        patch(
            "rana_qgis_plugin.workers.upload.get_tenant_file_descriptor",
            return_value=None,
        ),
    ):
        result = prepare_existing_file_upload(project, file, message=commit_message)
    assert result.job is not None
    assert result.error is None
    assert result.status is not None
    assert result.status.value == "ready"
    if commit_message:
        assert result.job.payload["message"] == commit_message
    else:
        assert "message" not in result.job.payload


def test_prepare_existing_file_timestamp_diverged():
    project = {"id": "project", "slug": "slug", "name": "Project"}
    file = {"id": "folder/file.tif", "descriptor_id": "descriptor"}
    with (
        patch(
            "rana_qgis_plugin.workers.upload.get_tenant_project_file",
            return_value={"last_modified": "2026-08-25T12:00:00Z"},
        ),
        patch(
            "rana_qgis_plugin.workers.upload.QSettings.value",
            return_value="2026-08-24T12:00:00Z",
        ),
    ):
        result = prepare_existing_file_upload(project, file)
    assert result.job is None
    assert result.error is not None


def test_prepare_existing_file_missing_server_file():
    project = {"id": "project", "slug": "slug", "name": "Project"}
    file = {"id": "folder/file.tif", "descriptor_id": "descriptor"}
    with patch(
        "rana_qgis_plugin.workers.upload.get_tenant_project_file", return_value=None
    ):
        result = prepare_existing_file_upload(project, file)
    assert result.job is None
    assert result.error is not None


def test_prepare_existing_file_descriptor_metadata(tmp_path):
    local_file = tmp_path / "file.tif"
    project = {"id": "project", "slug": "slug", "name": "Project"}
    file = {"id": "folder/file.tif", "descriptor_id": "descriptor"}
    response = {"urls": ["https://upload"], "id": "upload"}
    with (
        patch(
            "rana_qgis_plugin.workers.upload.get_tenant_project_file",
            return_value={"last_modified": "new"},
        ),
        patch("rana_qgis_plugin.workers.upload.QSettings.value", return_value="old"),
        patch(
            "rana_qgis_plugin.workers.upload.start_file_upload",
            return_value=(response, None),
        ),
        patch(
            "rana_qgis_plugin.workers.upload.get_tenant_file_descriptor",
            return_value={
                "meta": {"style_id": "style"},
                "description": "description",
                "data_type": "raster",
            },
        ),
    ):
        result = prepare_existing_file_upload(
            project, file, local_file=local_file, overwrite=True
        )
    assert result.error is None
    assert result.job is not None
    assert result.job.payload["descriptor"] == {
        "meta": {"style_id": "style"},
        "description": "description",
        "data_type": "raster",
    }


@patch(
    "rana_qgis_plugin.workers.upload.finish_file_upload",
    return_value={"id": "uploaded"},
)
@patch("rana_qgis_plugin.workers.upload.requests.put")
def test_upload_task_success(put, finish, tmp_path):
    put.return_value = MagicMock()
    task = make_task([make_job(tmp_path)])
    with (
        patch.object(FileUploadTask, "isCanceled", return_value=False),
        patch.object(FileUploadTask, "setProgress"),
    ):
        assert task.run() is True
    put.assert_called_once()
    finish.assert_called_once_with("project", {"path": "file.tif"})
    assert task.successful_files == [tmp_path / "file.tif"]
    assert task.failed_files == []


@patch("rana_qgis_plugin.workers.upload.requests.put")
@patch(
    "rana_qgis_plugin.workers.upload.finish_file_upload",
    return_value={"last_modified": "2026-08-26T12:00:00Z"},
)
def test_upload_task_stores_server_timestamp(finish, put, tmp_path):
    put.return_value = MagicMock()
    job = make_job(tmp_path)
    job.last_modified_key = "project/file.tif/last_modified"
    task = make_task([job])

    with (
        patch.object(FileUploadTask, "isCanceled", return_value=False),
        patch.object(FileUploadTask, "setProgress"),
        patch("rana_qgis_plugin.workers.upload.QSettings") as settings,
    ):
        assert task.run() is True

    settings.return_value.setValue.assert_called_once_with(
        "project/file.tif/last_modified", "2026-08-26T12:00:00Z"
    )


@patch(
    "rana_qgis_plugin.workers.upload.finish_file_upload",
    return_value={"id": "uploaded"},
)
@patch("rana_qgis_plugin.workers.upload.requests.put")
def test_upload_task_cancellation_between_files(put, finish, tmp_path):
    first = make_job(tmp_path)
    second_path = tmp_path / "second.tif"
    second_path.write_bytes(b"data")
    second = UploadJob("project", second_path, "https://upload", {"path": "second.tif"})
    task = make_task([first, second])

    with patch.object(FileUploadTask, "isCanceled", side_effect=[False, True]):
        assert task.run() is False
    assert put.call_count == 1
    assert finish.call_count == 1
    assert len(task.successful_files) == 1
    assert len(task.failed_files) == 0


def test_upload_task_failed_put(tmp_path):
    task = make_task([make_job(tmp_path)])
    response = MagicMock()
    response.raise_for_status.side_effect = RuntimeError("put failed")

    with patch.object(FileUploadTask, "isCanceled", return_value=False):
        with patch(
            "rana_qgis_plugin.workers.upload.requests.put", return_value=response
        ):
            assert task.run() is False
    assert task.failed_files == [(tmp_path / "file.tif", "put failed")]
    assert task.successful_files == []


@patch("rana_qgis_plugin.workers.upload.requests.put")
@patch("rana_qgis_plugin.workers.upload.finish_file_upload", return_value=None)
def test_upload_task_failed_finish(finish, put, tmp_path):
    put.return_value = MagicMock()
    task = make_task([make_job(tmp_path)])

    with (
        patch.object(FileUploadTask, "isCanceled", return_value=False),
        patch.object(FileUploadTask, "setProgress"),
    ):
        assert task.run() is False
    assert task.failed_files == [
        (tmp_path / "file.tif", "Failed to complete file upload")
    ]


@patch("rana_qgis_plugin.workers.upload.requests.put")
@patch(
    "rana_qgis_plugin.workers.upload.finish_file_upload",
    side_effect=[{"id": "first"}, None, {"id": "third"}],
)
def test_upload_task_emits_file_completed_once_per_successful_file(
    finish, put, tmp_path
):
    jobs = []
    for name in ("first.tif", "second.tif", "third.tif"):
        path = tmp_path / name
        path.write_bytes(b"data")
        jobs.append(UploadJob("project", path, "https://upload", {"path": name}))
    task = make_task(jobs)
    completed: list[UploadJob] = []
    task.file_completed.connect(completed.append)

    with (
        patch.object(FileUploadTask, "isCanceled", return_value=False),
        patch.object(FileUploadTask, "setProgress"),
    ):
        assert task.run() is False

    assert completed == [jobs[0], jobs[2]]
    assert len(task.failed_files) == 1


def rows_in_main_file_only(path: Path) -> int:
    """Count rows as seen by a copy of the main file, without its -wal file."""
    copy = path.with_name("copy.gpkg")
    copy.write_bytes(path.read_bytes())
    with sqlite3.connect(copy) as connection:
        count = connection.execute("SELECT count(*) FROM points").fetchone()[0]
    connection.close()
    copy.unlink()
    return count


def make_wal_geopackage(path: Path) -> sqlite3.Connection:
    """Create a GeoPackage-like file in WAL mode with one row only in the -wal."""
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA wal_autocheckpoint=0")
    connection.execute("CREATE TABLE points (id INTEGER)")
    connection.commit()
    connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    connection.execute("INSERT INTO points VALUES (1)")
    connection.commit()
    return connection


def test_geopackage_preprocess_moves_wal_edits_into_main_file(tmp_path):
    path = tmp_path / "file.gpkg"
    writer = make_wal_geopackage(path)
    job = UploadJob("project", path, "https://upload", {})
    assert rows_in_main_file_only(path) == 0

    job.preprocess()

    assert rows_in_main_file_only(path) == 1
    writer.close()


def test_geopackage_preprocess_fails_when_checkpoint_stays_busy(tmp_path, monkeypatch):
    monkeypatch.setattr(upload_module, "CHECKPOINT_TIMEOUT", 0.05)
    monkeypatch.setattr(upload_module, "CHECKPOINT_RETRY_DELAY", 0.01)
    path = tmp_path / "file.gpkg"
    writer = make_wal_geopackage(path)
    reader = sqlite3.connect(path)
    reader.execute("BEGIN")
    reader.execute("SELECT count(*) FROM points").fetchone()
    writer.execute("INSERT INTO points VALUES (2)")
    writer.commit()
    job = UploadJob("project", path, "https://upload", {})

    with pytest.raises(RuntimeError, match="file.gpkg"):
        job.preprocess()

    reader.close()
    writer.close()


def test_non_geopackage_preprocess_does_nothing(tmp_path):
    job = make_job(tmp_path)

    with patch("rana_qgis_plugin.workers.upload.sqlite3.connect") as connect:
        job.preprocess()

    connect.assert_not_called()
