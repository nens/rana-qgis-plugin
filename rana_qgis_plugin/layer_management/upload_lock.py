"""Keep layers read-only while their file is being uploaded to Rana."""

from dataclasses import dataclass
from pathlib import Path

from qgis.core import QgsMapLayer, QgsProject, QgsProviderRegistry, QgsVectorLayer

from rana_qgis_plugin.layer_management.sync_lock import LayerLockRegistry, SyncKey
from rana_qgis_plugin.workers.upload import UploadJob

UPLOAD_LOCK_PROPERTY = "rana/upload_lock"


def layers_for_file(path: Path) -> list[QgsMapLayer]:
    """Return all project layers whose source is *path* (any GeoPackage table)."""
    project = QgsProject.instance()
    registry = QgsProviderRegistry.instance()
    if project is None or registry is None:
        return []
    target = path.resolve()
    layers = []
    for layer in project.mapLayers().values():
        source_path = registry.decodeUri(layer.providerType(), layer.source()).get(
            "path"
        )
        if source_path and Path(source_path).resolve() == target:
            layers.append(layer)
    return layers


def restore_layer(layer: QgsMapLayer) -> None:
    """Restore the read-only state saved by an upload lock and clear the marker."""
    previous = layer.customProperty(UPLOAD_LOCK_PROPERTY)
    if previous is None:
        return
    if isinstance(layer, QgsVectorLayer):
        layer.setReadOnly(str(previous).lower() == "true")
    layer.removeCustomProperty(UPLOAD_LOCK_PROPERTY)


def restore_stale_upload_locks(project: QgsProject) -> None:
    """Undo locks left in a project that was saved during an upload."""
    for layer in project.mapLayers().values():
        restore_layer(layer)


@dataclass
class FileLock:
    """Sync key and read-only vector layers held for one uploading file."""

    key: SyncKey
    registry: LayerLockRegistry
    layer_ids: list[str]

    def release(self) -> None:
        """Restore layers and release the key. Safe to call more than once."""
        project = QgsProject.instance()
        if project is not None:
            for layer_id in self.layer_ids:
                layer = project.mapLayer(layer_id)
                if layer is not None:
                    restore_layer(layer)
        self.registry.release(self.key)


def lock_jobs(
    jobs: list[UploadJob], registry: LayerLockRegistry
) -> tuple[list[FileLock], list[str]]:
    """Lock the key and vector layers of each job, in the main thread.

    Jobs that cannot be locked (key held, layer in edit mode) are skipped with a
    warning. When locking raises, everything already taken is released first.
    """
    locks: list[FileLock] = []
    warnings: list[str] = []
    try:
        for job in jobs:
            if job.sync_key is None:
                raise ValueError(f"Upload job for {job.local_path} has no sync key")
            layers = [
                layer
                for layer in layers_for_file(job.local_path)
                if isinstance(layer, QgsVectorLayer)
            ]
            if any(layer.isEditable() for layer in layers):
                warnings.append(
                    f"{job.local_path.name}: save or discard your edits first."
                )
                continue
            if not registry.acquire(job.sync_key):
                warnings.append(f"{job.local_path.name} is already being synced.")
                continue
            lock = FileLock(job.sync_key, registry, [layer.id() for layer in layers])
            locks.append(lock)
            for layer in layers:
                layer.setCustomProperty(
                    UPLOAD_LOCK_PROPERTY, "true" if layer.readOnly() else "false"
                )
                layer.setReadOnly(True)
    except Exception:
        for lock in locks:
            lock.release()
        raise
    return locks, warnings
