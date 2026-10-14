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


def make_indicator_manager(project: QgsProject):
    view = QgsLayerTreeView()
    model = QgsLayerTreeModel(project.layerTreeRoot(), view)
    view.setModel(model)
    manager = IndicatorManager(project, view)
    manager.connect()
    return view, manager


def test_layer_indicator_added_after_dirty_property_changes(qgis_application):
    project = QgsProject.instance()
    project.clear()
    view, manager = make_indicator_manager(project)

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
    view, manager = make_indicator_manager(project)

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
    view, manager = make_indicator_manager(project)

    layer = QgsVectorLayer("Point?crs=EPSG:4326", "unlinked", "memory")
    attach_dirty_tracking(layer)
    project.addMapLayer(layer, False)
    node = project.layerTreeRoot().addLayer(layer)
    layer.styleChanged.emit()

    assert view.indicators(node) == []

    manager.disconnect()
    project.clear()


def test_group_indicator_remains_until_all_dirty_children_are_clean(qgis_application):
    project = QgsProject.instance()
    project.clear()
    view, manager = make_indicator_manager(project)
    root = project.layerTreeRoot()
    group = root.addGroup("files")
    first_layer = make_linked_vector_layer("first")
    second_layer = make_linked_vector_layer("second")
    project.addMapLayer(first_layer, False)
    project.addMapLayer(second_layer, False)
    first_node = group.addLayer(first_layer)
    second_node = group.addLayer(second_layer)

    first_layer.styleChanged.emit()
    second_layer.styleChanged.emit()
    assert len(view.indicators(first_node)) == 1
    assert len(view.indicators(second_node)) == 1
    assert len(view.indicators(group)) == 1
    assert len(view.indicators(root)) == 1

    clear_dirty(first_layer, "rana/style_dirty")
    assert len(view.indicators(group)) == 1
    assert len(view.indicators(root)) == 1

    clear_dirty(second_layer, "rana/style_dirty")
    assert view.indicators(first_node) == []
    assert view.indicators(second_node) == []
    assert view.indicators(group) == []
    assert view.indicators(root) == []

    manager.disconnect()
    project.clear()


def test_removed_layer_detaches_layer_and_group_indicators(qgis_application):
    project = QgsProject.instance()
    project.clear()
    view, manager = make_indicator_manager(project)
    root = project.layerTreeRoot()
    group = root.addGroup("files")
    layer = make_linked_vector_layer("linked")
    project.addMapLayer(layer, False)
    node = group.addLayer(layer)
    layer.styleChanged.emit()
    assert len(view.indicators(node)) == 1
    assert len(view.indicators(group)) == 1

    group.removeChildNode(node)

    assert view.indicators(group) == []
    assert layer.id() not in manager._tracked_layers
    manager.disconnect()
    project.clear()


def test_disconnect_removes_managed_indicators(qgis_application):
    project = QgsProject.instance()
    project.clear()
    view, manager = make_indicator_manager(project)
    layer = make_linked_vector_layer("linked")
    project.addMapLayer(layer, False)
    group = project.layerTreeRoot().addGroup("files")
    node = group.addLayer(layer)
    layer.styleChanged.emit()
    assert len(view.indicators(node)) == 1
    assert len(view.indicators(group)) == 1

    manager.disconnect()

    assert view.indicators(node) == []
    assert view.indicators(group) == []
    layer.styleChanged.emit()
    assert view.indicators(node) == []
    project.clear()
