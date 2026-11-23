"""Central locking for Rana file synchronization."""

from qgis.core import Qgis, QgsMessageLog

SyncKey = tuple[str, str]


def sync_key(project_id: str, file_id: str) -> SyncKey:
    """Return the lock key for a Rana file.

    The server assigns a new descriptor_id on every upload, so the key uses
    the stable file_id instead.
    """
    return (project_id, file_id)


class LayerLockRegistry:
    """Track locks for Rana-linked layers/files."""

    def __init__(self) -> None:
        self._locked_keys: set[SyncKey] = set()

    def acquire(self, key: SyncKey) -> bool:
        """Acquire *key*, returning False when it is already locked."""
        if key in self._locked_keys:
            QgsMessageLog.logMessage(
                f"Lock acquire refused: {key}", "Rana", Qgis.MessageLevel.Info
            )
            return False
        self._locked_keys.add(key)
        QgsMessageLog.logMessage(
            f"Lock acquired: {key}", "Rana", Qgis.MessageLevel.Info
        )
        return True

    def release(self, key: SyncKey) -> None:
        """Release *key* if it is currently locked."""
        self._locked_keys.discard(key)
        QgsMessageLog.logMessage(
            f"Lock released: {key}", "Rana", Qgis.MessageLevel.Info
        )

    def is_locked(self, key: SyncKey) -> bool:
        """Return whether *key* is currently locked."""
        return key in self._locked_keys
