"""Rana file descriptor table Browser data item."""

from __future__ import annotations

from typing import TYPE_CHECKING

from qgis.core import Qgis, QgsDataItem
from qgis.PyQt.QtWidgets import QAction

from rana_qgis_plugin.data_items.file_actions import FileAction
from rana_qgis_plugin.utils.data_models import OpenVectorFileRequest, VectorTableRef
from rana_qgis_plugin.utils.generic import get_file_icon_name
from rana_qgis_plugin.widgets.utils_icons import get_icon_from_theme

if TYPE_CHECKING:
    from rana_qgis_plugin.loader import Loader


class RanaTableDataItem(QgsDataItem):
    """Leaf item representing a geometryless table within a vector file."""

    def __init__(
        self,
        parent: QgsDataItem,
        loader: Loader,
        table_id: str,
        display_name: str,
    ):
        self.loader = loader
        self.table_id = table_id
        super().__init__(
            Qgis.BrowserItemType.Custom,
            parent,
            display_name,
            f"{parent.path()}/{table_id}",
            "Rana",
        )
        self.setIcon(get_icon_from_theme(get_file_icon_name("table")))
        self.setState(Qgis.BrowserItemState.Populated)

    def actions(self, parent) -> list:
        """Return the Open in QGIS action."""
        q_action = QAction(FileAction.OPEN_IN_QGIS.value, parent)
        q_action.triggered.connect(lambda: self.handleDoubleClick())
        return [q_action]

    def handleDoubleClick(self) -> bool:
        """Download the parent vector file and open this table."""
        from rana_qgis_plugin.data_items.file_item import RanaFileDataItem

        file_item = self.parent()
        if not isinstance(file_item, RanaFileDataItem):
            return False

        self.loader.open_items(
            [
                OpenVectorFileRequest(
                    project=file_item.project,
                    file_item=file_item.file_item,
                    children=(VectorTableRef(name=self.table_id, id=self.table_id),),
                )
            ]
        )
        return True
