"""Central locking for Rana file synchronization."""

SyncKey = tuple[str, str]


class LayerLockRegistry:
    """Track locks for Rana-linked layers/files."""

    def __init__(self) -> None:
        self._locked_keys: set[SyncKey] = set()

    def acquire(self, key: SyncKey) -> bool:
        """Acquire *key*, returning False when it is already locked."""
        if key in self._locked_keys:
            return False
        self._locked_keys.add(key)
        return True

    def release(self, key: SyncKey) -> None:
        """Release *key* if it is currently locked."""
        self._locked_keys.discard(key)

    def is_locked(self, key: SyncKey) -> bool:
        """Return whether *key* is currently locked."""
        return key in self._locked_keys
