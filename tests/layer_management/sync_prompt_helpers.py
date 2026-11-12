"""Shared fakes/helpers for the CloseSyncPrompt-family tests."""

from pathlib import PurePosixPath
from types import ModuleType
from unittest.mock import patch

from qgis.core import QgsLayerTreeGroup, QgsMapLayer
from qgis.PyQt.QtWidgets import QDialog

from rana_qgis_plugin.layer_management.close_sync_prompt import SYNC_NOW
from rana_qgis_plugin.layer_management.layer_manager import (
    RanaLayerRef,
    get_rana_refs,
    set_rana_refs,
)
from rana_qgis_plugin.layer_management.layer_tree_menu import LayerTreeMenuProvider
from rana_qgis_plugin.layer_management.sync_changes import (
    ChangedFile,
    ChangedLayer,
    SyncChanges,
    SyncFileKey,
    SyncKind,
)
from rana_qgis_plugin.utils.data_models import DataType


def fk(file_id: str, project_id: str = "project") -> SyncFileKey:
    return SyncFileKey(project_id, file_id)


def make_changes(
    data: dict[SyncFileKey, list[str]] | None = None,
    style: dict[SyncFileKey, list[str]] | None = None,
) -> SyncChanges:
    """Build changes of point layers from the layer names per file."""
    return SyncChanges(data=to_changed(data or {}), style=to_changed(style or {}))


def to_changed(files: dict[SyncFileKey, list[str]]) -> dict[SyncFileKey, ChangedFile]:
    return {
        key: ChangedFile(
            key.ref,
            "vector",
            tuple(ChangedLayer(name, "point") for name in sorted(layers)),
        )
        for key, layers in files.items()
    }


def make_linked_layer(
    layer: QgsMapLayer, file_id: str, project_id: str = "project"
) -> QgsMapLayer:
    set_rana_refs(layer, RanaLayerRef(project_id, file_id, descriptor_id=file_id))
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
    """Stand-in for `SyncDialog` that never opens a modal window.

    Patches `SyncDialog` in `module` and records the changes each dialog is
    given. The dialog accepts when its confirm label equals `choice` and
    rejects otherwise, as if the user clicked that button. Files whose file ID
    is in `unchecked` are reported as unselected. Use as a context manager: the
    patch is active only inside the `with` block.
    """

    def __init__(
        self,
        module: ModuleType,
        choice: str,
        unchecked: frozenset[str] = frozenset(),
    ):
        self.choice = choice
        self.unchecked = unchecked
        self.shown: list[SyncChanges] = []
        self._patcher = patch.object(module, "SyncDialog", self.fake_dialog_class())

    def __enter__(self) -> "ChoiceRecorder":
        self._patcher.start()
        return self

    def __exit__(self, *exc_info) -> None:
        self._patcher.stop()

    def fake_dialog_class(self):
        recorder = self

        class FakeSyncDialog:
            def __init__(
                self,
                parent,
                title,
                confirm_label,
                cancel_label,
                changes,
                show_kinds=True,
            ):
                recorder.shown.append(changes)
                self.confirm_label = confirm_label

            def exec(self) -> QDialog.DialogCode:
                if recorder.choice == self.confirm_label:
                    return QDialog.DialogCode.Accepted
                return QDialog.DialogCode.Rejected

            def selected(self, kind: SyncKind) -> set[SyncFileKey]:
                return {
                    key
                    for key in recorder.shown[-1].files(kind)
                    if key.ref not in recorder.unchecked
                }

        return FakeSyncDialog


def shown_paths(changes: SyncChanges) -> set[str]:
    """Return the file paths a dialog would list for the given changes."""
    return {
        PurePosixPath(changed.path).name
        for files in (changes.data, changes.style)
        for changed in files.values()
    }


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
        self.project_id = "project"
        self.descriptor_id = file_id
        self.layer_source = FakeLayerSource()


class FakeDataItem:
    def __init__(self, file_id: str):
        self.rana_ref = RanaLayerRef("project", file_id, descriptor_id=file_id)
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
