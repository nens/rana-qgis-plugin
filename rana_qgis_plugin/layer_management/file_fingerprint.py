"""Stat-based fingerprints for the raster file uploaded to Rana."""

import hashlib
from pathlib import Path

from qgis.core import QgsRasterLayer

from rana_qgis_plugin.layer_management.layer_manager import is_rana_linked
from rana_qgis_plugin.utils.settings import rana_cache_dir


def fingerprint_file(path: str | Path) -> str | None:
    """Return a stable digest of the uploaded file's size and nanosecond mtime.

    File contents and non-uploaded sidecars are not read. Missing or unreadable
    files return None.
    """
    file_path = Path(path)
    try:
        if not file_path.is_file():
            return None
        stat = file_path.stat()
    except OSError:
        return None

    manifest = f"{file_path.name}|{stat.st_size}|{stat.st_mtime_ns}"
    digest = hashlib.sha256(manifest.encode("utf-8"))
    return digest.hexdigest()[:16]


def raster_source_path(layer: QgsRasterLayer) -> Path | None:
    """Return the eligible linked raster file that is uploaded to Rana."""
    if not isinstance(layer, QgsRasterLayer):
        return None
    if layer.providerType() != "gdal" or not is_rana_linked(layer):
        return None

    source_path = layer.source().split("|", 1)[0]
    try:
        source = Path(source_path).resolve()
        cache = Path(rana_cache_dir()).resolve()
        source.relative_to(cache)
    except (OSError, ValueError):
        return None
    return source
