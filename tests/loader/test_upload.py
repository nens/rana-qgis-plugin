import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from qgis.core import QgsApplication
from qgis.PyQt.QtCore import QCoreApplication

from rana_qgis_plugin.loader import Loader, UploadChoice
from rana_qgis_plugin.workers.upload import UploadJob, UploadPreparationResult


def make_loader():
    communication = MagicMock()
    return Loader(communication), communication


def wait_for(condition, timeout=3.0):
    """Process Qt events until condition is true or timeout expires."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        if condition():
            return True
        time.sleep(0.05)
    return False


def test_upload_files_with_no_jobs():
    loader, communication = make_loader()
    path = "/tmp/file.tif"
    with (
        patch(
            "rana_qgis_plugin.loader.QFileDialog.getOpenFileNames",
            return_value=([path], ""),
        ),
        patch(
            "rana_qgis_plugin.loader.prepare_new_file_upload",
            return_value=UploadPreparationResult(None),
        ),
        patch("rana_qgis_plugin.loader.QgsApplication.taskManager") as manager,
    ):
        loader.upload_files({"id": "project"}, "folder")
    manager.assert_not_called()
    communication.custom_ask.assert_not_called()


@pytest.mark.parametrize(
    "prep_result",
    [
        UploadPreparationResult(
            None, "conflict", conflict_path="foo/bar", exact_conflict=True
        ),
        UploadPreparationResult(None, "error", conflict_path="", exact_conflict=False),
    ],
)
def test_upload_files_abort_on_problems(prep_result):
    loader, communication = make_loader()
    communication.custom_ask.return_value = "Abort"
    with (
        patch(
            "rana_qgis_plugin.loader.QFileDialog.getOpenFileNames",
            return_value=(["/tmp/file.tif"], ""),
        ),
        patch(
            "rana_qgis_plugin.loader.prepare_new_file_upload",
            return_value=prep_result,
        ),
        patch("rana_qgis_plugin.loader.QgsApplication.taskManager") as manager,
    ):
        loader.upload_files({"id": "project"}, "folder")
    manager.assert_not_called()


@pytest.mark.parametrize("upload_choice", [UploadChoice.OVERWRITE, UploadChoice.SKIP])
def test_upload_files_case_conflict_overwrite(tmp_path, upload_choice):
    loader, communication = make_loader()
    communication.custom_ask.return_value = upload_choice.value

    case_result = UploadPreparationResult(
        None,
        "A case-insensitive conflict exists.",
        conflict_path="folder/FILE.tif",
    )
    prepared_job = UploadJob("project", tmp_path / "file.tif", "url", {})

    with (
        patch(
            "rana_qgis_plugin.loader.QFileDialog.getOpenFileNames",
            return_value=([str(tmp_path / "file.tif")], ""),
        ),
        patch(
            "rana_qgis_plugin.loader.prepare_new_file_upload",
            side_effect=[case_result, UploadPreparationResult(prepared_job)],
        ) as prepare,
        patch("rana_qgis_plugin.loader.FileUploadTask") as task_class,
        patch(
            "rana_qgis_plugin.loader.QgsApplication.taskManager",
            return_value=MagicMock(),
        ),
    ):
        loader.upload_files({"id": "project"}, "folder")
    communication.custom_ask.assert_called_once()
    if upload_choice == UploadChoice.OVERWRITE:
        assert prepare.call_count == 2
        task_class.assert_called_once_with([prepared_job])
    else:
        assert prepare.call_count == 1
        task_class.assert_not_called()


def test_upload_files_collects_multiple_jobs():
    loader, _ = make_loader()
    first = UploadJob("project", Path("first.tif"), "url1", {})
    second = UploadJob("project", Path("second.tif"), "url2", {})
    task_manager = MagicMock()
    with (
        patch(
            "rana_qgis_plugin.loader.QFileDialog.getOpenFileNames",
            return_value=(["/tmp/first.tif", "/tmp/second.tif"], ""),
        ),
        patch(
            "rana_qgis_plugin.loader.prepare_new_file_upload",
            side_effect=[
                UploadPreparationResult(first),
                UploadPreparationResult(second),
            ],
        ),
        patch("rana_qgis_plugin.loader.FileUploadTask") as task_class,
        patch(
            "rana_qgis_plugin.loader.QgsApplication.taskManager",
            return_value=task_manager,
        ),
    ):
        loader.upload_files({"id": "project"}, "folder")
    task_class.assert_called_once_with([first, second])
    task_manager.addTask.assert_called_once_with(task_class.return_value)


def test_upload_files_collects_multiple_jobs_abort():
    loader, communication = make_loader()
    communication.custom_ask.return_value = UploadChoice.ABORT.value
    first = UploadJob("project", Path("first.tif"), "url1", {})
    third = UploadJob("project", Path("third.tif"), "url2", {})
    task_manager = MagicMock()
    with (
        patch(
            "rana_qgis_plugin.loader.QFileDialog.getOpenFileNames",
            return_value=(["/tmp/first.tif", "/tmp/second.tif"], ""),
        ),
        patch(
            "rana_qgis_plugin.loader.prepare_new_file_upload",
            side_effect=[
                UploadPreparationResult(first),
                UploadPreparationResult(
                    None, "conflict", conflict_path="second.tif", exact_conflict=False
                ),
                UploadPreparationResult(third),
            ],
        ) as prepare,
        patch("rana_qgis_plugin.loader.FileUploadTask") as task_class,
        patch(
            "rana_qgis_plugin.loader.QgsApplication.taskManager",
            return_value=task_manager,
        ),
    ):
        loader.upload_files({"id": "project"}, "folder")
    communication.custom_ask.assert_called_once()
    assert prepare.call_count == 2
    task_manager.addTask.assert_not_called()
    task_class.assert_not_called()


def test_upload_files_collects_multiple_jobs_overwrite_all():
    loader, communication = make_loader()
    communication.custom_ask.return_value = UploadChoice.OVERWRITE_ALL.value
    first = UploadJob("project", Path("first.tif"), "url1", {})
    second = UploadJob("project", Path("second.tif"), "url2", {})
    third = UploadJob("project", Path("third.tif"), "url3", {})
    task_manager = MagicMock()
    with (
        patch(
            "rana_qgis_plugin.loader.QFileDialog.getOpenFileNames",
            return_value=(["/tmp/first.tif", "/tmp/second.tif", "/tmp/third.tif"], ""),
        ),
        patch(
            "rana_qgis_plugin.loader.prepare_new_file_upload",
            side_effect=[
                UploadPreparationResult(first),
                UploadPreparationResult(
                    second, "conflict", conflict_path="second.tif", exact_conflict=False
                ),
                UploadPreparationResult(second),
                UploadPreparationResult(
                    third, "conflict", conflict_path="second.tif", exact_conflict=False
                ),
            ],
        ) as prepare,
        patch("rana_qgis_plugin.loader.FileUploadTask") as upload_task,
        patch(
            "rana_qgis_plugin.loader.QgsApplication.taskManager",
            return_value=task_manager,
        ),
    ):
        loader.upload_files({"id": "project"}, "folder")
    assert prepare.call_count == 4
    assert communication.custom_ask.call_count == 1
    task_manager.addTask.assert_called_once_with(upload_task.return_value)
    upload_task.assert_called_once_with([first, second, third])


# --- Layer 1: handle_upload_completed / handle_upload_file_started / handle_upload_file_failed ---


def test_handle_upload_completed_success_calls_callback():
    loader, communication = make_loader()
    callback = MagicMock()
    loader.handle_upload_completed(True, refresh_callback=callback)
    callback.assert_called_once_with()
    communication.bar_info.assert_called_once()


def test_handle_upload_completed_success_without_callback():
    loader, communication = make_loader()
    loader.handle_upload_completed(True)
    communication.bar_info.assert_called_once()


def test_handle_upload_completed_failure():
    loader, communication = make_loader()
    callback = MagicMock()
    loader.handle_upload_completed(False, refresh_callback=callback)
    communication.bar_error.assert_called_once()


def test_handle_upload_completed_cancelled():
    loader, communication = make_loader()
    task = MagicMock()
    task.isCanceled.return_value = True
    loader.handle_upload_completed(False, task)
    communication.bar_warn.assert_called_once()


def test_handle_upload_completed_clears_message_bar():
    loader, communication = make_loader()
    loader.handle_upload_completed(True)
    communication.clear_message_bar.assert_called_once()


def test_handle_upload_file_failed_logs_error():
    loader, communication = make_loader()
    loader.handle_upload_file_failed("/tmp/file.tif", "connection error")
    communication.log_err.assert_called_once()


def test_data_sync_acquires_and_releases_lock_and_clears_dirty_state():
    loader, communication = make_loader()
    task = MagicMock()
    task.rana_sync_keys = [("project", "descriptor")]
    task.failed_files = []
    task.isCanceled.return_value = False
    layer = MagicMock()

    with (
        patch.object(loader, "layers_for_keys", return_value=[layer]),
        patch("rana_qgis_plugin.loader.clear_dirty") as clear_dirty,
    ):
        assert loader.acquire_sync_keys(task.rana_sync_keys)
        loader.handle_sync_completed(
            task, "rana/data_dirty", "Data saved to Rana.", task.failed_files
        )

    clear_dirty.assert_called_once_with(layer, "rana/data_dirty")
    assert not loader.layer_lock_registry.is_locked(("project", "descriptor"))
    communication.bar_info.assert_called_once()


def test_data_sync_termination_releases_lock_without_clearing_dirty_state():
    loader, _ = make_loader()
    task = MagicMock()
    task.rana_sync_keys = [("project", "descriptor")]
    task.isCanceled.return_value = True
    assert loader.acquire_sync_keys(task.rana_sync_keys)

    with patch("rana_qgis_plugin.loader.clear_dirty") as clear_dirty:
        loader.release_sync_keys(task.rana_sync_keys)
        loader.handle_data_sync_terminated(task)

    clear_dirty.assert_not_called()
    assert not loader.layer_lock_registry.is_locked(("project", "descriptor"))


def test_style_sync_completion_clears_style_state_and_releases_lock():
    loader, communication = make_loader()
    task = MagicMock()
    task.rana_sync_keys = [("project", "descriptor")]
    task.failed_items = []
    task.isCanceled.return_value = False
    layer = MagicMock()

    with (
        patch.object(loader, "layers_for_keys", return_value=[layer]),
        patch("rana_qgis_plugin.loader.clear_dirty") as clear_dirty,
    ):
        assert loader.acquire_sync_keys(task.rana_sync_keys)
        loader.handle_sync_completed(
            task, "rana/style_dirty", "Styles saved to Rana.", task.failed_items
        )

    clear_dirty.assert_called_once_with(layer, "rana/style_dirty")
    assert not loader.layer_lock_registry.is_locked(("project", "descriptor"))
    communication.bar_info.assert_called_once()


def test_sync_key_acquisition_releases_partial_batch_on_conflict():
    loader, communication = make_loader()
    first = ("project", "first")
    second = ("project", "second")
    assert loader.layer_lock_registry.acquire(second)

    assert not loader.acquire_sync_keys([first, second])

    assert not loader.layer_lock_registry.is_locked(first)
    assert loader.layer_lock_registry.is_locked(second)
    communication.bar_warn.assert_not_called()


# --- Layer 2: full signal chain via real QgsTaskManager ---


def test_upload_files_full_chain_success(qgis_application, tmp_path):
    loader, communication = make_loader()
    job_path = tmp_path / "file.tif"
    job_path.write_bytes(b"data")
    callback = MagicMock()

    with (
        patch(
            "rana_qgis_plugin.loader.QFileDialog.getOpenFileNames",
            return_value=([str(job_path)], ""),
        ),
        patch(
            "rana_qgis_plugin.loader.prepare_new_file_upload",
            return_value=UploadPreparationResult(
                UploadJob(
                    "project",
                    job_path,
                    "http://upload.example.com",
                    {"path": "file.tif"},
                )
            ),
        ),
        patch("rana_qgis_plugin.workers.upload.requests.put") as mock_put,
        patch(
            "rana_qgis_plugin.workers.upload.finish_file_upload",
            return_value={"id": "file.tif", "descriptor_id": "desc"},
        ),
        patch(
            "rana_qgis_plugin.loader.QgsApplication.taskManager",
            return_value=QgsApplication.taskManager(),
        ),
    ):
        mock_put.return_value = MagicMock(raise_for_status=lambda: None)
        loader.upload_files({"id": "project"}, "folder", refresh_callback=callback)
        assert wait_for(lambda: communication.bar_info.called), "upload never completed"

    communication.progress_bar.assert_called_once_with(
        "Downloading file.tif", minimum=0, maximum=0
    )
    communication.bar_info.assert_called_once()
    communication.bar_error.assert_not_called()
    callback.assert_called_once_with()


def test_upload_files_full_chain_failure(qgis_application, tmp_path):
    loader, communication = make_loader()
    job_path = tmp_path / "file.tif"
    job_path.write_bytes(b"data")
    callback = MagicMock()

    with (
        patch(
            "rana_qgis_plugin.loader.QFileDialog.getOpenFileNames",
            return_value=([str(job_path)], ""),
        ),
        patch(
            "rana_qgis_plugin.loader.prepare_new_file_upload",
            return_value=UploadPreparationResult(
                UploadJob(
                    "project",
                    job_path,
                    "http://upload.example.com",
                    {"path": "file.tif"},
                )
            ),
        ),
        patch(
            "rana_qgis_plugin.workers.upload.requests.put",
            side_effect=OSError("network error"),
        ),
        patch(
            "rana_qgis_plugin.loader.QgsApplication.taskManager",
            return_value=QgsApplication.taskManager(),
        ),
    ):
        loader.upload_files({"id": "project"}, "folder", refresh_callback=callback)
        assert wait_for(lambda: communication.bar_error.called), (
            "failure never reported"
        )

    communication.progress_bar.assert_called_once_with(
        "Downloading file.tif", minimum=0, maximum=0
    )
    communication.bar_error.assert_called_once()
    communication.bar_info.assert_not_called()
    callback.assert_not_called()
