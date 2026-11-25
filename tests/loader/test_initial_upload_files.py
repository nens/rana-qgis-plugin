from unittest.mock import MagicMock, patch

from rana_qgis_plugin.loader import Loader
from rana_qgis_plugin.simulation.utils import UploadFileType
from rana_qgis_plugin.workers.upload_handlers import InitialRevisionUploadHandler


def test_collects_geopackage_and_existing_rasters(tmp_path):
    (tmp_path / "dem.tif").write_bytes(b"")
    raster_paths = {"group": {"dem": "dem.tif"}}

    selected, missing = Loader.select_initial_revision_files(
        "/models/schematisation.gpkg", str(tmp_path), raster_paths
    )

    assert missing == []
    assert selected["geopackage"]["filepath"] == "/models/schematisation.gpkg"
    assert selected["geopackage"]["type"] == UploadFileType.DB
    assert selected["dem"]["filepath"] == str(tmp_path / "dem.tif")
    assert selected["dem"]["type"] == UploadFileType.RASTER


def test_reports_missing_rasters_and_skips_empty_paths(tmp_path):
    raster_paths = {"group": {"dem": "missing.tif", "unused": ""}}

    selected, missing = Loader.select_initial_revision_files(
        "/models/schematisation.gpkg", str(tmp_path), raster_paths
    )

    assert missing == [("dem", "missing.tif")]
    assert "unused" not in selected


def make_handler(task):
    loader = MagicMock()
    progress_bar = MagicMock()
    handler = InitialRevisionUploadHandler(
        loader,
        task,
        {"id": "project"},
        MagicMock(),
        progress_bar,
        MagicMock(),
        "Model",
        MagicMock(),
    )
    return handler, loader, progress_bar


def test_progress_is_ignored_after_model_hand_off():
    task = MagicMock()
    handler, _loader, _progress_bar = make_handler(task)

    with patch(
        "rana_qgis_plugin.workers.upload_handlers.update_step_progress"
    ) as update:
        handler.on_model_requested()
        handler.on_upload_progress("file.gpkg", 50, 0, 10)

    update.assert_not_called()


def test_model_requested_hands_off_to_loader():
    task = MagicMock()
    task.revision.id = 42
    task.upload_specification = {"cb_inherit_templates": True}
    handler, loader, _progress_bar = make_handler(task)

    handler.on_model_requested()

    assert handler.handed_off is True
    loader.handle_initial_model_requested.assert_called_once()
    args = loader.handle_initial_model_requested.call_args.args
    assert args[2] == 42
    assert args[3] is True
