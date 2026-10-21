"""Consumer-facing dirty-state predicates for Rana-linked layers."""

from enum import Enum, auto

from qgis.core import QgsMapLayer, QgsRasterLayer

from rana_qgis_plugin.layer_management.layer_dirty_flags import (
    is_data_dirty,
    is_style_dirty,
)
from rana_qgis_plugin.layer_management.layer_manager import is_rana_linked


class LayerSyncState(Enum):
    """Whether local data changes are known to be present."""

    CLEAN = auto()
    DIRTY = auto()
    UNKNOWN = auto()


def layer_sync_state(layer: QgsMapLayer) -> LayerSyncState:
    """Return data dirtiness, distinguishing untracked rasters from clean data."""
    if not is_rana_linked(layer):
        return LayerSyncState.CLEAN
    if isinstance(layer, QgsRasterLayer):
        return LayerSyncState.UNKNOWN
    return LayerSyncState.DIRTY if is_data_dirty(layer) else LayerSyncState.CLEAN


def has_unsynced_style(layer: QgsMapLayer) -> bool:
    """Return whether a linked layer has unsynced style changes."""
    return is_rana_linked(layer) and is_style_dirty(layer)


def should_badge(layer: QgsMapLayer) -> bool:
    """Return whether a layer should display an unsynced-changes badge."""
    return has_unsynced_style(layer) or layer_sync_state(layer) is LayerSyncState.DIRTY
