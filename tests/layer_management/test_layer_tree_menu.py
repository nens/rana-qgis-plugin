from contextlib import contextmanager
from typing import cast

from qgis.core import QgsLayerTreeModel, QgsProject, QgsRasterLayer, QgsVectorLayer
from qgis.gui import QgisInterface, QgsLayerTreeView
from qgis.PyQt import sip
from qgis.PyQt.QtWidgets import QMenu

from rana_qgis_plugin.layer_management.layer_manager import RanaLayerRef, set_rana_refs
from rana_qgis_plugin.layer_management.layer_tree_menu import LayerTreeMenuProvider
from rana_qgis_plugin.layer_management.sync_lock import LayerLockRegistry


class FakeInterface:
    def __init__(self, view):
        self.view = view

    def layerTreeView(self):
        return self.view


@contextmanager
def build_menu(project, group, qgis_application):
    """Build the Rana context menu for `group` and tear the view down again.

    The view schedules its own layout work on a Qt timer, so it has to be
    destroyed (and its queued events flushed) while the project's layer tree
    is still alive. Letting it outlive the project crashes QGIS once the timer
    fires against freed tree nodes.
    """
    view = QgsLayerTreeView()
    model = QgsLayerTreeModel(project.layerTreeRoot(), view)
    view.setModel(model)
    view.setCurrentNode(group)
    menu = QMenu()
    provider = LayerTreeMenuProvider(
        cast(QgisInterface, FakeInterface(view)), LayerLockRegistry()
    )
    provider.on_context_menu(menu)
    try:
        yield menu
    finally:
        view.setModel(None)
        sip.delete(view)
        qgis_application.processEvents()


def test_unlinked_dirty_layer_does_not_enable_group_sync(qgis_application):
    project = QgsProject()
    root = project.layerTreeRoot()
    group = root.addGroup("file")
    group.setCustomProperty("rana/project_id", "project")
    linked = QgsVectorLayer("Point?crs=EPSG:4326", "linked", "memory")
    set_rana_refs(linked, RanaLayerRef("project", "file.gpkg"))
    project.addMapLayer(linked, False)
    group.addLayer(linked)
    unlinked = QgsVectorLayer("Point?crs=EPSG:4326", "unlinked", "memory")
    unlinked.setCustomProperty("rana/style_dirty", True)
    unlinked.setCustomProperty("rana/data_sync_state", "dirty")
    project.addMapLayer(unlinked, False)
    group.addLayer(unlinked)
    with build_menu(project, group, qgis_application) as menu:
        actions = {action.text(): action for action in menu.actions() if action.text()}
        assert not actions["Save style to Rana"].isEnabled()
        assert not actions["Save data to Rana"].isEnabled()


def test_raster_unknown_data_keeps_group_data_sync_enabled(qgis_application):
    project = QgsProject()
    root = project.layerTreeRoot()
    group = root.addGroup("file")
    group.setCustomProperty("rana/project_id", "project")
    raster = QgsRasterLayer("/vsimem/nonexistent.tif", "raster")
    set_rana_refs(raster, RanaLayerRef("project", "raster.tif"))
    project.addMapLayer(raster, False)
    group.addLayer(raster)
    with build_menu(project, group, qgis_application) as menu:
        actions = {action.text(): action for action in menu.actions() if action.text()}
        assert not actions["Save style to Rana"].isEnabled()
        assert actions["Save data to Rana"].isEnabled()
