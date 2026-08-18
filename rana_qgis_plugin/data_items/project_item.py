"""Rana project Browser data item."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from qgis.core import Qgis, QgsDataItem
from qgis.PyQt.QtCore import QUrl
from qgis.PyQt.QtGui import QDesktopServices, QIcon
from qgis.PyQt.QtWidgets import QAction

from rana_qgis_plugin.api_error_signals import ApiErrorSignals
from rana_qgis_plugin.constant import ICONS_DIR
from rana_qgis_plugin.data_items.folder_item import RanaFilesDataItem
from rana_qgis_plugin.utils.settings import base_url, get_tenant_id, hide_project

if TYPE_CHECKING:
    from rana_qgis_plugin.loader import Loader


class RanaProjectDataItem(QgsDataItem):
    """Browser item representing a single Rana project."""

    def __init__(
        self,
        parent: QgsDataItem,
        loader: Loader,
        project: dict,
        error_signals: ApiErrorSignals,
    ):
        self.loader = loader
        self.project = project
        self.slug = project.get("slug", "")
        self.error_signals = error_signals
        super().__init__(
            Qgis.BrowserItemType.Collection,
            parent,
            project["name"],
            f"/Rana/projects/{project['id']}",
            "Rana",
        )
        self.setIcon(QIcon(str(ICONS_DIR / "rana.svg")))
        self.setCapabilitiesV2(
            cast(
                Qgis.BrowserItemCapabilities,
                Qgis.BrowserItemCapability.Fertile
                | Qgis.BrowserItemCapability.Collapse
                | Qgis.BrowserItemCapability.RefreshChildrenWhenItemIsRefreshed,
            )
        )

    def createChildren(self) -> list:
        """Return the files container for this project."""
        return [
            RanaFilesDataItem(
                self,
                self.loader,
                self.project,
                self.error_signals,
            )
        ]

    def actions(self, parent) -> list:
        url = f"{base_url()}/{get_tenant_id()}/projects/{self.slug}"
        open_action = QAction("Open project on web", parent)
        open_action.setIcon(QIcon(str(ICONS_DIR / "link.svg")))
        open_action.triggered.connect(lambda: QDesktopServices.openUrl(QUrl(url)))

        hide_action = QAction("Don't show this project", parent)
        hide_action.triggered.connect(self.hide_project)

        return [open_action, hide_action]

    def hide_project(self) -> None:
        hide_project(base_url(), get_tenant_id(), self.project["id"])
        parent = self.parent()
        if parent:
            parent.refresh()
