"""Which layers of which Rana files have unsynced changes."""

from dataclasses import dataclass, field
from enum import Enum

from qgis.core import QgsMapLayer

from rana_qgis_plugin.layer_management.layer_manager import get_rana_refs
from rana_qgis_plugin.layer_management.layer_sync_state import (
    LayerSyncState,
    has_unsynced_style,
    layer_sync_state,
)


class SyncKind(Enum):
    """The kinds of change a Rana sync moves."""

    DATA = "data"
    STYLE = "style"


@dataclass(frozen=True, order=True)
class FileKey:
    """A Rana file: its path is only unique within its project."""

    project_id: str
    file_id: str


@dataclass(frozen=True)
class SyncChanges:
    """Changed layer names per Rana file, for data and for style."""

    data: dict[FileKey, list[str]] = field(default_factory=dict)
    style: dict[FileKey, list[str]] = field(default_factory=dict)

    @classmethod
    def from_layers(
        cls,
        layers: list[QgsMapLayer],
        kinds: set[SyncKind],
        include_unknown_data: bool = False,
    ) -> "SyncChanges":
        """Return the changed layer names per file, sorted, for the given kinds only.

        ``include_unknown_data`` also counts layers whose data state is unknown, for
        actions that are enabled for anything but clean data.
        """
        data_states = {LayerSyncState.DIRTY}
        if include_unknown_data:
            data_states.add(LayerSyncState.UNKNOWN)
        data_files: dict[FileKey, set[str]] = {}
        style_files: dict[FileKey, set[str]] = {}
        for layer in layers:
            ref = get_rana_refs(layer)
            if ref is None:
                continue
            key = FileKey(ref.project_id, ref.file_id)
            if SyncKind.DATA in kinds and layer_sync_state(layer) in data_states:
                data_files.setdefault(key, set()).add(layer.name())
            if SyncKind.STYLE in kinds and has_unsynced_style(layer):
                style_files.setdefault(key, set()).add(layer.name())
        return cls(
            data={name: sorted(names) for name, names in data_files.items()},
            style={name: sorted(names) for name, names in style_files.items()},
        )

    @staticmethod
    def merge_files(
        first: dict[FileKey, list[str]], second: dict[FileKey, list[str]]
    ) -> dict[FileKey, list[str]]:
        return {
            name: sorted(set(first.get(name, [])) | set(second.get(name, [])))
            for name in first.keys() | second.keys()
        }

    def files(self, kind: SyncKind) -> dict[FileKey, list[str]]:
        return self.data if kind is SyncKind.DATA else self.style

    def for_kind(self, kind: SyncKind) -> "SyncChanges":
        """Return a copy that only keeps the changes of `kind`."""
        if kind is SyncKind.DATA:
            return SyncChanges(data=self.data)
        return SyncChanges(style=self.style)

    def merge(self, other: "SyncChanges") -> "SyncChanges":
        """Return the union of both, with sorted layer names per file."""
        return SyncChanges(
            data=self.merge_files(self.data, other.data),
            style=self.merge_files(self.style, other.style),
        )

    def is_empty(self) -> bool:
        return not self.data and not self.style

    def file_count(self) -> int:
        return len(set(self.data) | set(self.style))
