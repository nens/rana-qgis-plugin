import os
from pathlib import Path
from unittest.mock import patch

from qgis.core import QgsRasterLayer

from rana_qgis_plugin.layer_management.file_fingerprint import (
    fingerprint_file,
    raster_source_path,
)
from rana_qgis_plugin.layer_management.layer_manager import RanaLayerRef, set_rana_refs


def test_fingerprint_is_stable_for_identical_file_state(tmp_path: Path):
    raster_file = tmp_path / "raster.tif"
    raster_file.write_bytes(b"raster")
    assert fingerprint_file(raster_file) == fingerprint_file(raster_file)


def test_fingerprint_changes_when_raster_file_size_or_mtime_changes(tmp_path: Path):
    raster_file = tmp_path / "raster.tif"
    raster_file.write_bytes(b"raster")
    original = fingerprint_file(raster_file)

    raster_file.write_bytes(b"raster changed")
    changed_size = fingerprint_file(raster_file)
    assert changed_size != original

    stat = raster_file.stat()
    # Explicitly vary nanosecond mtime while preserving size.
    os.utime(raster_file, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))
    assert fingerprint_file(raster_file) != changed_size


def test_fingerprint_returns_none_for_missing_or_unreadable_file(
    tmp_path: Path,
):
    assert fingerprint_file(tmp_path / "missing.tif") is None
    raster_file = tmp_path / "raster.tif"
    raster_file.write_bytes(b"raster")

    with patch(
        "rana_qgis_plugin.layer_management.file_fingerprint.Path.stat",
        side_effect=PermissionError("unreadable"),
    ):
        assert fingerprint_file(raster_file) is None


def test_raster_source_path_accepts_linked_gdal_source_with_uri_suffix(
    tmp_path: Path, qgis_application
):
    cache_dir = tmp_path / "cache"
    source_dir = cache_dir / "project" / "files" / "raster"
    source_dir.mkdir(parents=True)
    source_file = source_dir / "raster.tif"
    source_file.write_bytes(b"raster")
    layer = QgsRasterLayer(f"{source_file}|option=value", "raster", "gdal")
    set_rana_refs(layer, RanaLayerRef("project", "raster.tif"))

    with patch(
        "rana_qgis_plugin.layer_management.file_fingerprint.rana_cache_dir",
        return_value=str(cache_dir),
    ):
        assert raster_source_path(layer) == source_file.resolve()


def test_raster_source_path_rejects_unlinked_and_out_of_cache_layers(
    tmp_path: Path, qgis_application
):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    outside = tmp_path / "outside.tif"
    outside.write_bytes(b"raster")

    unlinked = QgsRasterLayer(str(outside), "raster", "gdal")
    linked_outside = QgsRasterLayer(str(outside), "raster", "gdal")
    set_rana_refs(linked_outside, RanaLayerRef("project", "raster.tif"))

    with patch(
        "rana_qgis_plugin.layer_management.file_fingerprint.rana_cache_dir",
        return_value=str(cache_dir),
    ):
        assert raster_source_path(unlinked) is None
        assert raster_source_path(linked_outside) is None


def test_raster_source_path_rejects_non_gdal_provider(tmp_path: Path, qgis_application):
    cache_dir = tmp_path / "cache"
    source_dir = cache_dir / "project" / "files" / "raster"
    source_dir.mkdir(parents=True)
    source_file = source_dir / "raster.tif"
    source_file.write_bytes(b"raster")
    layer = QgsRasterLayer(f"type=xyz&url=file://{source_file}", "raster", "wms")
    set_rana_refs(layer, RanaLayerRef("project", "raster.tif"))

    assert layer.providerType() == "wms"
    with patch(
        "rana_qgis_plugin.layer_management.file_fingerprint.rana_cache_dir",
        return_value=str(cache_dir),
    ):
        assert raster_source_path(layer) is None
