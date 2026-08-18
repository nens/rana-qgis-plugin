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
from rana_qgis_plugin.data_items.layer_item import RanaLayerDataItem
from rana_qgis_plugin.data_items.project_item import RanaProjectDataItem
from rana_qgis_plugin.utils.data_models import (
    OpenFileRequest,
    OpenFolderRequest,
    OpenLayerRequest,
)

# Actions permitted for a valid multi-select (files/folders/layers, no root)
MULTI_SELECT_ACTIONS: list[FileAction] = [FileAction.OPEN_IN_QGIS]


class SelectionKind(Enum):
    SINGLE = "single"
    INVALID_MULTI = "invalid_multi"
    VALID_MULTI = "valid_multi"


def classify_selection(selected_items: Sequence[QgsDataItem]) -> SelectionKind:
    """Classify a Browser selection for context-menu gating purposes.

    projects and the files-root item cannot be part of a valid multi-select;
    files/folders/layers can.
    """
    if len(selected_items) <= 1:
        return SelectionKind.SINGLE
    if any(isinstance(item, RanaProjectDataItem) for item in selected_items):
        return SelectionKind.INVALID_MULTI
    if any(isinstance(item, RanaFilesDataItem) for item in selected_items):
        return SelectionKind.INVALID_MULTI
    if all(
        isinstance(item, (RanaFolderDataItem, RanaFileDataItem, RanaLayerDataItem))
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

    For 0-1 selected items: no-op (per-item actions() stand).
    For invalid multi-select: clears the menu.
    For valid multi-select: keeps only whitelisted actions common to all
    items, replacing OPEN_IN_QGIS with a batch handler that resolves
    the full selection.
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
            if action.text() == FileAction.OPEN_IN_QGIS.value:
                batch_action = QAction(FileAction.OPEN_IN_QGIS.value, menu)
                batch_action.setIcon(FileAction.OPEN_IN_QGIS.icon)
                batch_action.triggered.connect(
                    lambda: RanaDataItemGuiProvider.open_selected_items(selected)
                )
                menu.addAction(batch_action)
            else:
                menu.addAction(action)

    @staticmethod
    def open_selected_items(items: Sequence[QgsDataItem]) -> None:
        """Build open requests from the selection and delegate to the loader."""
        requests: list[OpenFileRequest | OpenLayerRequest | OpenFolderRequest] = []
        loader = None

        for item in items:
            if isinstance(item, RanaLayerDataItem):
                parent = item.parent()
                if isinstance(parent, RanaFileDataItem):
                    requests.append(
                        OpenLayerRequest(
                            project=parent.project,
                            file_item=parent.file_item,
                            layer_name=item.name(),
                            layer_id=item.layer_id,
                        )
                    )
                    loader = loader or item.loader
            elif isinstance(item, RanaFileDataItem):
                if item.data_type in ("vector", "raster"):
                    requests.append(
                        OpenFileRequest(project=item.project, file_item=item.file_item)
                    )
                    loader = loader or item.loader
            elif isinstance(item, RanaFolderDataItem):
                requests.append(
                    OpenFolderRequest(
                        project=item.project, folder_path=item.folder_path
                    )
                )
                loader = loader or item.loader

        if requests and loader is not None:
            loader.open_items(requests)
