"""Multi-select gating logic for Rana Browser context menus."""

from __future__ import annotations

from enum import Enum
from typing import Sequence

from qgis.core import QgsDataItem

from rana_qgis_plugin.data_items.file_item import RanaFileDataItem
from rana_qgis_plugin.data_items.folder_item import (
    RanaFilesDataItem,
    RanaFolderDataItem,
)
from rana_qgis_plugin.data_items.project_item import RanaProjectDataItem


class SelectionKind(Enum):
    SINGLE = "single"
    INVALID_MULTI = "invalid_multi"
    VALID_MULTI = "valid_multi"


def classify_selection(selected_items: Sequence[QgsDataItem]) -> SelectionKind:
    """Classify a Browser selection for context-menu gating purposes.

    See design decision 20260818-1300: projects and the files-root item
    cannot be part of a valid multi-select; files/folders can.
    """
    if len(selected_items) <= 1:
        return SelectionKind.SINGLE
    if any(isinstance(item, RanaProjectDataItem) for item in selected_items):
        return SelectionKind.INVALID_MULTI
    if any(isinstance(item, RanaFilesDataItem) for item in selected_items):
        return SelectionKind.INVALID_MULTI
    if all(
        isinstance(item, (RanaFolderDataItem, RanaFileDataItem))
        for item in selected_items
    ):
        return SelectionKind.VALID_MULTI
    return SelectionKind.INVALID_MULTI
