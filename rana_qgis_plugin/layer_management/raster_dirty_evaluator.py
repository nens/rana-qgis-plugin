"""Capture and evaluate baselines for locally cached Rana raster files."""

from qgis.core import QgsRasterLayer

from rana_qgis_plugin.layer_management.file_fingerprint import (
    fingerprint_file,
    raster_source_path,
)
from rana_qgis_plugin.layer_management.layer_dirty_flags import (
    DATA_FINGERPRINT_PROPERTY,
    set_data_sync_state,
)
from rana_qgis_plugin.layer_management.layer_sync_state import LayerSyncState


def capture_raster_baseline(layer: QgsRasterLayer) -> None:
    """Store the uploaded source fingerprint and mark the layer clean."""
    source = raster_source_path(layer)
    if source is None:
        return

    fingerprint = fingerprint_file(source)
    if fingerprint is None:
        return

    layer.setCustomProperty(DATA_FINGERPRINT_PROPERTY, fingerprint)
    set_data_sync_state(layer, LayerSyncState.CLEAN.value)


def evaluate_raster_data_dirty(layer: QgsRasterLayer) -> LayerSyncState:
    """Compare an eligible raster's source file with its saved baseline."""
    source = raster_source_path(layer)
    baseline = layer.customProperty(DATA_FINGERPRINT_PROPERTY)
    if source is None or not isinstance(baseline, str) or not baseline:
        set_data_sync_state(layer, LayerSyncState.UNKNOWN.value)
        return LayerSyncState.UNKNOWN

    fingerprint = fingerprint_file(source)
    if fingerprint is None:
        set_data_sync_state(layer, LayerSyncState.UNKNOWN.value)
        return LayerSyncState.UNKNOWN

    if fingerprint == baseline:
        set_data_sync_state(layer, LayerSyncState.CLEAN.value)
        return LayerSyncState.CLEAN

    set_data_sync_state(layer, LayerSyncState.DIRTY.value)
    return LayerSyncState.DIRTY


def finish_raster_upload(layer: QgsRasterLayer, start_fingerprint: str | None) -> None:
    """Set the raster's data state after its file was uploaded.

    *start_fingerprint* was taken just before the file was read for upload. A
    file that changed since then holds edits that were not uploaded, so the
    layer stays dirty. A missing fingerprint counts as changed.
    """
    source = raster_source_path(layer)
    if source is None:
        return
    if start_fingerprint is not None and fingerprint_file(source) == start_fingerprint:
        capture_raster_baseline(layer)
    else:
        set_data_sync_state(layer, LayerSyncState.DIRTY.value)
