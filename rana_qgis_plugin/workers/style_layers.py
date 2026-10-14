"""Supply the layers a style build needs, either live or restored from a snapshot.

A style build needs real ``QgsMapLayer`` objects with renderers attached: QML
export, the Lizard colormap conversion and the Mapbox conversion all read the
layer's renderer directly. Resolving those layers from ``QgsProject`` at build
time only works while the layers are still in the project, which is not the
case once a project is cleared or a layer tree node is removed.

These sources decouple the builders from that assumption. The menu-driven save
hands over the live layers it already has; the close prompt captures a cheap
QML snapshot while the layers are still alive and restores equivalent layers
later on the worker thread.
"""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from qgis.core import QgsMapLayer, QgsRasterLayer, QgsVectorLayer

from rana_qgis_plugin.utils.qgis import strip_rana_properties_from_qml


@dataclass(frozen=True)
class LayerStyleSnapshot:
    """Everything needed to rebuild one styled layer without the project."""

    source: str
    name: str
    provider_key: str
    is_raster: bool
    qml_path: Path


class LayerSource(Protocol):
    """Provides the layers a StyleBuilder should collect style files for."""

    @property
    def layers(self) -> list[QgsMapLayer]: ...

    def discard(self) -> None:
        """Release any resources held on behalf of a build that never ran."""
        ...


class LiveLayerSource:
    """Hands over layers that are still owned by the project."""

    def __init__(self, layers: list[QgsMapLayer]):
        self._layers = list(layers)

    @property
    def layers(self) -> list[QgsMapLayer]:
        return self._layers

    def discard(self) -> None:
        """Nothing to release: the project owns these layers."""


class SnapshotLayerSource:
    """Rebuilds styled layers from a snapshot taken before they were removed.

    Reconstruction is deferred until ``layers`` is first read so it happens on
    the upload task's worker thread rather than in the signal handler that
    captured the snapshot.
    """

    def __init__(self, snapshots: list[LayerStyleSnapshot], qml_dir: Path):
        self.snapshots = snapshots
        self.qml_dir = qml_dir
        self._layers: list[QgsMapLayer] | None = None

    @property
    def layers(self) -> list[QgsMapLayer]:
        if self._layers is None:
            restored = []
            for snapshot in self.snapshots:
                layer = build_layer(snapshot)
                if layer is not None:
                    restored.append(layer)
            self._layers = restored
        return self._layers

    def discard(self) -> None:
        shutil.rmtree(self.qml_dir, ignore_errors=True)


def build_layer(snapshot: LayerStyleSnapshot) -> QgsMapLayer | None:
    """Recreate a styled layer from its snapshot, or None if it cannot be read."""
    layer: QgsMapLayer
    if snapshot.is_raster:
        layer = QgsRasterLayer(snapshot.source, snapshot.name, snapshot.provider_key)
    else:
        layer = QgsVectorLayer(snapshot.source, snapshot.name, snapshot.provider_key)
    if not layer.isValid():
        return None
    # QGIS returns (message, success); an unreadable QML leaves the layer with
    # its default renderer, which would silently upload the wrong style.
    _, loaded = layer.loadNamedStyle(str(snapshot.qml_path))
    if not loaded:
        return None
    layer.setName(snapshot.name)
    return layer


def capture_layer_styles(layers: list[QgsMapLayer]) -> SnapshotLayerSource:
    """Snapshot the current style of live layers into a temporary directory.

    Called from signal handlers while the layers are still alive, so this stays
    limited to serializing each renderer to a small QML file. The caller owns
    the result and must ``discard()`` it if no build follows.
    """
    qml_dir = Path(tempfile.mkdtemp())
    snapshots = []
    for index, layer in enumerate(layers):
        # Index-based names avoid layer names that are illegal as file names.
        qml_path = qml_dir.joinpath(f"{index}.qml")
        layer.saveNamedStyle(str(qml_path))
        strip_rana_properties_from_qml(qml_path)
        snapshots.append(
            LayerStyleSnapshot(
                source=layer.source(),
                name=layer.name(),
                provider_key=layer.providerType(),
                is_raster=isinstance(layer, QgsRasterLayer),
                qml_path=qml_path,
            )
        )
    return SnapshotLayerSource(snapshots, qml_dir)
