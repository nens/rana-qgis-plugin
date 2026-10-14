"""Watch linked raster cache files and refresh their cached dirty state."""

from pathlib import Path

from qgis.core import QgsMapLayer, QgsProject, QgsRasterLayer
from qgis.PyQt.QtCore import QFileSystemWatcher, QTimer

from rana_qgis_plugin.layer_management.file_fingerprint import raster_source_path
from rana_qgis_plugin.layer_management.layer_manager import is_rana_linked
from rana_qgis_plugin.layer_management.raster_dirty_evaluator import (
    evaluate_raster_data_dirty,
)


class RasterWatch:
    """Maintain filesystem watches for linked, file-backed Rana rasters."""

    def __init__(self, project: QgsProject, debounce_ms: int = 1500):
        self.project = project
        self._watcher = QFileSystemWatcher()
        self._watcher.fileChanged.connect(self.on_path_changed)
        self._watcher.directoryChanged.connect(self.on_path_changed)
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.setInterval(debounce_ms)
        self._timer.timeout.connect(self.evaluate_pending_layers)
        self._layer_paths: dict[str, Path] = {}
        self._layers: dict[str, QgsRasterLayer] = {}
        self._pending_layer_ids: set[str] = set()
        self._connected = False

    def connect(self) -> None:
        """Start watching eligible rasters, including layers already present."""
        if self._connected:
            return
        self._connected = True
        self.project.layersAdded.connect(self.track_layers)
        self.project.layersWillBeRemoved.connect(self.on_layers_will_be_removed)
        self.project.cleared.connect(self.clear)
        self.track_layers(list(self.project.mapLayers().values()))

    def disconnect(self) -> None:
        """Stop the watcher and release all layer and filesystem connections."""
        if not self._connected:
            return
        self._connected = False
        self.project.layersAdded.disconnect(self.track_layers)
        self.project.layersWillBeRemoved.disconnect(self.on_layers_will_be_removed)
        self.project.cleared.disconnect(self.clear)
        self._timer.stop()
        self._pending_layer_ids.clear()
        self._layers.clear()
        self._layer_paths.clear()
        paths = self._watcher.files() + self._watcher.directories()
        if paths:
            self._watcher.removePaths(paths)
        self._watcher.deleteLater()
        self._timer.deleteLater()

    def track_layers(self, layers: list[QgsMapLayer]) -> None:
        """Begin watching eligible raster layers and immediately revalidate."""
        for layer in layers:
            if not isinstance(layer, QgsRasterLayer) or not is_rana_linked(layer):
                continue
            layer_id = layer.id()
            self._layers[layer_id] = layer
            self.refresh_layer_watches(layer_id)
            self._pending_layer_ids.add(layer_id)
        self.start_debounce_if_pending()

    def on_layers_will_be_removed(self, layer_ids: list[str]) -> None:
        """Remove watches for layers as they leave the project."""
        for layer_id in layer_ids:
            self.remove_layer(layer_id)

    def on_path_changed(self, path: str) -> None:
        """Refresh path watches and debounce evaluation of affected layers."""
        changed_path = Path(path)
        layer_ids = {
            layer_id
            for layer_id, source_path in self._layer_paths.items()
            if source_path == changed_path
        }
        active_layer_ids: set[str] = set()
        for layer_id in layer_ids:
            if not changed_path.is_file():
                self.remove_layer(layer_id)
                continue
            self.refresh_layer_watches(layer_id)
            active_layer_ids.add(layer_id)
        self._pending_layer_ids.update(active_layer_ids)
        self.start_debounce_if_pending()

    def evaluate_pending_layers(self) -> None:
        """Recompute dirty state for the raster layers affected by events."""
        layer_ids = self._pending_layer_ids
        self._pending_layer_ids = set()
        for layer_id in layer_ids:
            layer = self._layers.get(layer_id)
            if isinstance(layer, QgsRasterLayer) and is_rana_linked(layer):
                evaluate_raster_data_dirty(layer)

    def clear(self) -> None:
        """Drop all watches when the project is cleared."""
        for layer_id in list(self._layers):
            self.remove_layer(layer_id)
        self._timer.stop()
        self._pending_layer_ids.clear()

    def refresh_layer_watches(self, layer_id: str) -> None:
        """Register the layer's single uploaded source file for watching."""
        layer = self._layers.get(layer_id)
        if layer is None:
            return
        source_path = raster_source_path(layer)
        if source_path is None or not source_path.is_file():
            self.remove_layer(layer_id)
            return

        # Track only the file whose bytes are uploaded to Rana. If it is
        # atomically replaced at this path, its change signal lets us restore
        # the watch after Qt drops it from the old file object.
        old_path = self._layer_paths.get(layer_id)
        if old_path is not None and old_path != source_path:
            self._remove_file_watch_if_unused(old_path, layer_id)
        self._layer_paths[layer_id] = source_path
        if str(source_path) not in self._watcher.files():
            # Qt drops a file watch when that file is atomically replaced.
            # The resulting fileChanged signal reaches here to restore it.
            self._watcher.addPath(str(source_path))

    def _remove_file_watch_if_unused(
        self, source_path: Path, removing_layer_id: str
    ) -> None:
        """Keep a shared source watch until its last tracked layer is removed."""
        if any(
            layer_id != removing_layer_id and path == source_path
            for layer_id, path in self._layer_paths.items()
        ):
            return
        source = str(source_path)
        if source in self._watcher.files():
            self._watcher.removePath(source)

    def remove_layer(self, layer_id: str) -> None:
        """Forget a raster layer and detach its path watches."""
        source_path = self._layer_paths.pop(layer_id, None)
        if source_path is not None:
            self._remove_file_watch_if_unused(source_path, layer_id)
        self._layers.pop(layer_id, None)
        self._pending_layer_ids.discard(layer_id)
        if self._pending_layer_ids:
            self.start_debounce_if_pending()
        else:
            self._timer.stop()

    def start_debounce_if_pending(self) -> None:
        if self._pending_layer_ids:
            self._timer.start()
