"""Filesystem helpers."""

import tempfile
from pathlib import Path


def ensure_writable_directory(directory: str | Path) -> tuple[bool, str | None]:
    """Create a directory and verify that files can be written there."""
    try:
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path, delete=True):
            pass
    except OSError as error:
        return False, str(error)
    return True, None
