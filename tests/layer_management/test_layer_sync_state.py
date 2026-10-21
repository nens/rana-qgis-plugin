import pytest
from qgis.core import QgsMapLayer, QgsRasterLayer, QgsVectorLayer

from rana_qgis_plugin.layer_management.layer_manager import RanaLayerRef, set_rana_refs
from rana_qgis_plugin.layer_management.layer_sync_state import (
    LayerSyncState,
    has_unsynced_style,
    layer_sync_state,
    should_badge,
)


@pytest.mark.parametrize("layer_type", ["vector", "raster"])
@pytest.mark.parametrize("linked", [False, True])
@pytest.mark.parametrize("data_dirty", [False, True])
@pytest.mark.parametrize("style_dirty", [False, True])
def test_consumer_dirty_state(
    qgis_application,
    layer_type: str,
    linked: bool,
    data_dirty: bool,
    style_dirty: bool,
):
    if layer_type == "raster":
        layer: QgsMapLayer = QgsRasterLayer("/vsimem/nonexistent.tif", "test")
    else:
        layer = QgsVectorLayer("Point?crs=EPSG:4326", "test", "memory")
    if linked:
        set_rana_refs(layer, RanaLayerRef("project", "test.gpkg"))
    if data_dirty:
        layer.setCustomProperty("rana/data_dirty", True)
    if style_dirty:
        layer.setCustomProperty("rana/style_dirty", True)

    expected_dirty_data = (
        LayerSyncState.CLEAN
        if not linked
        else LayerSyncState.UNKNOWN
        if layer_type == "raster"
        else LayerSyncState.DIRTY
        if data_dirty
        else LayerSyncState.CLEAN
    )
    expected_dirty_style = linked and style_dirty

    assert layer_sync_state(layer) is expected_dirty_data
    assert has_unsynced_style(layer) is expected_dirty_style
    assert should_badge(layer) is (
        expected_dirty_style or expected_dirty_data is LayerSyncState.DIRTY
    )


def test_raster_data_state_is_unknown(qgis_application):
    raster = QgsRasterLayer("/vsimem/nonexistent.tif", "raster")
    set_rana_refs(raster, RanaLayerRef("project", "raster.tif"))
    raster.setCustomProperty("rana/data_dirty", True)

    assert layer_sync_state(raster) is LayerSyncState.UNKNOWN
