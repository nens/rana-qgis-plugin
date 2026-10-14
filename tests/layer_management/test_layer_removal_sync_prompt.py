from typing import cast

from qgis.core import QgsProject, QgsVectorLayer

from rana_qgis_plugin.layer_management.close_sync_prompt import (
    CONTINUE_WITHOUT_SYNCING,
    SYNC_NOW,
    LayerRemovalSyncPrompt,
    ProjectCloseSyncPrompt,
)
from rana_qgis_plugin.layer_management.layer_tree_menu import LayerTreeMenuProvider
from tests.layer_management.sync_prompt_helpers import (
    ChoiceRecorder,
    SyncRecorder,
    add_file_group,
    make_linked_layer,
)


def make_layer_removal_prompt(project, choice):
    """Build a disconnected `ProjectCloseSyncPrompt` (never True here) plus
    the `LayerRemovalSyncPrompt` under test, matching how they're wired in
    production (the removal prompt always needs a project-close companion to
    check `is_clearing`, even when this test never triggers a project clear).
    """
    communication = ChoiceRecorder(choice)
    sync = SyncRecorder()
    project_close = ProjectCloseSyncPrompt(
        project, cast(LayerTreeMenuProvider, sync), communication
    )
    prompt = LayerRemovalSyncPrompt(
        project, cast(LayerTreeMenuProvider, sync), communication, project_close
    )
    return prompt, communication, sync


def test_removing_dirty_project_layer_prompts_and_dispatches_sync(qgis_application):
    project = QgsProject()
    root = project.layerTreeRoot()
    assert root is not None
    group = root.addGroup("dirty-file")
    assert group is not None
    layer = make_linked_layer(
        QgsVectorLayer("Point?crs=EPSG:4326", "dirty", "memory"), "dirty.gpkg"
    )
    project.addMapLayer(layer, False)
    group.addLayer(layer)
    layer.setCustomProperty("rana/data_sync_state", "dirty")
    prompt, communication, sync = make_layer_removal_prompt(project, SYNC_NOW)
    prompt.connect()

    try:
        project.removeMapLayer(layer.id())
        # Removal reaches the layer tree before the registry signal, so the
        # prompt is batched via a zero-delay timer.
        qgis_application.processEvents()
        assert sync.data_groups == ["dirty.gpkg"]
        assert sync.style_groups == []
    finally:
        prompt.disconnect()


def test_removing_group_with_multiple_dirty_layers_prompts_once(qgis_application):
    project = QgsProject()
    root = project.layerTreeRoot()
    assert root is not None
    group = root.addGroup("multi-layer-file")
    assert group is not None
    first = make_linked_layer(
        QgsVectorLayer("Point?crs=EPSG:4326", "first", "memory"), "multi.gpkg"
    )
    second = make_linked_layer(
        QgsVectorLayer("Point?crs=EPSG:4326", "second", "memory"), "multi.gpkg"
    )
    project.addMapLayer(first, False)
    project.addMapLayer(second, False)
    group.addLayer(first)
    group.addLayer(second)
    first.setCustomProperty("rana/data_sync_state", "dirty")
    second.setCustomProperty("rana/style_dirty", True)
    prompt, communication, sync = make_layer_removal_prompt(project, SYNC_NOW)
    prompt.connect()

    root.removeChildNode(group)
    # Tree-driven group removal batches the prompt via a zero-delay timer.
    qgis_application.processEvents()

    assert len(communication.questions) == 1
    assert sync.data_groups == ["multi.gpkg"]
    assert sync.style_groups == ["multi.gpkg"]
    prompt.disconnect()


