"""Rana project folder Browser data item."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from qgis.core import Qgis, QgsDataItem, QgsErrorItem
from qgis.PyQt.QtWidgets import QAction

from rana_qgis_plugin.api_error_signals import ApiErrorSignals
from rana_qgis_plugin.data_items.file_actions import (
    FileAction,
    create_separator,
    get_action_tooltip,
    get_folder_actions,
)
from rana_qgis_plugin.data_items.file_item import RanaFileDataItem
from rana_qgis_plugin.icons import dir_icon
from rana_qgis_plugin.network_manager import NetworkUnavailableError
from rana_qgis_plugin.utils.api import RanaFetchError, get_tenant_project_files

if TYPE_CHECKING:
    from rana_qgis_plugin.loader import Loader


class RanaFolderDataItem(QgsDataItem):
    """Lazy-loading container for one level of a Rana project folder."""

    def __init__(
        self,
        parent: QgsDataItem,
        loader: Loader,
        project_id: str,
        folder_path: str,
        display_name: str,
        error_signals: ApiErrorSignals,
    ):
        self.loader = loader
        self.project_id = project_id
        self.folder_path = folder_path
        self.error_signals = error_signals
        super().__init__(
            Qgis.BrowserItemType.Collection,
            parent,
            display_name,
            f"{parent.path()}/{folder_path}"
            if folder_path
            else f"{parent.path()}/files",
            "Rana",
        )
        self.setIcon(dir_icon)
        self.setSortKey(f"0:{display_name.lower()}")
        self.setCapabilitiesV2(
            cast(
                Qgis.BrowserItemCapabilities,
                Qgis.BrowserItemCapability.Fertile
                | Qgis.BrowserItemCapability.Collapse
                | Qgis.BrowserItemCapability.RefreshChildrenWhenItemIsRefreshed,
            )
        )

    def createChildren(self) -> list:
        """Fetch and return the immediate contents of this folder."""
        params = {"path": self.folder_path} if self.folder_path else None
        try:
            files = get_tenant_project_files(self.project_id, params=params)
        except NetworkUnavailableError:
            self.error_signals.connection_lost.emit()
            return [QgsErrorItem(self, "No connection to Rana", self.path())]
        except RanaFetchError as e:
            self.error_signals.fetch_error_occurred.emit(str(e), True)
            return [QgsErrorItem(self, "Failed to load files", self.path())]

        return [self.create_child_item(item) for item in files]

    def actions(self, parent) -> list:
        """Return unconnected folder context-menu actions."""
        actions = []
        for action in get_folder_actions(is_root=not self.folder_path):
            if action is FileAction.DELETE:
                actions.append(create_separator(parent))
            q_action = QAction(action.value, parent)
            q_action.setIcon(action.icon)
            q_action.setToolTip(get_action_tooltip(action))
            if action is FileAction.UPLOAD_FILES:
                q_action.triggered.connect(
                    lambda: self.loader.upload_files(
                        {"id": self.project_id},
                        self.folder_path,
                        parent,
                        refresh_callback=self.refresh_if_populated,
                    )
                )
            actions.append(q_action)
        return actions

    def refresh_if_populated(self) -> None:
        """Refresh this folder if it has already been populated."""
        if self.state() == Qgis.BrowserItemState.Populated:
            self.refresh()

    def create_child_item(self, item: dict) -> QgsDataItem:
        """Create a folder or file child item."""
        is_directory = item["type"] == "directory"
        display_name = item["id"].rstrip("/").rsplit("/", 1)[-1]
        if is_directory:
            return RanaFolderDataItem(
                self,
                self.loader,
                self.project_id,
                item["id"],
                display_name,
                self.error_signals,
            )
        return RanaFileDataItem(
            self,
            self.loader,
            self.project_id,
            item,
            display_name,
            self.error_signals,
        )


class RanaFilesDataItem(RanaFolderDataItem):
    """Container for the files belonging to a Rana project."""

    def __init__(
        self,
        parent: QgsDataItem,
        loader: Loader,
        project_id: str,
        error_signals: ApiErrorSignals,
    ):
        super().__init__(parent, loader, project_id, "", "Files", error_signals)
