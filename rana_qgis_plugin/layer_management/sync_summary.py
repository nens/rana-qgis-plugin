"""Describe pending Rana sync changes as text for dialogs and notices."""

import html

from rana_qgis_plugin.layer_management.sync_changes import (
    FileKey,
    SyncChanges,
    SyncKind,
)


def describe_changes(has_style: bool, has_data: bool, single_file: bool) -> str:
    """Name the kinds of change being reported."""
    if has_style and has_data:
        return "data and style" if single_file else "data and/or style"
    return "style" if has_style else "data"


def build_summary(changes: SyncChanges) -> str:
    """Build the one-line summary of how many files changed and how."""
    total = changes.file_count()
    if total == 1:
        kinds = describe_changes(bool(changes.style), bool(changes.data), True)
        return f"1 file has unsynced changes ({kinds})."
    counts = []
    if changes.data:
        counts.append(f"data: {len(changes.data)}")
    if changes.style:
        counts.append(f"style: {len(changes.style)}")
    return f"{total} files have unsynced changes ({', '.join(counts)})."


def file_labels(changes: SyncChanges) -> dict[FileKey, str]:
    """Label each changed file as `project: path`."""
    keys = set(changes.data) | set(changes.style)
    return {key: f"{key.project_id}: {key.file_id}" for key in keys}


def format_file_changes(
    files: dict[FileKey, list[str]], labels: dict[FileKey, str]
) -> str:
    """Render changed layers per file: one layer inline, several as a nested list."""
    items = []
    for key, layers in sorted(files.items(), key=lambda item: labels[item[0]]):
        name = labels[key]
        if len(layers) == 1:
            items.append(f"<li>{html.escape(name)}: {html.escape(layers[0])}</li>")
        else:
            layer_items = "".join(f"<li>{html.escape(layer)}</li>" for layer in layers)
            items.append(
                f"<li>{html.escape(name)}:"
                f'<ul style="margin-top:0px; margin-bottom:0px">{layer_items}</ul></li>'
            )
    return f'<ul style="margin-top:0px; margin-bottom:0px">{"".join(items)}</ul>'


def build_details(changes: SyncChanges) -> str:
    """Build rich-text details listing the changed layers per file, by kind."""
    sections: list[str] = []
    labels = file_labels(changes)
    for heading, files in [
        ("Data changes:", changes.data),
        ("Style changes:", changes.style),
    ]:
        if files:
            top = "10px" if sections else "0px"
            sections.append(
                f'<p style="margin-top:{top}; margin-bottom:0px"><b>{heading}</b></p>'
                f"{format_file_changes(files, labels)}"
            )
    return "".join(sections)


def build_sync_notice(kind: SyncKind, changes: SyncChanges) -> str:
    """Build the notice shown when syncing `kind` starts."""
    files = changes.files(kind)
    if len(files) == 1:
        (key,) = files
        name = file_labels(changes)[key]
        return f"Syncing {kind.value} of <b>{html.escape(name)}</b> to Rana..."
    return f"Syncing {kind.value} of {len(files)} files to Rana..."
