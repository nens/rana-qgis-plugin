"""Rana project folder Browser data item."""

from __future__ import annotations

from typing import cast

from qgis.core import Qgis, QgsDataItem, QgsErrorItem
from qgis.PyQt.QtWidgets import QAction

from rana_qgis_plugin.api_error_signals import ApiErrorSignals
from rana_qgis_plugin.icons import dir_icon
from rana_qgis_plugin.network_manager import NetworkUnavailableError
from rana_qgis_plugin.utils.api import FetchError, get_tenant_project_files


class RanaFolderDataItem(QgsDataItem):
    """Lazy-loading container for one level of a Rana project folder."""

    def __init__(
        self,
        parent: QgsDataItem,
        project_id: str,
        folder_path: str,
        display_name: str,
        error_signals: ApiErrorSignals,
    ):
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
        except FetchError as e:
            self.error_signals.fetch_error_occurred.emit(str(e))
            return [QgsErrorItem(self, "Failed to load files", self.path())]

        return [self.create_child_item(item) for item in files]

    def actions(self, parent) -> list:
        """Return a Refresh action scoped to this folder's children."""
        refresh_action = QAction("Refresh", parent)
        refresh_action.triggered.connect(self.refresh)
        return [refresh_action]

    def create_child_item(self, item: dict) -> QgsDataItem:
        """Create a folder or file placeholder child item."""
        is_directory = item["type"] == "directory"
        display_name = item["id"].rstrip("/").rsplit("/", 1)[-1]
        if is_directory:
            return RanaFolderDataItem(
                self,
                self.project_id,
                item["id"],
                item["id"].rstrip("/").rsplit("/", 1)[-1],
                self.error_signals,
            )
        child = QgsDataItem(
            Qgis.BrowserItemType.Custom,
            self,
            display_name,
            f"{self.path()}/{item['id']}",
            "Rana",
        )
        child.setIcon(dir_icon)
        child.setSortKey(f"1:{display_name.lower()}")
        child.setState(Qgis.BrowserItemState.Populated)
        return child


class RanaFilesDataItem(RanaFolderDataItem):
    """Container for the files belonging to a Rana project."""

    def __init__(
        self,
        parent: QgsDataItem,
        project_id: str,
        error_signals: ApiErrorSignals,
    ):
        super().__init__(parent, project_id, "", "Files", error_signals)
