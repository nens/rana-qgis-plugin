from qgis.core import QgsLayerTreeModel, QgsProject, QgsVectorLayer
from qgis.gui import QgsLayerTreeView

from rana_qgis_plugin.layer_management.dirty_tracking import (
    attach_dirty_tracking,
    clear_dirty,
)
from rana_qgis_plugin.layer_management.indicator_manager import IndicatorManager
from rana_qgis_plugin.layer_management.layer_manager import (
    RanaLayerRef,
    clear_rana_refs,
    set_rana_refs,
)


def make_linked_vector_layer(name: str) -> QgsVectorLayer:
    layer = QgsVectorLayer("Point?crs=EPSG:4326", name, "memory")
    set_rana_refs(layer, RanaLayerRef("project", f"{name}.gpkg"))
    attach_dirty_tracking(layer)
    return layer


def make_vector_layer(name: str) -> QgsVectorLayer:
    layer = QgsVectorLayer("Point?crs=EPSG:4326", name, "memory")
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
    root = project.layerTreeRoot()
    assert root is not None
    node = root.addLayer(layer)
    layer.styleChanged.emit()

    assert view.indicators(node) == []

    manager.disconnect()
    project.clear()


def test_layer_linked_after_add_updates_layer_and_ancestor_indicators(
    qgis_application,
):
    """Linking an already-tracked dirty layer adds its badge and unlinking
    removes it, while ancestors retain badges for other dirty descendants.
    """
    project = QgsProject.instance()
    project.clear()
    view, manager = make_indicator_manager(project)
    root = project.layerTreeRoot()
    group = root.addGroup("files")
    other_layer = make_linked_vector_layer("other-dirty")
    other_layer.setCustomProperty("rana/style_dirty", True)
    project.addMapLayer(other_layer, False)
    other_node = group.addLayer(other_layer)
    layer = make_vector_layer("linked-later")
    layer.setCustomProperty("rana/data_dirty", True)
    project.addMapLayer(layer, False)
    node = group.addLayer(layer)

    assert len(view.indicators(other_node)) == 1
    assert len(view.indicators(group)) == 1
    set_rana_refs(layer, RanaLayerRef("project", "linked-later.gpkg"))

    assert len(view.indicators(node)) == 1
    assert len(view.indicators(group)) == 1
    assert len(view.indicators(root)) == 1

    clear_rana_refs(layer)
    assert layer.customProperty("rana/data_dirty") is True
    assert view.indicators(node) == []
    assert len(view.indicators(other_node)) == 1
    assert len(view.indicators(group)) == 1

    clear_dirty(other_layer, "rana/style_dirty")
    assert view.indicators(other_node) == []
    assert view.indicators(group) == []
    assert view.indicators(root) == []

    manager.disconnect()
    project.clear()


def test_tracking_initially_refreshes_already_dirty_added_layer(qgis_application):
    """An already-dirty layer gets layer and group badges when its node is added."""
    project = QgsProject.instance()
    project.clear()
    view, manager = make_indicator_manager(project)
    root = project.layerTreeRoot()
    group = root.addGroup("files")
    layer = make_linked_vector_layer("already-dirty")
    layer.setCustomProperty("rana/style_dirty", True)

    project.addMapLayer(layer, False)
    node = group.addLayer(layer)

    assert len(view.indicators(node)) == 1
    assert len(view.indicators(group)) == 1

    manager.disconnect()
    project.clear()


def test_removing_unlinked_tracked_layer_disconnects_its_property_slot(
    qgis_application,
):
    """Removing a tracked but unlinked layer also releases its signal slot."""
    project = QgsProject.instance()
    project.clear()
    _, manager = make_indicator_manager(project)
    layer = make_vector_layer("unlinked")
    layer_id = layer.id()
    project.addMapLayer(layer)

    assert layer_id in manager._tracked_layers

    project.removeMapLayer(layer_id)

    assert layer_id not in manager._tracked_layers
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