def test_tree_removal_clears_prompted_ids_for_removed_sibling_only(qgis_application):
    project = QgsProject()
    root = project.layerTreeRoot()
    assert root is not None
    layers = []
    groups = []
    for name in ("first", "middle", "last"):
        layer = make_linked_layer(
            QgsVectorLayer("Point?crs=EPSG:4326", name, "memory"), f"{name}.gpkg"
        )
        layer.setCustomProperty("rana/data_sync_state", "dirty")
        project.addMapLayer(layer, False)
        groups.append(add_file_group(root, f"{name}-file", layer))
        layers.append(layer)

    prompt, _, _ = make_layer_removal_prompt(project, CONTINUE_WITHOUT_SYNCING)
    prompt.connect()
    first_id, middle_id, last_id = (layer.id() for layer in layers)
    prompt._prompted_layer_ids.update({first_id, middle_id, last_id})

    root.removeChildNode(groups[1])
    qgis_application.processEvents()

    assert prompt._prompted_layer_ids == {first_id, last_id}
    prompt.disconnect()


def test_disconnect_cancels_pending_prompt_and_discards_style_snapshot(
    qgis_application,
):
    project = QgsProject()
    root = project.layerTreeRoot()
    assert root is not None
    layer = make_linked_layer(
        QgsVectorLayer("Point?crs=EPSG:4326", "dirty", "memory"), "dirty.gpkg"
    )
    layer.setCustomProperty("rana/style_dirty", True)
    group = add_file_group(root, "dirty-file", layer)
    prompt, communication, sync = make_layer_removal_prompt(project, SYNC_NOW)
    prompt.connect()

    root.removeChildNode(group)
    assert prompt._flush_timer.isActive()
    assert sync.captured_style_items

    prompt.disconnect()
    qgis_application.processEvents()

    assert communication.questions == []
    assert all(item.layer_source.discarded for item in sync.captured_style_items)


def test_removing_parent_group_with_multiple_dirty_file_groups_prompts_once(
    qgis_application,
):
    project = QgsProject()
    root = project.layerTreeRoot()
    assert root is not None
    parent_group = root.addGroup("parent")
    assert parent_group is not None

    first = make_linked_layer(
        QgsVectorLayer("Point?crs=EPSG:4326", "first", "memory"), "first.gpkg"
    )
    second = make_linked_layer(
        QgsVectorLayer("Point?crs=EPSG:4326", "second", "memory"), "second.gpkg"
    )
    project.addMapLayer(first, False)
    project.addMapLayer(second, False)
    add_file_group(parent_group, "first-file", first)
    add_file_group(parent_group, "second-file", second)
    first.setCustomProperty("rana/data_sync_state", "dirty")
    second.setCustomProperty("rana/style_dirty", True)
    prompt, communication, sync = make_layer_removal_prompt(project, SYNC_NOW)
    prompt.connect()

    try:
        root.removeChildNode(parent_group)
        # Tree-driven group removal batches the prompt via a zero-delay timer.
        qgis_application.processEvents()

        assert len(communication.questions) == 1
        assert sync.data_groups == ["first.gpkg"]
        assert sync.style_groups == ["second.gpkg"]
    finally:
        prompt.disconnect()


def test_removal_prompt_is_suppressed_while_project_is_clearing(qgis_application):
    project = QgsProject()
    root = project.layerTreeRoot()
    assert root is not None
    layer = make_linked_layer(
        QgsVectorLayer("Point?crs=EPSG:4326", "dirty", "memory"), "dirty.gpkg"
    )
    project.addMapLayer(layer, False)
    group = root.addGroup("dirty-file")
    assert group is not None
    group.addLayer(layer)
    layer.setCustomProperty("rana/data_sync_state", "dirty")

    communication = ChoiceRecorder(CONTINUE_WITHOUT_SYNCING)
    sync = SyncRecorder()
    project_close = ProjectCloseSyncPrompt(
        project, cast(LayerTreeMenuProvider, sync), communication
    )
    removal = LayerRemovalSyncPrompt(
        project, cast(LayerTreeMenuProvider, sync), communication, project_close
    )
    project_close.is_clearing = True
    removal.connect()

    try:
        project.removeMapLayer(layer.id())
        qgis_application.processEvents()
        assert communication.questions == []
        assert sync.data_groups == []
        assert sync.style_groups == []
    finally:
        removal.disconnect()
