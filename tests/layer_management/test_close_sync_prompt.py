from qgis.core import QgsLayerTreeGroup, QgsMapLayer, QgsRasterLayer, QgsVectorLayer

from rana_qgis_plugin.layer_management.close_sync_prompt import (
    collect_dirty_file_groups,
)
from rana_qgis_plugin.layer_management.layer_manager import RanaLayerRef, set_rana_refs


def make_linked_layer(layer: QgsMapLayer, file_id: str) -> QgsMapLayer:
    set_rana_refs(layer, RanaLayerRef("project", file_id))
    return layer


def add_file_group(
    root: QgsLayerTreeGroup, name: str, layer: QgsMapLayer
) -> QgsLayerTreeGroup:
    group = root.addGroup(name)
    group.addLayer(layer)
    return group


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


def test_collects_vector_data_dirty_groups_and_ignores_raster_data(qgis_application):
    root = QgsLayerTreeGroup()
    vector = make_linked_layer(
        QgsVectorLayer("Point?crs=EPSG:4326", "vector", "memory"), "vector.gpkg"
    )
    raster = make_linked_layer(
        QgsRasterLayer("/vsimem/nonexistent.tif", "raster"), "raster.tif"
    )
    vector.setCustomProperty("rana/data_dirty", True)
    raster.setCustomProperty("rana/data_dirty", True)
    vector_group = add_file_group(root, "vector-file", vector)
    add_file_group(root, "raster-file", raster)

    style_groups, data_groups = collect_dirty_file_groups(root)

    assert style_groups == []
    assert data_groups == [vector_group]


def test_ignores_dirty_unlinked_layers_and_finds_nested_file_group(qgis_application):
    root = QgsLayerTreeGroup()
    folder = root.addGroup("folder")
    unlinked = QgsVectorLayer("Point?crs=EPSG:4326", "unlinked", "memory")
    unlinked.setCustomProperty("rana/style_dirty", True)
    add_file_group(folder, "unlinked-file", unlinked)

    linked = make_linked_layer(
        QgsVectorLayer("Point?crs=EPSG:4326", "linked", "memory"), "linked.gpkg"
    )
    linked.setCustomProperty("rana/data_dirty", True)
    linked_group = add_file_group(folder, "linked-file", linked)

    style_groups, data_groups = collect_dirty_file_groups(root)

    assert style_groups == []
    assert data_groups == [linked_group]


def test_file_group_is_listed_once_when_multiple_layers_are_dirty(qgis_application):
    root = QgsLayerTreeGroup()
    group = root.addGroup("multi-layer-file")
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
