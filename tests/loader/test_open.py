from pathlib import Path
from unittest.mock import patch

from osgeo import gdal
from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer

from rana_qgis_plugin.layer_management.layer_dirty_flags import (
    DATA_FINGERPRINT_PROPERTY,
    DATA_SYNC_STATE_PROPERTY,
    is_data_dirty,
)
from rana_qgis_plugin.layer_management.layer_manager import get_rana_refs
from rana_qgis_plugin.layer_management.layer_sync_state import LayerSyncState
from rana_qgis_plugin.layer_management.raster_dirty_evaluator import (
    evaluate_raster_data_dirty,
)
from rana_qgis_plugin.loader import Loader
from rana_qgis_plugin.utils.qgis import get_qml_path_for_raster


def create_test_raster(path: Path) -> None:
    """Create a tiny valid GeoTIFF for the real layer-opening path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    dataset = gdal.GetDriverByName("GTiff").Create(str(path), 2, 2, 1, gdal.GDT_Byte)
    dataset.GetRasterBand(1).WriteRaster(0, 0, 2, 2, b"\x00" * 4)
    dataset = None


def create_test_vector(path: Path) -> None:
    """Create a minimal GeoPackage with one point layer."""
    from osgeo import ogr, osr

    driver = ogr.GetDriverByName("GPKG")
    dataset = driver.CreateDataSource(str(path))
    spatial_ref = osr.SpatialReference()
    spatial_ref.ImportFromEPSG(4326)
    dataset.CreateLayer("points", spatial_ref, ogr.wkbPoint)
    dataset = None


def test_open_file_captures_and_replaces_raster_baseline(
    tmp_path: Path, qgis_application
):
    project = QgsProject.instance()
    project.clear()
    loader = Loader(None)
    cache_dir = tmp_path / "cache"
    raster_path = cache_dir / "project" / "files" / "dem" / "dem.tif"
    create_test_raster(raster_path)
    project_data = {"id": "project", "name": "Project"}
    file_item = {"id": "dem.tif", "data_type": "raster"}

    with patch(
        "rana_qgis_plugin.layer_management.file_fingerprint.rana_cache_dir",
        return_value=str(cache_dir),
    ):
        # open_file is the callback after the download task has written the file.
        loader.open_file(str(raster_path), project_data, file_item)
        layer = next(iter(project.mapLayers().values()))
        original_baseline = layer.customProperty(DATA_FINGERPRINT_PROPERTY)
        assert original_baseline
        assert evaluate_raster_data_dirty(layer) is LayerSyncState.CLEAN

        # A main-file change makes the old layer dirty. Reopening via the
        # download callback replaces it and captures the downloaded state.
        raster_path.write_bytes(raster_path.read_bytes() + b"changed raster")
        assert evaluate_raster_data_dirty(layer) is LayerSyncState.DIRTY

        old_layer_id = layer.id()
        loader.open_file(str(raster_path), project_data, file_item)
        reopened_layer = next(iter(project.mapLayers().values()))
        assert reopened_layer.id() != old_layer_id
        assert (
            reopened_layer.customProperty(DATA_FINGERPRINT_PROPERTY)
            != original_baseline
        )
        assert evaluate_raster_data_dirty(reopened_layer) is LayerSyncState.CLEAN

    project.clear()


def test_open_file_clears_stale_vector_dirty_flags_from_qml(
    tmp_path: Path, qgis_application
):
    project = QgsProject.instance()
    project.clear()
    loader = Loader(None)
    gpkg_path = tmp_path / "cache" / "project" / "files" / "roads" / "roads.gpkg"
    gpkg_path.parent.mkdir(parents=True)
    create_test_vector(gpkg_path)
    styled_layer = QgsVectorLayer(f"{gpkg_path}|layername=points", "points", "ogr")
    styled_layer.setCustomProperty(DATA_SYNC_STATE_PROPERTY, "dirty")
    styled_layer.setCustomProperty("rana/style_dirty", True)
    styled_layer.saveNamedStyle(str(gpkg_path.parent / "points.qml"))
    project_data = {"id": "project", "name": "Project"}
    file_item = {"id": "roads.gpkg", "data_type": "vector"}

    loader.open_file(str(gpkg_path), project_data, file_item)

    layer = next(iter(project.mapLayers().values()))
    assert get_rana_refs(layer) is not None
    assert not is_data_dirty(layer)
    assert layer.customProperty("rana/style_dirty") is None
    project.clear()


def test_open_file_clears_stale_raster_dirty_flags_from_qml(
    tmp_path: Path, qgis_application
):
    """A raster's sidecar QML must not re-apply stale Rana dirty flags.

    QGIS loads `<stem>.qml` as the layer's default style while constructing
    `QgsRasterLayer`, before any plugin code runs, so a style uploaded while
    it was dirty would otherwise mark every later open dirty again.
    """
    project = QgsProject.instance()
    project.clear()
    loader = Loader(None)
    cache_dir = tmp_path / "cache"
    raster_path = cache_dir / "project" / "files" / "dem" / "dem.tif"
    create_test_raster(raster_path)
    styled_layer = QgsRasterLayer(str(raster_path), "dem.tif")
    styled_layer.setCustomProperty(DATA_SYNC_STATE_PROPERTY, "dirty")
    styled_layer.setCustomProperty("rana/style_dirty", True)
    styled_layer.saveNamedStyle(str(get_qml_path_for_raster(raster_path)))
    del styled_layer
    project_data = {"id": "project", "name": "Project"}
    file_item = {"id": "dem.tif", "data_type": "raster"}

    with patch(
        "rana_qgis_plugin.layer_management.file_fingerprint.rana_cache_dir",
        return_value=str(cache_dir),
    ):
        loader.open_file(str(raster_path), project_data, file_item)

    layer = next(iter(project.mapLayers().values()))
    assert get_rana_refs(layer) is not None
    assert not is_data_dirty(layer)
    assert layer.customProperty("rana/style_dirty") is None
    project.clear()


def test_raster_qml_sidecar_name_matches_between_download_and_open(tmp_path: Path):
    """The download writes the sidecar; the open path strips Rana flags out
    of it. If those names ever disagree the strip silently never runs, while
    QGIS still auto-loads the unstripped file during layer construction.
    """
    raster_path = tmp_path / "dem.tif"

    written_by_download = get_qml_path_for_raster(raster_path)
    read_by_open_path = get_qml_path_for_raster(raster_path)

    assert written_by_download == read_by_open_path == tmp_path / "dem.qml"
    # The name QGIS itself auto-loads is the file stem, not the full filename.
    assert written_by_download.name != f"{raster_path.name}.qml"
