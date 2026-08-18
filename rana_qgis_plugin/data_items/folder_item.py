"""Rana project folder Browser data item."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from qgis.core import Qgis, QgsDataItem, QgsErrorItem
from qgis.PyQt.QtCore import QUrl
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import QAction, QMessageBox

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
from rana_qgis_plugin.utils.data_models import OpenFolderRequest
from rana_qgis_plugin.utils.generic import get_rana_file_url
from rana_qgis_plugin.widgets.name_input_dialog import NameInputDialog

if TYPE_CHECKING:
    from rana_qgis_plugin.loader import Loader


class RanaFolderDataItem(QgsDataItem):
    """Lazy-loading container for one level of a Rana project folder."""

    def __init__(
        self,
        parent: QgsDataItem,
        loader: Loader,
        project: dict,
        folder_path: str,
        display_name: str,
        error_signals: ApiErrorSignals,
    ):
        self.loader = loader
        self.project = project
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
            files = get_tenant_project_files(self.project["id"], params=params)
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
            if action is FileAction.OPEN_IN_QGIS:
                q_action.triggered.connect(
                    lambda: self.loader.open_items(
                        [OpenFolderRequest(self.project, self.folder_path)]
                    )
                )
            elif action is FileAction.UPLOAD_FILES:
                q_action.triggered.connect(
                    lambda: self.loader.upload_files(
                        {"id": self.project["id"]},
                        self.folder_path,
                        parent,
                        refresh_callback=self.refresh_if_populated,
                    )
                )
            elif action is FileAction.DELETE:
                q_action.triggered.connect(lambda: self.delete_folder(parent))
            elif action is FileAction.CREATE_DIRECTORY:
                q_action.triggered.connect(lambda: self.create_subfolder(parent))
            elif action is FileAction.RENAME:
                q_action.triggered.connect(lambda: self.rename_folder(parent))
            elif action is FileAction.OPEN_IN_BROWSER:
                q_action.triggered.connect(
                    lambda: QDesktopServices.openUrl(
                        QUrl(
                            get_rana_file_url(
                                self.project.get("slug", ""), self.folder_path
                            )
                        )
                    )
                )
            actions.append(q_action)
        return actions

    def refresh_if_populated(self) -> None:
        """Refresh this folder if it has already been populated."""
        if self.state() == Qgis.BrowserItemState.Populated:
            self.refresh()

    def delete_folder(self, parent) -> None:
        """Confirm and delete this folder, then refresh its parent item."""
        if (
            QMessageBox.question(
                parent,
                "Delete folder",
                f"Delete '{self.name()}' and all its contents?",
                QMessageBox.StandardButton.Yes,
                QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return

        error = self.loader.delete_folder(self.project["id"], self.folder_path)
        if error:
            self.loader.communication.show_error(error, parent=parent)
            return
        parent_item = self.parent()
        if parent_item is not None:
            parent_item.refresh()

    def create_subfolder(self, parent) -> None:
        """Open a dialog to create a new subfolder inside this folder."""
        dialog = NameInputDialog(
            "Create folder",
            "Folder name:",
            "",
            lambda name: self.loader.create_folder(
                self.project["id"], self.folder_path, name
            ),
            parent,
        )
        if dialog.exec() == NameInputDialog.DialogCode.Accepted:
            self.refresh_if_populated()

    def rename_folder(self, parent) -> None:
        """Open a dialog to rename this folder."""
        current_name = self.name()
        dialog = NameInputDialog(
            "Rename folder",
            "New name:",
            current_name,
            lambda name: self.loader.rename_item(
                self.project["id"], self.folder_path, name, is_folder=True
            ),
            parent,
        )
        if dialog.exec() == NameInputDialog.DialogCode.Accepted:
            parent_item = self.parent()
            if parent_item is not None:
                parent_item.refresh()

    def create_child_item(self, item: dict) -> QgsDataItem:
        """Create a folder or file child item."""
        is_directory = item["type"] == "directory"
        display_name = item["id"].rstrip("/").rsplit("/", 1)[-1]
        if is_directory:
            return RanaFolderDataItem(
                self,
                self.loader,
                self.project,
                item["id"],
                display_name,
                self.error_signals,
            )
        return RanaFileDataItem(
            self,
            self.loader,
            self.project,
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
        project: dict,
        error_signals: ApiErrorSignals,
    ):
        super().__init__(parent, loader, project, "", "Files", error_signals)
        self.setCapabilitiesV2(
            cast(
                Qgis.BrowserItemCapabilities,
                Qgis.BrowserItemCapability.Fertile
                | Qgis.BrowserItemCapability.Collapse
                | Qgis.BrowserItemCapability.RefreshChildrenWhenItemIsRefreshed,
            )
        )

    # TODO add not implemented create and rename that raise
