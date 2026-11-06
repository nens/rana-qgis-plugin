"""Shared fakes/helpers for the CloseSyncPrompt-family tests."""

from pathlib import PurePosixPath
from unittest.mock import patch

from qgis.core import QgsLayerTreeGroup, QgsMapLayer

from rana_qgis_plugin.layer_management import close_sync_prompt
from rana_qgis_plugin.layer_management.layer_manager import (
    RanaLayerRef,
    get_rana_refs,
    set_rana_refs,
)
from rana_qgis_plugin.layer_management.layer_tree_menu import LayerTreeMenuProvider
from rana_qgis_plugin.layer_management.sync_changes import FileKey
from rana_qgis_plugin.layer_management.sync_summary import (
    build_details,
    build_summary,
)
from rana_qgis_plugin.utils.data_models import DataType


def fk(file_id: str, project_id: str = "project") -> FileKey:
    return FileKey(project_id, file_id)


def make_linked_layer(
    layer: QgsMapLayer, file_id: str, project_id: str = "project"
) -> QgsMapLayer:
    set_rana_refs(layer, RanaLayerRef(project_id, file_id))
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
    """Stand-in for `CloseSyncDialog` that never opens a modal window.

    Records the (summary, details) HTML the dialog would show and reports the
    configured label as the user's choice. Use as a context manager: the
    patch is active only inside the `with` block.
    """

    def __init__(self, choice: str):
        self.choice = choice
        self.shown: list[tuple[str, str]] = []
        self._patcher = patch.object(
            close_sync_prompt, "CloseSyncDialog", self.fake_dialog_class()
        )

    def __enter__(self) -> "ChoiceRecorder":
        self._patcher.start()
        return self

    def __exit__(self, *exc_info) -> None:
        self._patcher.stop()

    def fake_dialog_class(self):
        recorder = self

        class FakeCloseSyncDialog:
            def __init__(self, parent, changes):
                recorder.shown.append((build_summary(changes), build_details(changes)))

            def exec(self) -> int:
                return 0

            def selected_label(self) -> str:
                return recorder.choice

        return FakeCloseSyncDialog


class FakeLayerSource:
    def __init__(self):
        self.discarded = False

    def discard(self):
        self.discarded = True


class FakeStyleItem:
    def __init__(self, file_id: str):
        self.file_ref_str = f"file {file_id}"
        self.data_type = DataType.raster
        self.layer_in_file = None
        self.layer_source = FakeLayerSource()


class FakeDataItem:
    def __init__(self, file_id: str):
        self.rana_ref = RanaLayerRef("project", file_id)
        self.layer_name = None


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
