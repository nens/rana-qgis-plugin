"""Safe helpers for extracting flat ZIP archives."""

from pathlib import Path
from zipfile import ZipFile


def extract_flat(zip_file: ZipFile, target_dir: Path) -> list[Path]:
    """Extract files into target_dir, discarding archive directories.

    Duplicate resulting names are rejected to prevent silent overwrites.
    Returns the paths written, so callers can post-process exactly the files
    this extraction produced rather than everything in the target directory
    (which may hold unrelated files from the same Rana folder).
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    extracted_names: set[str] = set()
    extracted_paths: list[Path] = []
    for member in zip_file.infolist():
        if member.is_dir():
            continue
        filename = Path(member.filename).name
        if not filename:
            continue
        if filename in extracted_names:
            raise ValueError(f"Duplicate archive filename: {filename}")
        extracted_names.add(filename)
        target_path = target_dir / filename
        target_path.write_bytes(zip_file.read(member))
        extracted_paths.append(target_path)
    return extracted_paths
