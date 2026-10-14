"""Consumer-facing dirty-state predicates for Rana-linked layers."""

from enum import Enum

from qgis.core import QgsMapLayer, QgsRasterLayer

from rana_qgis_plugin.layer_management.layer_dirty_flags import (
    DATA_FINGERPRINT_PROPERTY,
    DATA_SYNC_STATE_PROPERTY,
    is_data_dirty,
    is_style_dirty,
    set_data_sync_state,
)
from rana_qgis_plugin.layer_management.layer_manager import is_rana_linked


class LayerSyncState(str, Enum):
    """Whether local data changes are known to be present."""

    CLEAN = "clean"
    DIRTY = "dirty"
    UNKNOWN = "unknown"


def layer_sync_state(layer: QgsMapLayer) -> LayerSyncState:
    """Return data dirtiness, distinguishing untracked rasters from clean data."""
    if not is_rana_linked(layer):
        return LayerSyncState.CLEAN
    stored_state = layer.customProperty(DATA_SYNC_STATE_PROPERTY)
    if stored_state is not None:
        try:
            return LayerSyncState(stored_state)
        except (TypeError, ValueError):
            state = LayerSyncState.UNKNOWN
            set_data_sync_state(layer, state.value)
            return state

    if isinstance(layer, QgsRasterLayer) and not layer.customProperty(
        DATA_FINGERPRINT_PROPERTY
    ):
        state = LayerSyncState.UNKNOWN
    elif is_data_dirty(layer):
        state = LayerSyncState.DIRTY
    else:
        state = LayerSyncState.CLEAN

    set_data_sync_state(layer, state.value)
    return state


def has_unsynced_style(layer: QgsMapLayer) -> bool:
    """Return whether a linked layer has unsynced style changes."""
    return is_rana_linked(layer) and is_style_dirty(layer)


def should_badge(layer: QgsMapLayer) -> bool:
    """Return whether a layer should display an unsynced-changes badge."""
    return has_unsynced_style(layer) or layer_sync_state(layer) is LayerSyncState.DIRTY
