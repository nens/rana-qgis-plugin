import os
import re
from pathlib import Path
from typing import Optional
from uuid import uuid4

from threedi_mi_utils import (
    LocalRevision,
    LocalSchematisation,
    list_local_schematisations,
)

from rana_qgis_plugin.utils.settings import rana_cache_dir


def is_writable(working_dir: str) -> bool:
    """Try to write and remove an empty text file into given location."""
    try:
        test_filename = f"{uuid4()}.txt"
        test_file_path = os.path.join(working_dir, test_filename)
        with open(test_file_path, "w") as test_file:
            test_file.write("")
        os.remove(test_file_path)
    except (PermissionError, OSError):
        return False
    else:
        return True


def sanitize_path_for_filesystem(path: str) -> str:
    """
    Sanitize a path to be valid for Linux and Windows
    """

    INVALID_CHARS = r'[<>:"/\\|?*]'

    def clean_part(part: str) -> str:
        # Replace invalid characters with underscore
        part = re.sub(INVALID_CHARS, "_", part)
        # Strip trailing spaces and dots (Windows limitation)
        part = part.rstrip(" .")
        return part

    if not path:
        return path
    path_obj = Path(path)

    parts = path_obj.parts

    # Remove anchor (drive + root) from parts
    anchor = path_obj.anchor  # e.g. "C:\\"
    if anchor:
        parts = parts[1:]

    # Clean each part
    sanitized_parts = [clean_part(p) for p in parts]

    # Rebuild relative path first
    sanitized_path = Path(*sanitized_parts)

    # Restore full anchor (drive + root)
    if anchor:
        sanitized_path = Path(anchor) / sanitized_path

    return str(sanitized_path)


def get_local_dir_structure(project_slug: str, path: str) -> str:
    file_name_without_extension = Path(path).stem
    base_dir = Path(rana_cache_dir())
    local_dir_structure = base_dir.joinpath(
        project_slug, "files", Path(path).parent, file_name_without_extension
    )
    return sanitize_path_for_filesystem(str(local_dir_structure))


def get_local_file_path(project_slug: str, path: str) -> str:
    local_dir_structure = Path(get_local_dir_structure(project_slug, path))
    file_name = sanitize_path_for_filesystem(Path(path).name)
    return str(local_dir_structure.joinpath(file_name))


def get_local_publication_dir_structure(
    project_slug: str, path: str, publication_tree: list[str]
) -> str:
    file_name_without_extension = Path(path).stem
    base_dir = Path(rana_cache_dir())
    local_dir_structure = base_dir.joinpath(
        project_slug, "publications", *publication_tree, file_name_without_extension
    )
    return sanitize_path_for_filesystem(str(local_dir_structure))


def get_local_publication_file_path(
    project_slug: str, path: str, publication_tree: list[str]
) -> str:
    local_dir_structure = Path(
        get_local_publication_dir_structure(project_slug, path, publication_tree)
    )
    local_file_path = local_dir_structure.joinpath(Path(path).name)
    return sanitize_path_for_filesystem(str(local_file_path))


def get_local_schematisation_revision_dir(
    working_dir: str,
    schematisation_id: int,
    schematisation_name: str,
    revision_number: int,
    create: bool = True,
) -> Optional[Path]:
    """Return the local revision directory for a schematisation.

    If create is True (default), creates the schematisation and revision structure
    if not found locally. If False, returns None when not found.
    """
    if not working_dir or not schematisation_id:
        return None
    local_schematisations = list_local_schematisations(working_dir)
    local_schematisation = local_schematisations.get(schematisation_id)
    if not local_schematisation:
        if not create:
            return None
        local_schematisation = LocalSchematisation(
            working_dir, schematisation_id, schematisation_name, create=True
        )
    local_revision = local_schematisation.revisions.get(revision_number)
    if not local_revision:
        if not create:
            return None
        local_revision = LocalRevision(local_schematisation, revision_number)
        local_revision.make_revision_structure()
    return Path(local_revision.main_dir)


def get_local_results_dir(
    working_dir: str,
    schematisation_id: int,
    schematisation_name: str,
    revision_number: int,
    simulation_name: str,
    simulation_id: int,
    create: bool = True,
) -> Optional[str]:
    """Return the local results directory for a schematisation simulation.

    If create is True (default), creates the directory structure if not found locally.
    If False, returns None when the revision directory is not found.
    """
    revision_dir = get_local_schematisation_revision_dir(
        working_dir, schematisation_id, schematisation_name, revision_number, create
    )
    if not revision_dir:
        return None
    result = str(
        Path(revision_dir / "results").joinpath(f"{simulation_name} ({simulation_id})")
    )
    # replace colons, invalid for Windows paths (don't replace drive colon)
    return result[:3] + result[3:].replace(":", "_")


def get_local_results_dir_from_meta(meta: dict, working_dir: str) -> Optional[str]:
    """Return the local results directory from scenario metadata.

    Only works for scenarios with complete schematisation/simulation metadata.
    Returns None if metadata is incomplete or the directory is not found locally.
    """
    schematisation = meta.get("schematisation") or {}
    simulation = meta.get("simulation") or {}
    schematisation_id = schematisation.get("id")
    schematisation_name = schematisation.get("name", "")
    revision_number = schematisation.get("version")
    simulation_name = simulation.get("name")
    simulation_id = simulation.get("id")
    if not all([schematisation_id, revision_number, simulation_name, simulation_id]):
        return None
    return get_local_results_dir(
        working_dir,
        schematisation_id,
        schematisation_name,
        revision_number,
        simulation_name,
        simulation_id,
        create=False,
    )


def cleanup_folder(folder: Path, communication) -> None:
    """Remove all contents of a folder, keeping the folder itself.

    Failures are logged via communication.log_warn and never raised.
    """
    if not folder.exists():
        return
    for item in folder.iterdir():
        try:
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
        except Exception as exc:
            communication.log_warn(f"Cache cleanup failed for {item}: {exc}")
