from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from rana_qgis_plugin.loader import Loader
from rana_qgis_plugin.simulation.utils import UploadFileStatus, UploadFileType
from rana_qgis_plugin.widgets.schematisation_new_wizard import (
    SchematisationWizardBase,
)


@pytest.fixture
def step_progress():
    with (
        patch.object(SchematisationWizardBase, "update_step_progress") as update,
        patch.object(SchematisationWizardBase, "finish_step_progress") as finish,
    ):
        yield SimpleNamespace(update=update, finish=finish)


def make_initial_revision_upload_context(tmp_path):
    raster_dir = tmp_path / "rasters"
    raster_dir.mkdir()
    raster_path = raster_dir / "dem.tif"
    raster_path.write_bytes(b"dem")
    database_path = tmp_path / "model.gpkg"
    database_path.write_bytes(b"gpkg")
    local_schematisation = MagicMock()
    local_schematisation.schematisation_db_filepath = str(database_path)
    local_schematisation.wip_revision = SimpleNamespace(raster_dir=str(raster_dir))
    schematisation = SimpleNamespace(id=42, name="Model")
    project = {"id": "project"}
    raster_paths = {"model_settings": {"dem_file": "dem.tif"}}
    return project, schematisation, local_schematisation, raster_paths, raster_path


def test_save_initial_revision_uses_revision_zero_spec_and_success_refresh(
    qgis_application, tmp_path, step_progress
):
    progress_bar = MagicMock()
    project, schematisation, local, raster_paths, raster_path = (
        make_initial_revision_upload_context(tmp_path)
    )
    communication = MagicMock()
    loader = Loader(communication)
    refresh = MagicMock()
    task_manager = MagicMock()

    with (
        patch("rana_qgis_plugin.loader.get_threedi_api", return_value=object()),
        patch(
            "rana_qgis_plugin.loader.QgsApplication.taskManager",
            return_value=task_manager,
        ),
    ):
        task = loader.save_initial_revision(
            project,
            schematisation,
            local,
            raster_paths,
            refresh,
            progress_bar,
            MagicMock(),
            "Model",
        )

    assert task is not None
    task_manager.addTask.assert_called_once_with(task)
    specification = task.upload_specification
    assert specification["latest_revision"].number == 0
    assert specification["create_revision"] is True
    assert specification["make_3di_model"] is True
    assert specification["commit_message"] == "Initial commit"
    assert specification["selected_files"]["geopackage"] == {
        "filepath": local.schematisation_db_filepath,
        "make_action": True,
        "remote_raster": None,
        "status": UploadFileStatus.NEW,
        "type": UploadFileType.DB,
    }
    assert specification["selected_files"]["dem_file"] == {
        "filepath": str(raster_path),
        "make_action": True,
        "remote_raster": None,
        "status": UploadFileStatus.NEW,
        "type": UploadFileType.RASTER,
    }

    task.upload_succeeded.emit(0)

    refresh.assert_called_once_with()
    communication.bar_info.assert_not_called()


def test_save_initial_revision_does_not_refresh_after_task_termination(
    qgis_application, tmp_path, step_progress
):
    progress_bar = MagicMock()
    project, schematisation, local, raster_paths, _ = (
        make_initial_revision_upload_context(tmp_path)
    )
    communication = MagicMock()
    loader = Loader(communication)
    refresh = MagicMock()
    task_manager = MagicMock()

    with (
        patch("rana_qgis_plugin.loader.get_threedi_api", return_value=object()),
        patch(
            "rana_qgis_plugin.loader.QgsApplication.taskManager",
            return_value=task_manager,
        ),
    ):
        task = loader.save_initial_revision(
            project,
            schematisation,
            local,
            raster_paths,
            refresh,
            progress_bar,
            MagicMock(),
            "Model",
        )

    assert task is not None
    task.error_message = "upload failed"
    task.taskTerminated.emit()

    communication.show_error.assert_called_once_with("upload failed")
    refresh.assert_not_called()


