from pathlib import Path
from unittest.mock import MagicMock, patch

from rana_qgis_plugin.utils.upload import (
    UploadJob,
    UploadPreparationResult,
    UploadTask,
    prepare_existing_file_upload,
    prepare_new_file_upload,
)


def make_job(tmp_path: Path) -> UploadJob:
    local_path = tmp_path / "file.tif"
    local_path.write_bytes(b"data")
    return UploadJob("project", local_path, "https://upload", {"path": "file.tif"})


def make_task(jobs: list[UploadJob]) -> UploadTask:
    return UploadTask(jobs)


def test_prepare_new_file_without_conflict(tmp_path):
    local_path = tmp_path / "file.tif"
    local_path.write_bytes(b"data")
    with (
        patch(
            "rana_qgis_plugin.utils.upload.get_tenant_project_file", return_value=None
        ),
        patch(
            "rana_qgis_plugin.utils.upload.start_file_upload",
            return_value=({"urls": ["https://upload"]}, None),
        ),
    ):
        prep_result = prepare_new_file_upload("project", local_path, "folder")
    assert prep_result.job == UploadJob(
        "project", local_path, "https://upload", {"urls": ["https://upload"]}
    )


def test_prepare_new_file_exact_conflict(tmp_path):
    local_path = tmp_path / "file.tif"
    with (
        patch(
            "rana_qgis_plugin.utils.upload.get_tenant_project_file",
            return_value={"id": "folder/file.tif"},
        ),
        patch("rana_qgis_plugin.utils.upload.start_file_upload") as start_upload,
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
            "rana_qgis_plugin.utils.upload.get_tenant_project_file", return_value=None
        ),
        patch(
            "rana_qgis_plugin.utils.upload.start_file_upload",
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
            "rana_qgis_plugin.utils.upload.get_tenant_project_file", return_value=None
        ),
        patch(
            "rana_qgis_plugin.utils.upload.start_file_upload",
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
            "rana_qgis_plugin.utils.upload.get_tenant_project_file", return_value=None
        ),
        patch(
            "rana_qgis_plugin.utils.upload.start_file_upload", return_value=(None, None)
        ),
    ):
        prep_result = prepare_new_file_upload("project", local_path, "folder")
    assert prep_result.job is None
    assert prep_result.error is not None


def test_prepare_existing_file_timestamp_match():
    project = {"id": "project", "slug": "slug", "name": "Project"}
    file = {"id": "folder/file.tif", "descriptor_id": "descriptor"}
    with (
        patch(
            "rana_qgis_plugin.utils.upload.get_tenant_project_file",
            return_value={"last_modified": "same"},
        ),
        patch("rana_qgis_plugin.utils.upload.QSettings.value", return_value="same"),
    ):
        result = prepare_existing_file_upload(project, file)
    assert result.job is None
    assert result.error is not None


def test_prepare_existing_file_timestamp_diverged():
    project = {"id": "project", "slug": "slug", "name": "Project"}
    file = {"id": "folder/file.tif", "descriptor_id": "descriptor"}
    with (
        patch(
            "rana_qgis_plugin.utils.upload.get_tenant_project_file",
            return_value={"last_modified": "new"},
        ),
        patch("rana_qgis_plugin.utils.upload.QSettings.value", return_value="old"),
    ):
        result = prepare_existing_file_upload(project, file)
    assert result.job is None
    assert result.error is not None


def test_prepare_existing_file_missing_server_file():
    project = {"id": "project", "slug": "slug", "name": "Project"}
    file = {"id": "folder/file.tif", "descriptor_id": "descriptor"}
    with patch(
        "rana_qgis_plugin.utils.upload.get_tenant_project_file", return_value=None
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
            "rana_qgis_plugin.utils.upload.get_tenant_project_file",
            return_value={"last_modified": "new"},
        ),
        patch("rana_qgis_plugin.utils.upload.QSettings.value", return_value="old"),
        patch(
            "rana_qgis_plugin.utils.upload.start_file_upload",
            return_value=(response, None),
        ),
        patch(
            "rana_qgis_plugin.utils.upload.get_tenant_file_descriptor",
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
    "rana_qgis_plugin.utils.upload.finish_file_upload",
    return_value={"id": "uploaded"},
)
@patch("rana_qgis_plugin.utils.upload.requests.put")
def test_upload_task_success(put, finish, tmp_path):
    put.return_value = MagicMock()
    task = make_task([make_job(tmp_path)])
    with (
        patch.object(UploadTask, "isCanceled", return_value=False),
        patch.object(UploadTask, "setProgress"),
    ):
        assert task.run() is True
    put.assert_called_once()
    finish.assert_called_once_with("project", {"path": "file.tif"})
    assert task.successful_files == [tmp_path / "file.tif"]
    assert task.failed_files == []


@patch(
    "rana_qgis_plugin.utils.upload.finish_file_upload",
    return_value={"id": "uploaded"},
)
@patch("rana_qgis_plugin.utils.upload.requests.put")
def test_upload_task_cancellation_between_files(put, finish, tmp_path):
    first = make_job(tmp_path)
    second_path = tmp_path / "second.tif"
    second_path.write_bytes(b"data")
    second = UploadJob("project", second_path, "https://upload", {"path": "second.tif"})
    task = make_task([first, second])

    with patch.object(UploadTask, "isCanceled", side_effect=[False, True]):
        assert task.run() is False
    assert put.call_count == 1
    assert finish.call_count == 1
    assert len(task.successful_files) == 1
    assert len(task.failed_files) == 0


def test_upload_task_failed_put(tmp_path):
    task = make_task([make_job(tmp_path)])
    response = MagicMock()
    response.raise_for_status.side_effect = RuntimeError("put failed")

    with patch.object(UploadTask, "isCanceled", return_value=False):
        with patch("rana_qgis_plugin.utils.upload.requests.put", return_value=response):
            assert task.run() is False
    assert task.failed_files == [(tmp_path / "file.tif", "put failed")]
    assert task.successful_files == []


@patch("rana_qgis_plugin.utils.upload.requests.put")
@patch("rana_qgis_plugin.utils.upload.finish_file_upload", return_value=None)
def test_upload_task_failed_finish(finish, put, tmp_path):
    put.return_value = MagicMock()
    task = make_task([make_job(tmp_path)])

    with (
        patch.object(UploadTask, "isCanceled", return_value=False),
        patch.object(UploadTask, "setProgress"),
    ):
        assert task.run() is False
    assert task.failed_files == [
        (tmp_path / "file.tif", "Failed to complete file upload")
    ]
