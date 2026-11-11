"""Which layers of which Rana files have unsynced changes."""

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum

from qgis.core import Qgis, QgsMapLayer, QgsRasterLayer, QgsVectorLayer

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
class SyncFileKey:
    """Identifies a Rana file for one kind of sync: project and descriptor or file ID."""

    project_id: str
    ref: str


def file_key(
    project_id: str | None, descriptor_id: str | None, file_id: str | None
) -> SyncFileKey | None:
    """Return the key that ties a file's changes to its upload items.

    The reference is the descriptor ID, or the file ID when there is none. Without a
    project ID or a reference there is no key, so the item never matches a change.
    """
    ref = descriptor_id or file_id
    if not project_id or not ref:
        return None
    return SyncFileKey(project_id, ref)


@dataclass(frozen=True)
class ChangedLayer:
    """A layer with unsynced changes, with the icon type that shows its geometry."""

    name: str
    icon_type: str


@dataclass(frozen=True)
class ChangedFile:
    """A Rana file with unsynced changes: its path from the project root and layers."""

    path: str
    icon_type: str
    layers: tuple[ChangedLayer, ...]


def layer_icon_type(layer: QgsMapLayer) -> str:
    if isinstance(layer, QgsRasterLayer):
        return "raster"
    if isinstance(layer, QgsVectorLayer):
        geometry = layer.geometryType()
        if geometry == Qgis.GeometryType.Point:
            return "point"
        if geometry == Qgis.GeometryType.Line:
            return "linestring"
        if geometry == Qgis.GeometryType.Polygon:
            return "polygon"
    return "table"


def sorted_layers(layers: Iterable[ChangedLayer]) -> tuple[ChangedLayer, ...]:
    return tuple(sorted(layers, key=lambda layer: (layer.name, layer.icon_type)))


def group_files(
    entries: list[tuple[SyncFileKey, str, QgsMapLayer]],
) -> dict[SyncFileKey, ChangedFile]:
    """Group (key, path, layer) entries into one changed file per key."""
    grouped: dict[SyncFileKey, tuple[str, list[QgsMapLayer]]] = {}
    for key, path, layer in entries:
        grouped.setdefault(key, (path, []))[1].append(layer)
    files = {}
    for key, (path, layers) in grouped.items():
        is_raster = any(isinstance(layer, QgsRasterLayer) for layer in layers)
        files[key] = ChangedFile(
            path=path,
            icon_type="raster" if is_raster else "vector",
            layers=sorted_layers(
                ChangedLayer(layer.name(), layer_icon_type(layer)) for layer in layers
            ),
        )
    return files


def merge_files(
    first: dict[SyncFileKey, ChangedFile], second: dict[SyncFileKey, ChangedFile]
) -> dict[SyncFileKey, ChangedFile]:
    merged = dict(first)
    for key, changed in second.items():
        if key not in merged:
            merged[key] = changed
            continue
        existing = merged[key]
        merged[key] = ChangedFile(
            path=existing.path,
            icon_type=existing.icon_type,
            layers=sorted_layers(set(existing.layers) | set(changed.layers)),
        )
    return merged


@dataclass(frozen=True)
class SyncChanges:
    """Changed files per Rana file, for data and for style."""

    data: dict[SyncFileKey, ChangedFile] = field(default_factory=dict)
    style: dict[SyncFileKey, ChangedFile] = field(default_factory=dict)
    # Project names stored on the layers, so display does not need the API.
    project_names: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_layers(
        cls,
        layers: list[QgsMapLayer],
        kinds: set[SyncKind],
        include_unknown_data: bool = False,
    ) -> "SyncChanges":
        """Return the changed files and layers for the given kinds only.

        ``include_unknown_data`` also counts layers whose data state is unknown, for
        actions that are enabled for anything but clean data. Style changes skip
        layers without a descriptor, because they cannot be uploaded as style.
        """
        data_states = {LayerSyncState.DIRTY}
        if include_unknown_data:
            data_states.add(LayerSyncState.UNKNOWN)
        data_entries: list[tuple[SyncFileKey, str, QgsMapLayer]] = []
        style_entries: list[tuple[SyncFileKey, str, QgsMapLayer]] = []
        project_names: dict[str, str] = {}
        seen_layer_ids: set[str] = set()
        for layer in layers:
            # A file group that is dirty for both kinds is collected twice by callers.
            if layer.id() in seen_layer_ids:
                continue
            seen_layer_ids.add(layer.id())
            ref = get_rana_refs(layer)
            if ref is None:
                continue
            if ref.project_name:
                project_names.setdefault(ref.project_id, ref.project_name)
            if SyncKind.DATA in kinds and layer_sync_state(layer) in data_states:
                key = file_key(ref.project_id, ref.descriptor_id, ref.file_id)
                if key is not None:
                    data_entries.append((key, ref.file_id, layer))
            if SyncKind.STYLE in kinds and has_unsynced_style(layer):
                key = file_key(ref.project_id, ref.descriptor_id, None)
                if key is not None:
                    style_entries.append((key, ref.file_id, layer))
        return cls(
            data=group_files(data_entries),
            style=group_files(style_entries),
            project_names=project_names,
        )

    def files(self, kind: SyncKind) -> dict[SyncFileKey, ChangedFile]:
        return self.data if kind is SyncKind.DATA else self.style

    def for_kind(self, kind: SyncKind) -> "SyncChanges":
        """Return a copy that only keeps the changes of `kind`."""
        if kind is SyncKind.DATA:
            return SyncChanges(data=self.data, project_names=self.project_names)
        return SyncChanges(style=self.style, project_names=self.project_names)

    def merge(self, other: "SyncChanges") -> "SyncChanges":
        """Return the union of both, with sorted layers per file."""
        return SyncChanges(
            data=merge_files(self.data, other.data),
            style=merge_files(self.style, other.style),
            project_names={**other.project_names, **self.project_names},
        )

    def is_empty(self) -> bool:
        return not self.data and not self.style

    def file_count(self) -> int:
        return len(set(self.data) | set(self.style))

    def project_ids(self) -> set[str]:
        return {key.project_id for key in set(self.data) | set(self.style)}
