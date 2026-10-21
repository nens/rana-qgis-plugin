import os
from pathlib import Path
from unittest.mock import patch

from qgis.core import QgsRasterLayer

from rana_qgis_plugin.layer_management.file_fingerprint import (
    fingerprint_dir,
    raster_cache_dir,
)
from rana_qgis_plugin.layer_management.layer_manager import RanaLayerRef, set_rana_refs


def test_fingerprint_is_stable_for_identical_directory_state(tmp_path: Path):
    raster_file = tmp_path / "raster.tif"
    raster_file.write_bytes(b"raster")
    assert fingerprint_dir(tmp_path) == fingerprint_dir(tmp_path)


def test_fingerprint_changes_when_relevant_file_is_added_changed_or_removed(
    tmp_path: Path,
):
    raster_file = tmp_path / "raster.tif"
    raster_file.write_bytes(b"raster")
    original = fingerprint_dir(tmp_path)

    sidecar = tmp_path / "raster.tif.aux.xml"
    sidecar.write_text("metadata")
    added = fingerprint_dir(tmp_path)
    assert added != original

    stat = sidecar.stat()
    os.utime(sidecar, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))
    assert fingerprint_dir(tmp_path) != added

    sidecar.unlink()
    assert fingerprint_dir(tmp_path) == original


def test_fingerprint_ignores_style_and_transient_files(tmp_path: Path):
    (tmp_path / "raster.tif").write_bytes(b"raster")
    original = fingerprint_dir(tmp_path)
    for name in (
        "style.qml",
        "write.tmp",
        "dataset.lock",
        "dataset.gpkg-wal",
        "dataset.gpkg-shm",
    ):
        (tmp_path / name).write_text("ignored")

    assert fingerprint_dir(tmp_path) == original


def test_fingerprint_returns_none_for_missing_or_unreadable_directory(
    tmp_path: Path,
):
    assert fingerprint_dir(tmp_path / "missing") is None

    with patch(
        "rana_qgis_plugin.layer_management.file_fingerprint.os.walk",
        side_effect=PermissionError("unreadable"),
    ):
        assert fingerprint_dir(tmp_path) is None


def test_raster_cache_dir_accepts_linked_gdal_source_with_uri_suffix(
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
        assert raster_cache_dir(layer) == source_dir.resolve()


def test_raster_cache_dir_rejects_unlinked_and_out_of_cache_layers(
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
        assert raster_cache_dir(unlinked) is None
        assert raster_cache_dir(linked_outside) is None


def test_raster_cache_dir_rejects_non_gdal_provider(tmp_path: Path, qgis_application):
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
        assert raster_cache_dir(layer) is None
