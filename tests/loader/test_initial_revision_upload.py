from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from qgis.gui import QgsMessageBar

from rana_qgis_plugin.communication import UICommunication
from rana_qgis_plugin.loader import Loader
from rana_qgis_plugin.simulation.utils import UploadFileStatus, UploadFileType


def make_progress_bar(qgis_application):
    iface = MagicMock()
    message_bar = QgsMessageBar()
    iface.messageBar.return_value = message_bar
    progress_bar = UICommunication(iface=iface).progress_bar("Preparing", maximum=100)
    progress_bar.message_bar = message_bar
    return progress_bar


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
            project,
            schematisation,
            local,
            raster_paths,
            refresh,
            make_progress_bar(qgis_application),
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
            project,
            schematisation,
            local,
            raster_paths,
            refresh,
            make_progress_bar(qgis_application),
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
            project,
            schematisation,
            local,
            raster_paths,
            refresh,
            make_progress_bar(qgis_application),
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
            project,
            schematisation,
            local,
            raster_paths,
            MagicMock(),
            make_progress_bar(qgis_application),
        )

    assert task is None
    task_manager.assert_not_called()
    communication.show_warn.assert_called_once()
    assert "dem.tif" in communication.show_warn.call_args.args[0]


def test_late_upload_progress_after_model_request_is_ignored(
    qgis_application, tmp_path
):
    project, schematisation, local, raster_paths, _ = (
        make_initial_revision_upload_context(tmp_path)
    )
    progress_bar = make_progress_bar(qgis_application)
    loader = Loader(MagicMock())
    with (
        patch("rana_qgis_plugin.loader.get_threedi_api", return_value=object()),
        patch("rana_qgis_plugin.loader.QgsApplication.taskManager"),
        patch.object(loader, "handle_initial_model_requested"),
    ):
        task = loader.save_initial_revision(
            project, schematisation, local, raster_paths, MagicMock(), progress_bar
        )
        task.revision = SimpleNamespace(id=7)
        task.model_requested.emit()
        task.progress_changed.emit("dem.tif", 50, 0, 100)

    assert progress_bar.value() == 33


def test_model_request_completes_and_removes_the_progress_item(
    qgis_application, tmp_path
):
    message_bar = QgsMessageBar()
    iface = MagicMock()
    iface.messageBar.return_value = message_bar
    communication = UICommunication(iface=iface)
    progress_bar = communication.progress_bar("Preparing", maximum=100)
    loader = Loader(communication)

    with patch.object(loader, "start_model_tracker_process", return_value={"id": "p"}):
        loader.handle_initial_model_requested(
            "project", SimpleNamespace(id=1, name="Model"), 7, False, progress_bar
        )

    assert message_bar.items() == []


def test_failed_model_request_also_removes_the_progress_item(
    qgis_application, tmp_path
):
    message_bar = QgsMessageBar()
    iface = MagicMock()
    iface.messageBar.return_value = message_bar
    communication = UICommunication(iface=iface)
    progress_bar = communication.progress_bar("Preparing", maximum=100)
    loader = Loader(communication)

    with patch.object(loader, "start_model_tracker_process", return_value=None):
        loader.handle_initial_model_requested(
            "project", SimpleNamespace(id=1, name="Model"), 7, False, progress_bar
        )

    assert message_bar.items() == []
