from pathlib import Path
from unittest.mock import patch

from qgis.core import QgsRasterLayer, QgsVectorLayer

from rana_qgis_plugin.layer_management.layer_dirty_flags import (
    DATA_FINGERPRINT_PROPERTY,
    DATA_SYNC_STATE_PROPERTY,
)
from rana_qgis_plugin.layer_management.layer_manager import (
    RanaLayerRef,
    clear_rana_refs,
    set_rana_refs,
)
from rana_qgis_plugin.layer_management.layer_sync_state import LayerSyncState
from rana_qgis_plugin.layer_management.raster_dirty_evaluator import (
    capture_raster_baseline,
    evaluate_raster_data_dirty,
)


def _linked_raster(cache_dir: Path, qgis_application) -> tuple[QgsRasterLayer, Path]:
    source_dir = cache_dir / "project" / "files" / "raster"
    source_dir.mkdir(parents=True)
    source_file = source_dir / "raster.tif"
    source_file.write_bytes(b"raster")
    layer = QgsRasterLayer(str(source_file), "raster", "gdal")
    set_rana_refs(layer, RanaLayerRef("project", "raster.tif"))
    return layer, source_dir


def test_capture_and_evaluate_raster_baseline(tmp_path: Path, qgis_application):
    """A change to the uploaded raster source file is reported as dirty."""
    cache_dir = tmp_path / "cache"
    layer, source_dir = _linked_raster(cache_dir, qgis_application)
    with patch(
        "rana_qgis_plugin.layer_management.file_fingerprint.rana_cache_dir",
        return_value=str(cache_dir),
    ):
        capture_raster_baseline(layer)
        baseline = layer.customProperty(DATA_FINGERPRINT_PROPERTY)
        assert evaluate_raster_data_dirty(layer) is LayerSyncState.CLEAN
        assert (
            layer.customProperty(DATA_SYNC_STATE_PROPERTY) == LayerSyncState.CLEAN.value
        )

        # A source-file modification changes its stat fingerprint.
        raster_file = source_dir / "raster.tif"
        raster_file.write_bytes(b"changed raster")
        assert evaluate_raster_data_dirty(layer) is LayerSyncState.DIRTY
        assert (
            layer.customProperty(DATA_SYNC_STATE_PROPERTY) == LayerSyncState.DIRTY.value
        )
        assert layer.customProperty(DATA_FINGERPRINT_PROPERTY) == baseline


def test_missing_baseline_is_unknown_and_not_captured_by_evaluation(
    tmp_path: Path, qgis_application
):
    """Evaluating a layer with no stored baseline must not silently adopt
    the current fingerprint as clean, and must clear any stale dirty flag."""
    cache_dir = tmp_path / "cache"
    layer, _ = _linked_raster(cache_dir, qgis_application)
    layer.setCustomProperty(DATA_SYNC_STATE_PROPERTY, LayerSyncState.DIRTY.value)

    with patch(
        "rana_qgis_plugin.layer_management.file_fingerprint.rana_cache_dir",
        return_value=str(cache_dir),
    ):
        assert evaluate_raster_data_dirty(layer) is LayerSyncState.UNKNOWN

    assert layer.customProperty(DATA_FINGERPRINT_PROPERTY) is None
    assert (
        layer.customProperty(DATA_SYNC_STATE_PROPERTY) == LayerSyncState.UNKNOWN.value
    )


def test_missing_current_directory_is_unknown_and_clears_stale_dirty_flag(
    tmp_path: Path, qgis_application
):
    """If the raster's cache directory has disappeared, evaluation can't
    compare fingerprints, so it must report UNKNOWN and clear any stale
    dirty flag rather than leaving a false DIRTY in place."""
    cache_dir = tmp_path / "cache"
    layer, _ = _linked_raster(cache_dir, qgis_application)
    layer.setCustomProperty(DATA_FINGERPRINT_PROPERTY, "stored-baseline")
    layer.setCustomProperty(DATA_SYNC_STATE_PROPERTY, LayerSyncState.DIRTY.value)
    raster_dir = cache_dir / "project" / "files" / "raster"
    (raster_dir / "raster.tif").unlink()
    raster_dir.rmdir()

    with patch(
        "rana_qgis_plugin.layer_management.file_fingerprint.rana_cache_dir",
        return_value=str(cache_dir),
    ):
        assert evaluate_raster_data_dirty(layer) is LayerSyncState.UNKNOWN

    assert (
        layer.customProperty(DATA_SYNC_STATE_PROPERTY) == LayerSyncState.UNKNOWN.value
    )


def test_ineligible_raster_is_unknown_and_clears_stale_dirty_flag(
    tmp_path: Path, qgis_application
):
    """A raster that isn't file-backed in the Rana cache (e.g. a /vsimem
    source) can never be evaluated, so it stays UNKNOWN regardless of any
    pre-existing baseline or stale dirty flag."""
    raster = QgsRasterLayer("/vsimem/nonexistent.tif", "raster", "gdal")
    set_rana_refs(raster, RanaLayerRef("project", "raster.tif"))
    raster.setCustomProperty(DATA_FINGERPRINT_PROPERTY, "stored-baseline")
    raster.setCustomProperty(DATA_SYNC_STATE_PROPERTY, LayerSyncState.DIRTY.value)

    assert evaluate_raster_data_dirty(raster) is LayerSyncState.UNKNOWN
    assert (
        raster.customProperty(DATA_SYNC_STATE_PROPERTY) == LayerSyncState.UNKNOWN.value
    )


def test_clear_rana_refs_removes_fingerprint_without_changing_vector_dirty_state(
    qgis_application,
):
    """Unlinking a layer removes the raster-specific fingerprint baseline
    alongside the Rana identity properties, but must not touch the
    vector-only data_dirty flag, which belongs to a different tracking
    mechanism (afterCommitChanges, not fingerprinting)."""
    vector = QgsVectorLayer("Point?crs=EPSG:4326", "vector", "memory")
    set_rana_refs(vector, RanaLayerRef("project", "data.gpkg"))
    vector.setCustomProperty(DATA_SYNC_STATE_PROPERTY, LayerSyncState.DIRTY.value)
    vector.setCustomProperty(DATA_FINGERPRINT_PROPERTY, "fingerprint")

    clear_rana_refs(vector)

    assert vector.customProperty(DATA_FINGERPRINT_PROPERTY) is None
    assert vector.customProperty(DATA_SYNC_STATE_PROPERTY) is None
