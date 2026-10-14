import os
from pathlib import Path
from unittest.mock import patch

from osgeo import gdal
from qgis.core import QgsProject, QgsRasterLayer

from rana_qgis_plugin.layer_management.layer_dirty_flags import (
    DATA_FINGERPRINT_PROPERTY,
    DATA_SYNC_STATE_PROPERTY,
)
from rana_qgis_plugin.layer_management.layer_manager import RanaLayerRef, set_rana_refs
from rana_qgis_plugin.layer_management.layer_sync_state import LayerSyncState
from rana_qgis_plugin.layer_management.raster_dirty_evaluator import (
    capture_raster_baseline,
    evaluate_raster_data_dirty,
)
from rana_qgis_plugin.layer_management.raster_watch import RasterWatch


def create_test_raster(path: Path) -> None:
    """Create a tiny valid GeoTIFF for watcher tests."""
    path.parent.mkdir(parents=True, exist_ok=True)
    dataset = gdal.GetDriverByName("GTiff").Create(str(path), 2, 2, 1, gdal.GDT_Byte)
    dataset.GetRasterBand(1).WriteRaster(0, 0, 2, 2, b"\x00" * 4)
    dataset = None


def add_linked_raster(project: QgsProject, raster_path: Path) -> QgsRasterLayer:
    layer = QgsRasterLayer(str(raster_path), raster_path.name, "gdal")
    set_rana_refs(layer, RanaLayerRef("project", raster_path.name))
    project.addMapLayer(layer)
    return layer


def patch_cache_dir(cache_dir: Path):
    """Redirect the configured raster cache root to the temporary directory."""
    return patch(
        "rana_qgis_plugin.layer_management.file_fingerprint.rana_cache_dir",
        return_value=str(cache_dir),
    )


def test_connect_tracks_existing_rasters_without_creating_missing_baselines(
    tmp_path: Path, qgis_application
):
    project = QgsProject.instance()
    assert project is not None
    project.clear()
    raster_path = tmp_path / "dem.tif"
    create_test_raster(raster_path)
    layer = add_linked_raster(project, raster_path)
    watch = RasterWatch(project)

    with patch_cache_dir(tmp_path):
        watch.connect()
        assert layer.id() in watch._layers
        assert watch._layer_paths[layer.id()] == raster_path.resolve()
        assert str(raster_path) in watch._watcher.files()
        assert not watch._watcher.directories()

        watch.evaluate_pending_layers()
        assert layer.customProperty(DATA_FINGERPRINT_PROPERTY) is None
        assert (
            layer.customProperty(DATA_SYNC_STATE_PROPERTY)
            == LayerSyncState.UNKNOWN.value
        )
        assert evaluate_raster_data_dirty(layer) is LayerSyncState.UNKNOWN

        watch.disconnect()
        assert not watch._watcher.files()
        assert not watch._watcher.directories()
    project.clear()


def test_main_file_change_is_evaluated(tmp_path: Path, qgis_application):
    project = QgsProject.instance()
    assert project is not None
    project.clear()
    raster_path = tmp_path / "dem.tif"
    create_test_raster(raster_path)
    layer = add_linked_raster(project, raster_path)
    watch = RasterWatch(project)

    with patch_cache_dir(tmp_path):
        capture_raster_baseline(layer)
        watch.connect()

        raster_path.write_bytes(raster_path.read_bytes() + b"updated")
        watch.on_path_changed(str(raster_path))
        assert layer.id() in watch._pending_layer_ids
        watch.evaluate_pending_layers()
        assert evaluate_raster_data_dirty(layer) is LayerSyncState.DIRTY

        watch.disconnect()
    project.clear()


def test_atomic_replacement_at_same_path_refreshes_file_watch_and_evaluates(
    tmp_path: Path, qgis_application
):
    project = QgsProject.instance()
    assert project is not None
    project.clear()
    raster_path = tmp_path / "dem.tif"
    create_test_raster(raster_path)
    layer = add_linked_raster(project, raster_path)
    watch = RasterWatch(project)

    with patch_cache_dir(tmp_path):
        capture_raster_baseline(layer)
        watch.connect()

        replacement = tmp_path / "dem.new.tif"
        create_test_raster(replacement)
        os.replace(replacement, raster_path)
        watch.on_path_changed(str(raster_path))
        assert str(raster_path) in watch._watcher.files()
        watch.evaluate_pending_layers()
        assert evaluate_raster_data_dirty(layer) is LayerSyncState.DIRTY

    watch.disconnect()
    project.clear()


def test_renamed_or_removed_source_stops_tracking(tmp_path: Path, qgis_application):
    project = QgsProject.instance()
    assert project is not None
    project.clear()
    raster_path = tmp_path / "dem.tif"
    create_test_raster(raster_path)
    layer = add_linked_raster(project, raster_path)
    watch = RasterWatch(project)

    with patch_cache_dir(tmp_path):
        watch.connect()
        layer_id = layer.id()
        renamed_path = tmp_path / "dem-renamed.tif"
        raster_path.rename(renamed_path)

        # An event from a removed file has no path to re-register, so tracking
        # for the layer's now-missing source is released.
        watch.on_path_changed(str(raster_path))
        assert layer_id not in watch._layers
        assert layer_id not in watch._layer_paths
        assert not watch._watcher.files()
        assert not watch._watcher.directories()

        watch.disconnect()
    project.clear()


def test_notifications_debounce_and_layer_removal_cleans_watches(
    tmp_path: Path, qgis_application
):
    project = QgsProject.instance()
    assert project is not None
    project.clear()
    raster_path = tmp_path / "dem.tif"
    create_test_raster(raster_path)
    layer = add_linked_raster(project, raster_path)
    watch = RasterWatch(project, debounce_ms=0)
    with patch_cache_dir(tmp_path):
        capture_raster_baseline(layer)
        watch.connect()
        layer_id = layer.id()
        raster_path.write_bytes(raster_path.read_bytes() + b"updated")
        watch.on_path_changed(str(raster_path))
        watch.on_path_changed(str(raster_path))
        assert watch._pending_layer_ids == {layer_id}

        qgis_application.processEvents()
        assert watch._pending_layer_ids == set()
        assert evaluate_raster_data_dirty(layer) is LayerSyncState.DIRTY

        project.removeMapLayer(layer_id)
        assert layer_id not in watch._layers
        assert layer_id not in watch._pending_layer_ids
        assert not watch._watcher.files()
        assert not watch._watcher.directories()

        remaining_layer = add_linked_raster(project, raster_path)
        assert remaining_layer.id() in watch._layers
        assert watch._watcher.files()
        assert not watch._watcher.directories()
        watch.disconnect()
        assert not watch._layers
        assert not watch._watcher.files()
        assert not watch._watcher.directories()
    project.clear()