def test_save_initial_revision_reports_cancel_without_refresh(
    qgis_application, tmp_path, step_progress
):
    progress_bar = MagicMock()
    project, schematisation, local, raster_paths, _ = (
        make_initial_revision_upload_context(tmp_path)
    )
    communication = MagicMock()
    loader = Loader(communication)
    refresh = MagicMock()
    task_manager = MagicMock()

    with (
        patch("rana_qgis_plugin.loader.get_threedi_api", return_value=object()),
        patch(
            "rana_qgis_plugin.loader.QgsApplication.taskManager",
            return_value=task_manager,
        ),
    ):
        task = loader.save_initial_revision(
            project,
            schematisation,
            local,
            raster_paths,
            refresh,
            progress_bar,
            MagicMock(),
            "Model",
        )

    assert task is not None
    task.cancel()

    communication.bar_warn.assert_called_once_with(
        "Initial schematisation upload cancelled."
    )
    communication.show_error.assert_not_called()
    refresh.assert_not_called()


def test_save_initial_revision_stops_before_task_if_a_raster_is_missing(
    qgis_application, tmp_path, step_progress
):
    project, schematisation, local, raster_paths, raster_path = (
        make_initial_revision_upload_context(tmp_path)
    )
    raster_path.unlink()
    communication = MagicMock()
    loader = Loader(communication)
    progress_bar = MagicMock()

    with (
        patch("rana_qgis_plugin.loader.get_threedi_api", return_value=object()),
        patch("rana_qgis_plugin.loader.QgsApplication.taskManager") as task_manager,
    ):
        task = loader.save_initial_revision(
            project,
            schematisation,
            local,
            raster_paths,
            MagicMock(),
            progress_bar,
            MagicMock(),
            "Model",
        )

    assert task is None
    task_manager.assert_not_called()
    communication.show_error.assert_called_once()
    assert "dem.tif" in communication.show_error.call_args.args[0]
    step_progress.finish.assert_called_once_with(communication.iface, progress_bar)
    communication.bar_error.assert_called_once()
    assert "was created" in communication.bar_error.call_args.args[0]
    assert communication.bar_error.call_args.kwargs["dur"] == 0


def test_late_upload_progress_after_model_request_is_ignored(
    qgis_application, tmp_path, step_progress
):
    project, schematisation, local, raster_paths, _ = (
        make_initial_revision_upload_context(tmp_path)
    )
    loader = Loader(MagicMock())
    with (
        patch("rana_qgis_plugin.loader.get_threedi_api", return_value=object()),
        patch("rana_qgis_plugin.loader.QgsApplication.taskManager"),
        patch.object(loader, "handle_initial_model_requested"),
    ):
        task = loader.save_initial_revision(
            project,
            schematisation,
            local,
            raster_paths,
            MagicMock(),
            MagicMock(),
            MagicMock(),
            "Model",
        )
        task.revision = SimpleNamespace(id=7)
        task.progress_changed.emit("dem.tif", 25, 0, 100)
        calls_before_hand_off = step_progress.update.call_count
        task.model_requested.emit()
        task.progress_changed.emit("dem.tif", 50, 0, 100)

    assert calls_before_hand_off > 1
    assert step_progress.update.call_count == calls_before_hand_off


@pytest.mark.parametrize(
    "response, expect_prompt",
    [({"id": "p"}, True), (None, False)],
)
def test_model_request_always_finishes_the_progress_item(
    qgis_application, step_progress, response, expect_prompt
):
    communication = MagicMock()
    loader = Loader(communication)
    progress_bar = MagicMock()

    with (
        patch.object(loader, "start_model_tracker_process", return_value=response),
        patch.object(loader, "point_user_to_processes") as point_user,
    ):
        loader.handle_initial_model_requested(
            {"id": "project"},
            SimpleNamespace(id=1, name="Model"),
            7,
            False,
            progress_bar,
            MagicMock(),
            "Model",
        )

    step_progress.finish.assert_called_once_with(communication.iface, progress_bar)
    assert point_user.called is expect_prompt


def test_model_request_points_user_to_processes_with_job_id(
    qgis_application, step_progress
):
    project = {"id": "project"}
    schematisation = SimpleNamespace(id=1, name="Model")
    error_signals = MagicMock()
    main_window = object()
    communication = MagicMock()
    communication.iface.mainWindow.return_value = main_window
    loader = Loader(communication)
    progress_bar = MagicMock()

    with (
        patch.object(
            loader, "start_model_tracker_process", return_value={"job_id": "job-9"}
        ),
        patch.object(loader, "point_user_to_processes") as point_user,
    ):
        loader.handle_initial_model_requested(
            project,
            schematisation,
            7,
            False,
            progress_bar,
            error_signals,
            "Model",
        )

    point_user.assert_called_once_with(
        project,
        ["job-9"],
        error_signals,
        main_window,
        question="Track model creation for Model in the Processes window?",
    )
