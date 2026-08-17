"""Rana project file Browser data item."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, cast

from qgis.core import Qgis, QgsDataItem, QgsErrorItem
from qgis.PyQt.QtCore import QUrl
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import QAction, QMessageBox

from rana_qgis_plugin.api_error_signals import ApiErrorSignals
from rana_qgis_plugin.data_items.file_actions import (
    FileAction,
    create_separator,
    get_action_tooltip,
    get_file_actions,
)
from rana_qgis_plugin.data_items.layer_item import RanaLayerDataItem
from rana_qgis_plugin.legacy.widgets.utils_icons import get_icon_from_theme
from rana_qgis_plugin.network_manager import NetworkUnavailableError
from rana_qgis_plugin.utils.api import (
    RanaFetchError,
    get_tenant_file_descriptor,
)
from rana_qgis_plugin.utils.generic import get_file_icon_name, get_rana_file_url
from rana_qgis_plugin.widgets.file_info_dialog import (
    FileInfoDialog,
    SchematisationFileInfoDialog,
)

if TYPE_CHECKING:
    from rana_qgis_plugin.loader import Loader


class RanaFileDataItem(QgsDataItem):
    """Browser item representing one file in a Rana project."""

    def __init__(
        self,
        parent: QgsDataItem,
        loader: Loader,
        project: dict,
        file_item: dict,
        display_name: str,
        error_signals: ApiErrorSignals,
    ):
        self.loader = loader
        self.project_id = project["id"]
        self.project = project
        self.file_item = file_item
        self.data_type = file_item.get("data_type", "")
        self.descriptor_id = file_item.get("descriptor_id")
        self.error_signals = error_signals
        super().__init__(
            Qgis.BrowserItemType.Custom,
            parent,
            display_name,
            f"{parent.path()}/{file_item['id']}",
            "Rana",
        )
        self.setIcon(get_icon_from_theme(get_file_icon_name(self.data_type)))
        self.setSortKey(f"1:{display_name.lower()}")
        if self.data_type == "vector":
            self.setCapabilitiesV2(
                cast(
                    Qgis.BrowserItemCapabilities,
                    Qgis.BrowserItemCapability.Fertile
                    | Qgis.BrowserItemCapability.Collapse
                    | Qgis.BrowserItemCapability.Rename,
                )
            )
        else:
            self.setCapabilitiesV2(
                cast(
                    Qgis.BrowserItemCapabilities,
                    Qgis.BrowserItemCapability.Rename,
                )
            )
            self.setState(Qgis.BrowserItemState.Populated)

    def createChildren(self) -> list:
        """Fetch and return the layers contained in a vector file."""
        if self.data_type != "vector" or not self.descriptor_id:
            return []
        try:
            descriptor = get_tenant_file_descriptor(self.descriptor_id)
        except NetworkUnavailableError:
            self.error_signals.connection_lost.emit()
            return [QgsErrorItem(self, "No connection to Rana", self.path())]
        except RanaFetchError as e:
            self.error_signals.fetch_error_occurred.emit(str(e), True)
            return [QgsErrorItem(self, "Failed to load layers", self.path())]
        if not descriptor:
            return []
        return [
            RanaLayerDataItem(
                self,
                self.loader,
                self.descriptor_id,
                layer.get("id", ""),
                layer.get("name", ""),
                layer.get("type"),
                self.error_signals,
            )
            for layer in descriptor.get("layers", [])
        ]

    def actions(self, parent) -> list:
        """Return unconnected file context-menu actions."""
        actions = []
        for action in get_file_actions(self.data_type):
            if action is FileAction.DELETE:
                actions.append(create_separator(parent))
            q_action = QAction(action.value, parent)
            q_action.setIcon(action.icon)
            q_action.setToolTip(get_action_tooltip(action))
            if action is FileAction.VIEW_FILE_INFO:
                q_action.triggered.connect(
                    lambda: (
                        SchematisationFileInfoDialog
                        if self.file_item.get("data_type") == "threedi_schematisation"
                        else FileInfoDialog
                    )(self.file_item, self.error_signals, parent).exec()
                )
            elif action is FileAction.DELETE:
                q_action.triggered.connect(lambda: self.delete_file(parent))
            elif action is FileAction.OPEN_IN_BROWSER:
                q_action.triggered.connect(
                    lambda: QDesktopServices.openUrl(
                        QUrl(
                            get_rana_file_url(
                                self.project["slug"], self.file_item["id"]
                            )
                        )
                    )
                )
            actions.append(q_action)
        return actions

    def delete_file(self, parent) -> None:
        """Confirm and delete this file, then refresh its parent item."""
        if (
            QMessageBox.question(
                parent,
                "Delete file",
                f"Delete '{self.name()}'?",
                QMessageBox.StandardButton.Yes,
                QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return

        error = self.loader.delete_file(self.project_id, self.file_item["id"])
        if error:
            self.loader.communication.show_error(error, parent=parent)
            return
        parent_item = self.parent()
        if parent_item is not None:
            parent_item.refresh()
