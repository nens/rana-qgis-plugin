"""Shared fakes/helpers for the CloseSyncPrompt-family tests."""

from pathlib import PurePosixPath

from qgis.core import QgsLayerTreeGroup, QgsMapLayer

from rana_qgis_plugin.layer_management.layer_manager import (
    RanaLayerRef,
    get_rana_refs,
    set_rana_refs,
)
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


def file_id_for_group(group: QgsLayerTreeGroup) -> str:
    """Return the Rana file ID linked to a group's (first) layer."""
    layers = LayerTreeMenuProvider.collect_all_layers([group])
    ref = get_rana_refs(layers[0])
    assert ref is not None
    return ref.file_id


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
    def __init__(self, file_id: str):
        self.file_ref_str = f"file {file_id}"
        self.layer_source = FakeLayerSource()


class FakeDataItem:
    def __init__(self, file_id: str):
        self.rana_ref = RanaLayerRef("project", file_id)


class SyncRecorder:
    """Fake `LayerTreeMenuProvider` recording captured/dispatched sync items."""

    def __init__(self):
        self.style_groups = []
        self.data_groups = []
        self.captured_style_items: list[FakeStyleItem] = []
        self.capture_for_close: list[bool] = []

    def capture_style_items(self, groups, for_close: bool = False):
        self.capture_for_close.append(for_close)
        items = [FakeStyleItem(file_id_for_group(group)) for group in groups]
        self.captured_style_items.extend(items)
        return items

    def dispatch_style_items(self, items):
        self.style_groups.extend(
            PurePosixPath(item.file_ref_str.removeprefix("file ")).name
            for item in items
        )

    def capture_data_items(self, groups):
        return [FakeDataItem(file_id_for_group(group)) for group in groups]

    def dispatch_data_items(self, items):
        self.data_groups.extend(
            PurePosixPath(item.rana_ref.file_id).name for item in items
        )
