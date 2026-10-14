from pathlib import Path
from unittest.mock import patch

from osgeo import gdal
from qgis.core import QgsLayerTreeGroup, QgsRasterLayer, QgsVectorLayer

from rana_qgis_plugin.layer_management.close_sync_prompt import (
    build_question,
    collect_dirty_file_groups,
)
from rana_qgis_plugin.layer_management.layer_dirty_flags import DATA_SYNC_STATE_PROPERTY
from rana_qgis_plugin.layer_management.layer_sync_state import LayerSyncState
from rana_qgis_plugin.layer_management.raster_dirty_evaluator import (
    capture_raster_baseline,
)
from tests.layer_management.sync_prompt_helpers import add_file_group, make_linked_layer


def create_test_raster(path: Path) -> None:
    """Create a small valid GeoTIFF for raster prompt tests."""
    path.parent.mkdir(parents=True, exist_ok=True)
    dataset = gdal.GetDriverByName("GTiff").Create(str(path), 2, 2, 1, gdal.GDT_Byte)
    dataset.GetRasterBand(1).WriteRaster(0, 0, 2, 2, b"\x00" * 4)
    dataset = None


def test_collects_style_dirty_rana_file_groups(qgis_application):
    root = QgsLayerTreeGroup()
    dirty = make_linked_layer(
        QgsVectorLayer("Point?crs=EPSG:4326", "dirty", "memory"), "dirty.gpkg"
    )
    clean = make_linked_layer(
        QgsVectorLayer("Point?crs=EPSG:4326", "clean", "memory"), "clean.gpkg"
    )
    dirty.setCustomProperty("rana/style_dirty", True)
    dirty_group = add_file_group(root, "dirty-file", dirty)
    add_file_group(root, "clean-file", clean)

    style_groups, data_groups = collect_dirty_file_groups(root)

    assert style_groups == [dirty_group]
    assert data_groups == []


def test_collects_vector_data_dirty_groups_and_ignores_unknown_raster_data(
    qgis_application,
):
    root = QgsLayerTreeGroup()
    vector = make_linked_layer(
        QgsVectorLayer("Point?crs=EPSG:4326", "vector", "memory"), "vector.gpkg"
    )
    raster = make_linked_layer(
        QgsRasterLayer("/vsimem/nonexistent.tif", "raster"), "raster.tif"
    )
    vector.setCustomProperty(DATA_SYNC_STATE_PROPERTY, LayerSyncState.DIRTY.value)
    raster.setCustomProperty(DATA_SYNC_STATE_PROPERTY, LayerSyncState.DIRTY.value)
    vector_group = add_file_group(root, "vector-file", vector)
    add_file_group(root, "raster-file", raster)

    style_groups, data_groups = collect_dirty_file_groups(root)

    assert style_groups == []
    assert data_groups == [vector_group]


def test_close_prompt_rechecks_raster_source_before_collecting_dirty_groups(
    tmp_path: Path, qgis_application
):
    root = QgsLayerTreeGroup()
    cache_dir = tmp_path / "cache"
    raster_path = cache_dir / "project" / "files" / "dem" / "dem.tif"
    create_test_raster(raster_path)
    raster = make_linked_layer(
        QgsRasterLayer(str(raster_path), "dem", "gdal"), "dem.tif"
    )
    assert isinstance(raster, QgsRasterLayer)
    raster_group = add_file_group(root, "raster-file", raster)

    with patch(
        "rana_qgis_plugin.layer_management.file_fingerprint.rana_cache_dir",
        return_value=str(cache_dir),
    ):
        capture_raster_baseline(raster)
        raster_path.write_bytes(raster_path.read_bytes() + b"changed")

        assert (
            raster.customProperty(DATA_SYNC_STATE_PROPERTY)
            == LayerSyncState.CLEAN.value
        )
        style_groups, data_groups = collect_dirty_file_groups(root)

    assert style_groups == []
    assert data_groups == [raster_group]
    assert raster.customProperty(DATA_SYNC_STATE_PROPERTY) == LayerSyncState.DIRTY.value


def test_close_prompt_ignores_raster_when_source_is_unavailable(qgis_application):
    root = QgsLayerTreeGroup()
    raster = make_linked_layer(
        QgsRasterLayer("/vsimem/missing.tif", "raster"), "raster.tif"
    )
    add_file_group(root, "raster-file", raster)
    raster.setCustomProperty("rana/data_fingerprint", "stored-baseline")
    raster.setCustomProperty(DATA_SYNC_STATE_PROPERTY, LayerSyncState.DIRTY.value)

    style_groups, data_groups = collect_dirty_file_groups(root)

    assert style_groups == []
    assert data_groups == []
    assert (
        raster.customProperty(DATA_SYNC_STATE_PROPERTY) == LayerSyncState.UNKNOWN.value
    )


def test_ignores_dirty_unlinked_layers_and_finds_nested_file_group(qgis_application):
    root = QgsLayerTreeGroup()
    folder = root.addGroup("folder")
    assert folder is not None
    unlinked = QgsVectorLayer("Point?crs=EPSG:4326", "unlinked", "memory")
    unlinked.setCustomProperty("rana/style_dirty", True)
    add_file_group(folder, "unlinked-file", unlinked)

    linked = make_linked_layer(
        QgsVectorLayer("Point?crs=EPSG:4326", "linked", "memory"), "linked.gpkg"
    )
    linked.setCustomProperty("rana/data_sync_state", "dirty")
    linked_group = add_file_group(folder, "linked-file", linked)

    style_groups, data_groups = collect_dirty_file_groups(root)

    assert style_groups == []
    assert data_groups == [linked_group]


def test_file_group_is_listed_once_when_multiple_layers_are_dirty(qgis_application):
    root = QgsLayerTreeGroup()
    group = root.addGroup("multi-layer-file")
    assert group is not None
    first = make_linked_layer(
        QgsVectorLayer("Point?crs=EPSG:4326", "first", "memory"), "multi.gpkg"
    )
    second = make_linked_layer(
        QgsVectorLayer("Point?crs=EPSG:4326", "second", "memory"), "multi.gpkg"
    )
    group.addLayer(first)
    group.addLayer(second)
    first.setCustomProperty("rana/style_dirty", True)
    second.setCustomProperty("rana/style_dirty", True)

    style_groups, data_groups = collect_dirty_file_groups(root)

    assert style_groups == [group]
    assert data_groups == []


def test_single_file_with_only_style_changes_says_style(qgis_application):
    question = build_question(["roads.gpkg"], [])

    assert "unsynced style changes" in question
    assert "data" not in question


def test_single_file_with_only_data_changes_says_data(qgis_application):
    question = build_question([], ["roads.gpkg"])

    assert "unsynced data changes" in question
    assert "style" not in question


def test_single_file_dirty_in_both_ways_says_data_and_style(qgis_application):
    question = build_question(["roads.gpkg"], ["roads.gpkg"])

    assert "unsynced data and style changes" in question
    assert "and/or" not in question


def test_separate_files_per_change_kind_say_data_and_or_style(qgis_application):
    question = build_question(["style.gpkg"], ["data.gpkg"])

    assert "unsynced data and/or style changes" in question
    assert "style.gpkg" in question
    assert "data.gpkg" in question


def test_a_file_dirty_in_both_ways_is_listed_once(qgis_application):
    question = build_question(["roads.gpkg", "water.gpkg"], ["roads.gpkg"])

    assert question.count("roads.gpkg") == 1
