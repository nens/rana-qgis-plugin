"""Describe pending Rana sync changes as text for dialogs."""

from rana_qgis_plugin.layer_management.sync_changes import SyncChanges


def describe_changes(has_style: bool, has_data: bool, single_file: bool) -> str:
    """Name the kinds of change being reported."""
    if has_style and has_data:
        return "data and style" if single_file else "data and/or style"
    return "style" if has_style else "data"


def build_summary(changes: SyncChanges, include_kinds: bool = True) -> str:
    """Build the one-line summary of how many files changed and, optionally, how."""
    total = changes.file_count()
    if not include_kinds:
        noun = "file has" if total == 1 else "files have"
        return f"{total} {noun} unsynced changes."
    if total == 1:
        kinds = describe_changes(bool(changes.style), bool(changes.data), True)
        return f"1 file has unsynced changes ({kinds})."
    counts = []
    if changes.data:
        counts.append(f"data: {len(changes.data)}")
    if changes.style:
        counts.append(f"style: {len(changes.style)}")
    return f"{total} files have unsynced changes ({', '.join(counts)})."
