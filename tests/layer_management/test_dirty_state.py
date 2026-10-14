import pytest
from qgis.core import QgsMapLayer, QgsRasterLayer, QgsVectorLayer

from rana_qgis_plugin.layer_management.dirty_state import (
    DataDirtyState,
    data_dirty_state,
    has_unsynced_style,
    should_badge,
)
from rana_qgis_plugin.layer_management.layer_manager import RanaLayerRef, set_rana_refs


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
        DataDirtyState.CLEAN
        if not linked
        else DataDirtyState.UNKNOWN
        if layer_type == "raster"
        else DataDirtyState.DIRTY
        if data_dirty
        else DataDirtyState.CLEAN
    )
    expected_dirty_style = linked and style_dirty

    assert data_dirty_state(layer) is expected_dirty_data
    assert has_unsynced_style(layer) is expected_dirty_style
    assert should_badge(layer) is (
        expected_dirty_style or expected_dirty_data is DataDirtyState.DIRTY
    )


def test_raster_data_state_is_unknown(qgis_application):
    raster = QgsRasterLayer("/vsimem/nonexistent.tif", "raster")
    set_rana_refs(raster, RanaLayerRef("project", "raster.tif"))
    raster.setCustomProperty("rana/data_dirty", True)

    assert data_dirty_state(raster) is DataDirtyState.UNKNOWN
