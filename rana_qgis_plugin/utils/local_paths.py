import os
import re
import shutil
from pathlib import Path
from typing import Optional
from uuid import uuid4

from threedi_mi_utils import (
    LocalRevision,
    LocalSchematisation,
    list_local_schematisations,
)

from rana_qgis_plugin.communication import UICommunication
from rana_qgis_plugin.utils.settings import rana_cache_dir

UNC_PREFIX = "\\\\?\\"
INVALID_PATH_CHARS = re.compile(r'[<>:"/\\|?*]')


def sanitize_path_segment(segment: str) -> str:
    """Make one path segment valid on both Linux and Windows."""
    return INVALID_PATH_CHARS.sub("_", str(segment)).rstrip(" .")


def sanitize_path(path_str: str) -> str:
    path_obj = Path(path_str)
    anchor = path_obj.anchor
    parts = path_obj.parts[1:] if anchor else path_obj.parts
    sanitized_path = Path(*(sanitize_path_segment(part) for part in parts))
    if anchor:
        sanitized_path = Path(anchor) / sanitized_path
    return str(sanitized_path)


def extended_length_path(path: str | Path) -> str:
    """Return an absolute path that supports paths longer than Windows MAX_PATH.

    The extended-length prefix is only meaningful on Windows.  The function is
    deliberately idempotent so callers can safely apply it at I/O boundaries.
    """
    path_str = os.fspath(path)
    if path_str.startswith(UNC_PREFIX):
        return path_str
    path_str = os.path.abspath(path_str)
    if os.name != "nt":
        return path_str
    if path_str.startswith("\\\\"):
        return f"{UNC_PREFIX}UNC\\{path_str[2:]}"
    return f"{UNC_PREFIX}{path_str}"


def get_safe_local_path(path: str | Path) -> str:
    """Sanitize a newly assembled local path and make it long-path safe."""
    path_str = os.fspath(path)
    # Remove extended-length prefix if present to safely sanitize the path
    if path_str.startswith(UNC_PREFIX):
        path_str = path_str[len(UNC_PREFIX) :]
        if path_str.startswith("UNC\\"):
            path_str = f"\\\\{path_str[4:]}"
    result = sanitize_path(path_str)
    # Extend path length; this will also restore the extended-length prefix if it was present before sanitization
    return extended_length_path(result)


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


def get_local_dir_structure(project_slug: str, path: str) -> str:
    file_path = Path(path)
    local_dir_structure = Path(rana_cache_dir()).joinpath(
        project_slug, "files", file_path.parent, file_path.stem
    )
    return get_safe_local_path(local_dir_structure)


def get_local_file_path(project_slug: str, path: str) -> str:
    file_path = Path(path)
    local_file_path = Path(rana_cache_dir()).joinpath(
        project_slug,
        "files",
        file_path.parent,
        file_path.stem,
        file_path.name,
    )
    return get_safe_local_path(local_file_path)


def get_local_publication_dir_structure(
    project_slug: str, path: str, publication_tree: list[str]
) -> str:
    file_path = Path(path)
    local_dir_structure = Path(rana_cache_dir()).joinpath(
        project_slug,
        "publications",
        *publication_tree,
        file_path.stem,
    )
    return get_safe_local_path(local_dir_structure)


def get_local_publication_file_path(
    project_slug: str, path: str, publication_tree: list[str]
) -> str:
    file_path = Path(path)
    local_file_path = Path(rana_cache_dir()).joinpath(
        project_slug,
        "publications",
        *publication_tree,
        file_path.stem,
        file_path.name,
    )
    return get_safe_local_path(local_file_path)


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
    return extended_length_path(
        str(
            revision_dir
            / "results"
            / sanitize_path_segment(f"{simulation_name} ({simulation_id})")
        )
    )


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
        schematisation_id,  # type: ignore[arg-type]
        schematisation_name,
        revision_number,  # type: ignore[arg-type]
        simulation_name,  # type: ignore[arg-type]
        simulation_id,  # type: ignore[arg-type]
        create=False,
    )


def cleanup_folder(folder: Path, communication: UICommunication) -> None:
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
