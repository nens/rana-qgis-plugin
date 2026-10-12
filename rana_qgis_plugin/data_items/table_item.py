"""Rana file descriptor table Browser data item."""

from __future__ import annotations

from typing import TYPE_CHECKING

from qgis.core import Qgis, QgsDataItem

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
