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


def make_project_close_prompt(project, choice):
    communication = ChoiceRecorder(choice)
    sync = SyncRecorder()
    prompt = ProjectCloseSyncPrompt(
        project, cast(LayerTreeMenuProvider, sync), communication
    )
    return prompt, communication, sync


def test_project_clear_skips_prompt_when_there_are_no_dirty_layers(qgis_application):
    project = QgsProject()
    root = project.layerTreeRoot()
    assert root is not None
    prompt, communication, sync = make_project_close_prompt(project, SYNC_NOW)
    prompt.connect()

    try:
        project.clear()
        assert communication.questions == []
        assert sync.style_groups == []
        assert sync.data_groups == []
    finally:
        prompt.disconnect()


def test_continue_without_syncing_does_not_dispatch_uploads(qgis_application):
    project = QgsProject()
    root = project.layerTreeRoot()
    assert root is not None
    layer = make_linked_layer(
        QgsVectorLayer("Point?crs=EPSG:4326", "dirty", "memory"), "dirty.gpkg"
    )
    layer.setCustomProperty("rana/style_dirty", True)
    add_file_group(root, "dirty-file", layer)
    prompt, communication, sync = make_project_close_prompt(
        project, CONTINUE_WITHOUT_SYNCING
    )
    prompt.connect()

    try:
        project.clear()
        assert len(communication.questions) == 1
        title, question, choices = communication.questions[0]
        assert title == "Unsynced changes"
        assert "dirty.gpkg" in question
        assert choices == (SYNC_NOW, CONTINUE_WITHOUT_SYNCING)
        assert sync.style_groups == []
        assert sync.data_groups == []
    finally:
        prompt.disconnect()


def test_continue_without_syncing_releases_captured_style_snapshots(qgis_application):
    project = QgsProject()
    root = project.layerTreeRoot()
    assert root is not None
    layer = make_linked_layer(
        QgsVectorLayer("Point?crs=EPSG:4326", "dirty", "memory"), "dirty.gpkg"
    )
    layer.setCustomProperty("rana/style_dirty", True)
    add_file_group(root, "dirty-file", layer)
    prompt, communication, sync = make_project_close_prompt(
        project, CONTINUE_WITHOUT_SYNCING
    )
    prompt.connect()

    try:
        project.clear()
        assert sync.captured_style_items
        assert all(item.layer_source.discarded for item in sync.captured_style_items)
    finally:
        prompt.disconnect()


def test_sync_now_keeps_captured_style_snapshots_for_the_upload(qgis_application):
    project = QgsProject()
    root = project.layerTreeRoot()
    assert root is not None
    layer = make_linked_layer(
        QgsVectorLayer("Point?crs=EPSG:4326", "dirty", "memory"), "dirty.gpkg"
    )
    layer.setCustomProperty("rana/style_dirty", True)
    add_file_group(root, "dirty-file", layer)
    prompt, communication, sync = make_project_close_prompt(project, SYNC_NOW)
    prompt.connect()

    try:
        project.clear()
        assert sync.captured_style_items
        assert not any(
            item.layer_source.discarded for item in sync.captured_style_items
        )
    finally:
        prompt.disconnect()


def test_project_clear_snapshots_styles_before_prompting(qgis_application):
    project = QgsProject()
    root = project.layerTreeRoot()
    assert root is not None
    layer = make_linked_layer(
        QgsVectorLayer("Point?crs=EPSG:4326", "dirty", "memory"), "dirty.gpkg"
    )
    layer.setCustomProperty("rana/style_dirty", True)
    add_file_group(root, "dirty-file", layer)
    prompt, communication, sync = make_project_close_prompt(project, SYNC_NOW)
    prompt.connect()

    try:
        project.clear()
        # The upload task runs after the project is gone, so the close path
        # must never hand over live layer references.
        assert sync.capture_for_close == [True]
    finally:
        prompt.disconnect()


def test_sync_now_routes_each_dirty_group_to_its_own_sync_type(qgis_application):
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
    data_layer.setCustomProperty("rana/data_sync_state", "dirty")
    add_file_group(root, "style-file", style_layer)
    add_file_group(root, "data-file", data_layer)
    prompt, communication, sync = make_project_close_prompt(project, SYNC_NOW)
    prompt.connect()

    try:
        project.clear()
        assert sync.style_groups == ["style.gpkg"]
        assert sync.data_groups == ["data.gpkg"]
    finally:
        prompt.disconnect()


def test_prompt_reports_change_kinds_separately_on_project_clear(qgis_application):
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
    data_layer.setCustomProperty("rana/data_sync_state", "dirty")
    add_file_group(root, "style-file", style_layer)
    add_file_group(root, "data-file", data_layer)
    prompt, communication, sync = make_project_close_prompt(
        project, CONTINUE_WITHOUT_SYNCING
    )
    prompt.connect()

    try:
        project.clear()
        _, question, _ = communication.questions[0]
        assert "unsynced data and/or style changes" in question
    finally:
        prompt.disconnect()


def test_prompt_says_style_only_when_just_the_style_is_dirty(qgis_application):
    project = QgsProject()
    root = project.layerTreeRoot()
    assert root is not None
    layer = make_linked_layer(
        QgsVectorLayer("Point?crs=EPSG:4326", "style", "memory"), "style.gpkg"
    )
    layer.setCustomProperty("rana/style_dirty", True)
    add_file_group(root, "style-file", layer)
    prompt, communication, sync = make_project_close_prompt(
        project, CONTINUE_WITHOUT_SYNCING
    )
    prompt.connect()

    try:
        project.clear()
        _, question, _ = communication.questions[0]
        assert "unsynced style changes" in question
    finally:
        prompt.disconnect()


def test_is_clearing_flag_is_set_during_the_prompt_and_reset_after_clear(
    qgis_application,
):
    project = QgsProject()
    root = project.layerTreeRoot()
    assert root is not None
    layer = make_linked_layer(
        QgsVectorLayer("Point?crs=EPSG:4326", "dirty", "memory"), "dirty.gpkg"
    )
    layer.setCustomProperty("rana/style_dirty", True)
    add_file_group(root, "dirty-file", layer)
    prompt, communication, sync = make_project_close_prompt(project, SYNC_NOW)
    removal = LayerRemovalSyncPrompt(
        project, cast(LayerTreeMenuProvider, sync), communication, prompt
    )
    prompt.connect()
    removal.connect()

    try:
        assert prompt.is_clearing is False
        project.clear()
        assert len(communication.questions) == 1
        assert prompt.is_clearing is False
    finally:
        removal.disconnect()
        prompt.disconnect()
