from rana_qgis_plugin.layer_management.sync_lock import LayerLockRegistry


def test_acquire_and_release_sync_lock():
    key = ("project", "descriptor")

    registry = LayerLockRegistry()
    assert registry.acquire(key)
    assert registry.is_locked(key)

    registry.release(key)

    assert not registry.is_locked(key)


def test_second_acquire_is_rejected_until_release():
    key = ("project", "descriptor")
    registry = LayerLockRegistry()

    assert registry.acquire(key)
    assert not registry.acquire(key)

    registry.release(key)
    assert registry.acquire(key)
    registry.release(key)


def test_releasing_unknown_key_is_safe():
    LayerLockRegistry().release(("unknown", "descriptor"))
