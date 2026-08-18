"""Dirty-state helpers for Rana-linked map layers."""

from qgis.core import QgsMapLayer, QgsVectorLayer

DATA_DIRTY_PROPERTY = "rana/data_dirty"
STYLE_DIRTY_PROPERTY = "rana/style_dirty"


def is_data_dirty(layer: QgsMapLayer) -> bool:
    return bool(layer.customProperty(DATA_DIRTY_PROPERTY, False))


def is_style_dirty(layer: QgsMapLayer) -> bool:
    return bool(layer.customProperty(STYLE_DIRTY_PROPERTY, False))


def clear_dirty(layer: QgsMapLayer, property_name: str) -> None:
    layer.removeCustomProperty(property_name)


def attach_dirty_tracking(layer: QgsMapLayer) -> None:
    """Track local data and style changes on a Rana-linked layer."""
    if isinstance(layer, QgsVectorLayer):
        layer.afterCommitChanges.connect(
            lambda: layer.setCustomProperty(DATA_DIRTY_PROPERTY, True)
        )
    layer.styleChanged.connect(
        lambda: layer.setCustomProperty(STYLE_DIRTY_PROPERTY, True)
    )
