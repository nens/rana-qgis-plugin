"""Rana project Browser data item."""

from __future__ import annotations

from qgis.core import Qgis, QgsDataItem
from qgis.PyQt.QtCore import QUrl
from qgis.PyQt.QtGui import QDesktopServices, QIcon
from qgis.PyQt.QtWidgets import QAction

from rana_qgis_plugin.constant import ICONS_DIR
from rana_qgis_plugin.utils.settings import base_url, get_tenant_id, hide_project


class RanaProjectDataItem(QgsDataItem):
    """Browser item representing a single Rana project."""

    def __init__(self, parent: QgsDataItem, project_id: str, name: str, slug: str):
        self.project_id = project_id
        self.slug = slug
        super().__init__(
            Qgis.BrowserItemType.Custom,
            parent,
            name,
            f"/Rana/projects/{project_id}",
            "Rana",
        )
        self.setState(Qgis.BrowserItemState.Populated)
        self.setIcon(QIcon(str(ICONS_DIR / "rana.svg")))

    def actions(self, parent) -> list:
        url = f"{base_url()}/{get_tenant_id()}/projects/{self.slug}"
        open_action = QAction("Open project on web", parent)
        open_action.setIcon(QIcon(str(ICONS_DIR / "link.svg")))
        open_action.triggered.connect(lambda: QDesktopServices.openUrl(QUrl(url)))

        hide_action = QAction("Don't show this project", parent)
        hide_action.triggered.connect(self.hide_project)

        return [open_action, hide_action]

    def hide_project(self) -> None:
        hide_project(base_url(), get_tenant_id(), self.project_id)
        parent = self.parent()
        if parent:
            parent.refresh()
