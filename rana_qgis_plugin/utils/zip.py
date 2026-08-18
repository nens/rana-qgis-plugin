"""Safe helpers for extracting flat ZIP archives."""

from pathlib import Path
from zipfile import ZipFile


def extract_flat(zip_file: ZipFile, target_dir: Path) -> None:
    """Extract files into target_dir, discarding archive directories.

    Duplicate resulting names are rejected to prevent silent overwrites.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    extracted_names: set[str] = set()
    for member in zip_file.infolist():
        if member.is_dir():
            continue
        filename = Path(member.filename).name
        if not filename:
            continue
        if filename in extracted_names:
            raise ValueError(f"Duplicate archive filename: {filename}")
        extracted_names.add(filename)
        (target_dir / filename).write_bytes(zip_file.read(member))
