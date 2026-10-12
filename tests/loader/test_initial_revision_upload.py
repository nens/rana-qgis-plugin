from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from rana_qgis_plugin.loader import Loader
from rana_qgis_plugin.simulation.utils import UploadFileStatus, UploadFileType


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
    qgis_application, tmp_path
):
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
            project, schematisation, local, raster_paths, refresh
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
    communication.bar_info.assert_called_once_with(
        "Initial schematisation revision uploaded."
    )


def test_save_initial_revision_does_not_refresh_after_task_termination(
    qgis_application, tmp_path
):
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
            project, schematisation, local, raster_paths, refresh
        )

    assert task is not None
    task.error_message = "upload failed"
    task.taskTerminated.emit()

    communication.show_error.assert_called_once_with("upload failed")
    refresh.assert_not_called()


def test_save_initial_revision_reports_cancel_without_refresh(
    qgis_application, tmp_path
):
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
            project, schematisation, local, raster_paths, refresh
        )

    assert task is not None
    task.cancel()

    communication.bar_warn.assert_called_once_with(
        "Initial schematisation upload cancelled."
    )
    communication.show_error.assert_not_called()
    refresh.assert_not_called()


def test_save_initial_revision_stops_before_task_if_a_raster_is_missing(
    qgis_application, tmp_path
):
    project, schematisation, local, raster_paths, raster_path = (
        make_initial_revision_upload_context(tmp_path)
    )
    raster_path.unlink()
    communication = MagicMock()
    loader = Loader(communication)

    with (
        patch("rana_qgis_plugin.loader.get_threedi_api", return_value=object()),
        patch("rana_qgis_plugin.loader.QgsApplication.taskManager") as task_manager,
    ):
        task = loader.save_initial_revision(
            project, schematisation, local, raster_paths, MagicMock()
        )

    assert task is None
    task_manager.assert_not_called()
    communication.show_warn.assert_called_once()
    assert "dem.tif" in communication.show_warn.call_args.args[0]
