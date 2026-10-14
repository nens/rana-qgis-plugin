from typing import cast

from qgis.core import (
    QgsLayerTreeGroup,
    QgsMapLayer,
    QgsProject,
    QgsRasterLayer,
    QgsVectorLayer,
)

from rana_qgis_plugin.layer_management.close_sync_prompt import (
    CONTINUE_WITHOUT_SYNCING,
    SYNC_NOW,
    CloseSyncPrompt,
    collect_dirty_file_groups,
)
from rana_qgis_plugin.layer_management.layer_manager import RanaLayerRef, set_rana_refs
from rana_qgis_plugin.layer_management.layer_tree_menu import LayerTreeMenuProvider


def make_linked_layer(layer: QgsMapLayer, file_id: str) -> QgsMapLayer:
    set_rana_refs(layer, RanaLayerRef("project", file_id))
    return layer


def add_file_group(
    root: QgsLayerTreeGroup, name: str, layer: QgsMapLayer
) -> QgsLayerTreeGroup:
    group = root.addGroup(name)
    assert group is not None
    group.addLayer(layer)
    return group


class ChoiceRecorder:
    def __init__(self, choice: str):
        self.choice = choice
        self.questions = []

    def custom_ask(self, parent, title, question, *choices):
        self.questions.append((title, question, choices))
        return self.choice


class SyncRecorder:
    def __init__(self):
        self.style_groups = []
        self.data_groups = []

    def save_style(self, groups):
        self.style_groups.extend(groups)

    def save_data(self, groups):
        self.data_groups.extend(groups)


def make_close_prompt(project, choice):
    communication = ChoiceRecorder(choice)
    sync = SyncRecorder()
    prompt = CloseSyncPrompt(project, cast(LayerTreeMenuProvider, sync), communication)
    return prompt, communication, sync


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
    assert folder is not None
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


def test_project_clear_skips_prompt_when_there_are_no_dirty_layers(qgis_application):
    project = QgsProject()
    root = project.layerTreeRoot()
    assert root is not None
    prompt, communication, sync = make_close_prompt(project, SYNC_NOW)
    prompt.connect()

    project.clear()

    assert communication.questions == []
    assert sync.style_groups == []
    assert sync.data_groups == []
    prompt.disconnect()


def test_continue_without_syncing_does_not_dispatch_uploads(qgis_application):
    project = QgsProject()
    root = project.layerTreeRoot()
    assert root is not None
    layer = make_linked_layer(
        QgsVectorLayer("Point?crs=EPSG:4326", "dirty", "memory"), "dirty.gpkg"
    )
    layer.setCustomProperty("rana/style_dirty", True)
    group = add_file_group(root, "dirty-file", layer)
    group_name = group.name()
    prompt, communication, sync = make_close_prompt(project, CONTINUE_WITHOUT_SYNCING)
    prompt.connect()

    project.clear()

    assert len(communication.questions) == 1
    title, question, choices = communication.questions[0]
    assert title == "Unsynced changes"
    assert group_name in question
    assert choices == (SYNC_NOW, CONTINUE_WITHOUT_SYNCING)
    assert sync.style_groups == []
    assert sync.data_groups == []
    prompt.disconnect()


def test_sync_now_dispatches_only_dirty_groups_by_sync_type(qgis_application):
    project = QgsProject()
    root = project.layerTreeRoot()
    assert root is not None
    style_layer = make_linked_layer(
        QgsVectorLayer("Point?crs=EPSG:4326", "style", "memory"), "style.gpkg"
    )
    data_layer = make_linked_layer(
        QgsVectorLayer("Point?crs=EPSG:4326", "data", "memory"), "data.gpkg"
    )
    style_layer.setCustomProperty("rana/style_dirty", True)
    data_layer.setCustomProperty("rana/data_dirty", True)
    style_group = add_file_group(root, "style-file", style_layer)
    data_group = add_file_group(root, "data-file", data_layer)
    prompt, communication, sync = make_close_prompt(project, SYNC_NOW)
    prompt.connect()

    project.clear()

    assert len(communication.questions) == 1
    assert sync.style_groups == [style_group]
    assert sync.data_groups == [data_group]
    prompt.disconnect()
