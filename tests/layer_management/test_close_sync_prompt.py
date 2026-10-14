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


class FakeLayerSource:
    def __init__(self):
        self.discarded = False

    def discard(self):
        self.discarded = True


class FakeStyleItem:
    def __init__(self, name: str):
        self.name = name
        self.layer_source = FakeLayerSource()


class SyncRecorder:
    def __init__(self):
        self.style_groups = []
        self.data_groups = []
        self.captured_style_items: list[FakeStyleItem] = []
        self.capture_for_close: list[bool] = []

    def capture_style_items(self, groups, for_close: bool = False):
        self.capture_for_close.append(for_close)
        items = [FakeStyleItem(group.name()) for group in groups]
        self.captured_style_items.extend(items)
        return items

    def dispatch_style_items(self, items):
        self.style_groups.extend(item.name for item in items)

    def capture_data_items(self, groups):
        return [group.name() for group in groups]

    def dispatch_data_items(self, items):
        self.data_groups.extend(items)


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
    group = add_file_group(root, "dirty-file", layer)
    group_name = group.name()
    prompt, communication, sync = make_close_prompt(project, CONTINUE_WITHOUT_SYNCING)
    prompt.connect()

    try:
        project.clear()
        assert len(communication.questions) == 1
        title, question, choices = communication.questions[0]
        assert title == "Unsynced changes"
        assert group_name in question
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
    prompt, communication, sync = make_close_prompt(project, CONTINUE_WITHOUT_SYNCING)
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
    prompt, communication, sync = make_close_prompt(project, SYNC_NOW)
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
    prompt, communication, sync = make_close_prompt(project, SYNC_NOW)
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
    data_layer.setCustomProperty("rana/data_dirty", True)
    style_group = add_file_group(root, "style-file", style_layer)
    data_group = add_file_group(root, "data-file", data_layer)
    style_group_name = style_group.name()
    data_group_name = data_group.name()
    prompt, communication, sync = make_close_prompt(project, SYNC_NOW)
    prompt.connect()

    try:
        project.clear()
        assert sync.style_groups == [style_group_name]
        assert sync.data_groups == [data_group_name]
    finally:
        prompt.disconnect()


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
    group_name = group.name()
    layer.setCustomProperty("rana/data_dirty", True)
    prompt, communication, sync = make_close_prompt(project, SYNC_NOW)
    prompt.connect()

    try:
        project.removeMapLayer(layer.id())
        # Removal reaches the layer tree before the registry signal, so the
        # prompt is batched via a zero-delay timer.
        qgis_application.processEvents()
        assert sync.data_groups == [group_name]
        assert sync.style_groups == []
    finally:
        prompt.disconnect()


def test_removing_group_with_multiple_dirty_layers_prompts_once(qgis_application):
    project = QgsProject()
    root = project.layerTreeRoot()
    assert root is not None
    group = root.addGroup("multi-layer-file")
    assert group is not None
    group_name = group.name()
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
    first.setCustomProperty("rana/data_dirty", True)
    second.setCustomProperty("rana/style_dirty", True)
    prompt, communication, sync = make_close_prompt(project, SYNC_NOW)
    prompt.connect()

    root.removeChildNode(group)
    # Tree-driven group removal batches the prompt via a zero-delay timer.
    qgis_application.processEvents()

    assert len(communication.questions) == 1
    assert sync.data_groups == [group_name]
    assert sync.style_groups == [group_name]
    prompt.disconnect()


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
    first_group = add_file_group(parent_group, "first-file", first)
    second_group = add_file_group(parent_group, "second-file", second)
    first_group_name = first_group.name()
    second_group_name = second_group.name()
    first.setCustomProperty("rana/data_dirty", True)
    second.setCustomProperty("rana/style_dirty", True)
    prompt, communication, sync = make_close_prompt(project, SYNC_NOW)
    prompt.connect()

    try:
        root.removeChildNode(parent_group)
        # Tree-driven group removal batches the prompt via a zero-delay timer.
        qgis_application.processEvents()

        assert len(communication.questions) == 1
        assert sync.data_groups == [first_group_name]
        assert sync.style_groups == [second_group_name]
    finally:
        prompt.disconnect()


def test_single_file_with_only_style_changes_says_style(qgis_application):
    question = CloseSyncPrompt.build_question(["roads.gpkg"], [])

    assert "unsynced style changes" in question
    assert "data" not in question


def test_single_file_with_only_data_changes_says_data(qgis_application):
    question = CloseSyncPrompt.build_question([], ["roads.gpkg"])

    assert "unsynced data changes" in question
    assert "style" not in question


def test_single_file_dirty_in_both_ways_says_data_and_style(qgis_application):
    question = CloseSyncPrompt.build_question(["roads.gpkg"], ["roads.gpkg"])

    assert "unsynced data and style changes" in question
    assert "and/or" not in question


def test_separate_files_per_change_kind_say_data_and_or_style(qgis_application):
    question = CloseSyncPrompt.build_question(["style.gpkg"], ["data.gpkg"])

    assert "unsynced data and/or style changes" in question
    assert "style.gpkg" in question
    assert "data.gpkg" in question


def test_a_file_dirty_in_both_ways_is_listed_once(qgis_application):
    question = CloseSyncPrompt.build_question(
        ["roads.gpkg", "water.gpkg"], ["roads.gpkg"]
    )

    assert question.count("roads.gpkg") == 1


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
    data_layer.setCustomProperty("rana/data_dirty", True)
    add_file_group(root, "style-file", style_layer)
    add_file_group(root, "data-file", data_layer)
    prompt, communication, sync = make_close_prompt(project, CONTINUE_WITHOUT_SYNCING)
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
    prompt, communication, sync = make_close_prompt(project, CONTINUE_WITHOUT_SYNCING)
    prompt.connect()

    try:
        project.clear()
        _, question, _ = communication.questions[0]
        assert "unsynced style changes" in question
    finally:
        prompt.disconnect()
