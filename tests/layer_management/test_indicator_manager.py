from qgis.core import QgsLayerTreeModel, QgsProject, QgsVectorLayer
from qgis.gui import QgsLayerTreeView

from rana_qgis_plugin.layer_management.dirty_tracking import (
    attach_dirty_tracking,
    clear_dirty,
)
from rana_qgis_plugin.layer_management.indicator_manager import IndicatorManager
from rana_qgis_plugin.layer_management.layer_manager import RanaLayerRef, set_rana_refs


def make_linked_vector_layer(name: str) -> QgsVectorLayer:
    layer = QgsVectorLayer("Point?crs=EPSG:4326", name, "memory")
    set_rana_refs(layer, RanaLayerRef("project", f"{name}.gpkg"))
    attach_dirty_tracking(layer)
    return layer


def test_layer_indicator_added_after_dirty_property_changes(qgis_application):
    project = QgsProject.instance()
    project.clear()
    view = QgsLayerTreeView()
    model = QgsLayerTreeModel(project.layerTreeRoot(), view)
    view.setModel(model)
    manager = IndicatorManager(project, view)
    manager.connect()

    layer = make_linked_vector_layer("linked")
    project.addMapLayer(layer, False)
    node = project.layerTreeRoot().addLayer(layer)

    layer.styleChanged.emit()

    indicators = view.indicators(node)
    assert len(indicators) == 1
    assert indicators[0].toolTip() == "Has unsynced changes to Rana"

    manager.disconnect()
    view.removeIndicator(node, indicators[0])
    indicators[0].deleteLater()
    project.clear()


def test_layer_indicator_removed_after_dirty_property_is_cleared(qgis_application):
    project = QgsProject.instance()
    project.clear()
    view = QgsLayerTreeView()
    model = QgsLayerTreeModel(project.layerTreeRoot(), view)
    view.setModel(model)
    manager = IndicatorManager(project, view)
    manager.connect()

    layer = make_linked_vector_layer("linked")
    project.addMapLayer(layer, False)
    node = project.layerTreeRoot().addLayer(layer)
    layer.startEditing()
    assert layer.commitChanges()

    indicators = view.indicators(node)
    assert len(indicators) == 1
    clear_dirty(layer, "rana/data_dirty")
    assert view.indicators(node) == []

    manager.disconnect()
    project.clear()


def test_non_rana_layer_does_not_receive_indicator(qgis_application):
    project = QgsProject.instance()
    project.clear()
    view = QgsLayerTreeView()
    model = QgsLayerTreeModel(project.layerTreeRoot(), view)
    view.setModel(model)
    manager = IndicatorManager(project, view)
    manager.connect()

    layer = QgsVectorLayer("Point?crs=EPSG:4326", "unlinked", "memory")
    attach_dirty_tracking(layer)
    project.addMapLayer(layer, False)
    node = project.layerTreeRoot().addLayer(layer)
    layer.styleChanged.emit()

    assert view.indicators(node) == []

    manager.disconnect()
    project.clear()
