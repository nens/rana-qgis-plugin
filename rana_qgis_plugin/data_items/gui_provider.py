"""Multi-select gating logic for Rana Browser context menus."""

from __future__ import annotations

from enum import Enum
from typing import Iterable, Optional, Sequence

from qgis.core import QgsDataItem
from qgis.gui import QgsDataItemGuiContext, QgsDataItemGuiProvider
from qgis.PyQt.QtWidgets import QAction, QMenu

from rana_qgis_plugin.data_items.file_actions import FileAction
from rana_qgis_plugin.data_items.file_item import RanaFileDataItem
from rana_qgis_plugin.data_items.folder_item import (
    RanaFilesDataItem,
    RanaFolderDataItem,
)
from rana_qgis_plugin.data_items.project_item import RanaProjectDataItem

# Actions permitted for a valid multi-select (files/folders, no root)
MULTI_SELECT_ACTIONS: list[FileAction] = []


class SelectionKind(Enum):
    SINGLE = "single"
    INVALID_MULTI = "invalid_multi"
    VALID_MULTI = "valid_multi"


def classify_selection(selected_items: Sequence[QgsDataItem]) -> SelectionKind:
    """Classify a Browser selection for context-menu gating purposes.

    projects and the files-root item cannot be part of a valid multi-select; files/folders can.
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


def merge_multi_select_actions(
    primary_actions: Sequence[QAction],
    per_item_action_texts: Sequence[set[str]],
    whitelist: Sequence[FileAction] = MULTI_SELECT_ACTIONS,
) -> list[QAction]:
    """Return the subset of `primary_actions` valid for a multi-select.

    An action is kept only if its text is present in every selected item's
    own action-text set (intersection — an action must apply to *all*
    selected items, not just some) AND its text is in the multi-select
    whitelist. `primary_actions` are the real, connected QAction objects
    from the item the context menu was invoked on, so surviving actions
    keep their existing handlers rather than being fabricated.
    """
    common_texts = (
        set.intersection(*per_item_action_texts) if per_item_action_texts else set()
    )
    whitelist_texts = {action.value for action in whitelist}
    allowed_texts = common_texts & whitelist_texts
    return [action for action in primary_actions if action.text() in allowed_texts]


class RanaDataItemGuiProvider(QgsDataItemGuiProvider):
    """Gates Rana Browser context menus for multi-select safety.

    Runs alongside the legacy per-item `actions()` menus (unchanged). For
    0-1 selected items it does nothing. For an invalid multi-select
    (projects, files-root, or otherwise disallowed combinations) it clears
    the menu entirely. For a valid multi-select (files/folders, no root)
    it keeps only the actions common to every selected item's own actions()
    that are also in `MULTI_SELECT_ACTIONS` (see `merge_multi_select_actions`).
    """

    def name(self) -> str:
        return "rana_multi_select_gating"

    def populateContextMenu(
        self,
        item: Optional[QgsDataItem],
        menu: Optional[QMenu],
        selectedItems: Iterable[QgsDataItem],
        context: QgsDataItemGuiContext,
    ) -> None:
        if menu is None:
            return
        selected = list(selectedItems)
        kind = classify_selection(selected)
        if kind is SelectionKind.SINGLE:
            return
        if kind is SelectionKind.INVALID_MULTI:
            menu.clear()
            return

        actions_by_item = [
            (selected_item, selected_item.actions(menu)) for selected_item in selected
        ]
        primary_item_actions = next(
            (actions for candidate, actions in actions_by_item if candidate is item),
            actions_by_item[0][1] if actions_by_item else [],
        )
        allowed_actions = merge_multi_select_actions(
            primary_item_actions,
            [{action.text() for action in actions} for _, actions in actions_by_item],
        )

        menu.clear()
        for action in allowed_actions:
            menu.addAction(action)
