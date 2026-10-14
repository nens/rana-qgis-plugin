"""Consumer-facing dirty-state predicates for Rana-linked layers."""

from enum import Enum, auto

from qgis.core import QgsMapLayer, QgsRasterLayer

from rana_qgis_plugin.layer_management.dirty_tracking import (
    is_data_dirty,
    is_style_dirty,
)
from rana_qgis_plugin.layer_management.layer_manager import is_rana_linked


class DataDirtyState(Enum):
    """Whether local data changes are known to be present."""

    CLEAN = auto()
    DIRTY = auto()
    UNKNOWN = auto()


def data_dirty_state(layer: QgsMapLayer) -> DataDirtyState:
    """Return data dirtiness, distinguishing untracked rasters from clean data."""
    if not is_rana_linked(layer):
        return DataDirtyState.CLEAN
    if isinstance(layer, QgsRasterLayer):
        return DataDirtyState.UNKNOWN
    return DataDirtyState.DIRTY if is_data_dirty(layer) else DataDirtyState.CLEAN


def has_unsynced_style(layer: QgsMapLayer) -> bool:
    """Return whether a linked layer has unsynced style changes."""
    return is_rana_linked(layer) and is_style_dirty(layer)


def should_badge(layer: QgsMapLayer) -> bool:
    """Return whether a layer should display an unsynced-changes badge."""
    return has_unsynced_style(layer) or data_dirty_state(layer) is DataDirtyState.DIRTY
