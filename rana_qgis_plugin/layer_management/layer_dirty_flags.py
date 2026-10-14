"""Low-level dirty-property and edit-signal tracking for Rana layers."""

from qgis.core import QgsMapLayer, QgsVectorLayer

DATA_SYNC_STATE_PROPERTY = "rana/data_sync_state"
DATA_FINGERPRINT_PROPERTY = "rana/data_fingerprint"
STYLE_DIRTY_PROPERTY = "rana/style_dirty"


def is_data_dirty(layer: QgsMapLayer) -> bool:
    return layer.customProperty(DATA_SYNC_STATE_PROPERTY) == "dirty"


def is_style_dirty(layer: QgsMapLayer) -> bool:
    return bool(layer.customProperty(STYLE_DIRTY_PROPERTY, False))


def clear_dirty(layer: QgsMapLayer, property_name: str) -> None:
    layer.removeCustomProperty(property_name)


def set_data_sync_state(layer: QgsMapLayer, state: str) -> None:
    """Persist one explicit data sync state on the layer."""
    layer.setCustomProperty(DATA_SYNC_STATE_PROPERTY, state)


def clear_data_sync_state(layer: QgsMapLayer) -> None:
    """Remove the stored data sync state."""
    layer.removeCustomProperty(DATA_SYNC_STATE_PROPERTY)


def attach_dirty_tracking(layer: QgsMapLayer) -> None:
    """Track local data and style changes on a Rana-linked layer."""
    set_data_sync_state(layer, "clean")
    if isinstance(layer, QgsVectorLayer):
        layer.afterCommitChanges.connect(lambda: set_data_sync_state(layer, "dirty"))
    layer.styleChanged.connect(
        lambda: layer.setCustomProperty(STYLE_DIRTY_PROPERTY, True)
    )
