"""Capture and evaluate baselines for locally cached Rana raster files."""

from qgis.core import QgsRasterLayer

from rana_qgis_plugin.layer_management.file_fingerprint import (
    fingerprint_dir,
    raster_cache_dir,
)
from rana_qgis_plugin.layer_management.layer_dirty_flags import (
    DATA_DIRTY_PROPERTY,
    DATA_FINGERPRINT_PROPERTY,
)
from rana_qgis_plugin.layer_management.layer_sync_state import LayerSyncState


def capture_raster_baseline(layer: QgsRasterLayer) -> bool:
    """Store the current fingerprint as the layer's known-in-sync baseline."""
    directory = raster_cache_dir(layer)
    if directory is None:
        return False

    fingerprint = fingerprint_dir(directory)
    if fingerprint is None:
        return False

    layer.setCustomProperty(DATA_FINGERPRINT_PROPERTY, fingerprint)
    layer.removeCustomProperty(DATA_DIRTY_PROPERTY)
    return True


def evaluate_raster_data_dirty(layer: QgsRasterLayer) -> LayerSyncState:
    """Compare an eligible raster's current files with its saved baseline."""
    directory = raster_cache_dir(layer)
    baseline = layer.customProperty(DATA_FINGERPRINT_PROPERTY)
    if directory is None or not isinstance(baseline, str) or not baseline:
        layer.removeCustomProperty(DATA_DIRTY_PROPERTY)
        return LayerSyncState.UNKNOWN

    fingerprint = fingerprint_dir(directory)
    if fingerprint is None:
        layer.removeCustomProperty(DATA_DIRTY_PROPERTY)
        return LayerSyncState.UNKNOWN

    if fingerprint == baseline:
        layer.removeCustomProperty(DATA_DIRTY_PROPERTY)
        return LayerSyncState.CLEAN

    layer.setCustomProperty(DATA_DIRTY_PROPERTY, True)
    return LayerSyncState.DIRTY
