"""Stat-based fingerprints for locally cached Rana raster files."""

import hashlib
import os
from pathlib import Path

from qgis.core import QgsRasterLayer

from rana_qgis_plugin.layer_management.layer_manager import is_rana_linked
from rana_qgis_plugin.utils.settings import rana_cache_dir

_EXCLUDED_SUFFIXES = (".qml", ".tmp", ".lock", ".gpkg-wal", ".gpkg-shm")


def fingerprint_dir(path: str | Path) -> str | None:
    """Return a stable digest of file paths, sizes, and mtimes in a directory.

    File contents are not read. Missing or unreadable directories return None.
    """
    root = Path(path)
    manifest: list[str] = []

    def raise_walk_error(error: OSError) -> None:
        raise error

    try:
        if not root.is_dir():
            return None
        for current, _, filenames in os.walk(root, onerror=raise_walk_error):
            directory = Path(current)
            for filename in filenames:
                if filename.lower().endswith(_EXCLUDED_SUFFIXES):
                    continue
                file_path = directory / filename
                stat = file_path.stat()
                relative_path = file_path.relative_to(root).as_posix()
                manifest.append(f"{relative_path}|{stat.st_size}|{stat.st_mtime_ns}")
    except OSError:
        return None

    digest = hashlib.sha256("\n".join(sorted(manifest)).encode("utf-8"))
    return digest.hexdigest()[:16]


def raster_cache_dir(layer: QgsRasterLayer) -> Path | None:
    """Return the containing directory for an eligible linked Rana raster."""
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
    return source.parent
