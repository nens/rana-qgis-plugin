"""Rana file descriptor layer Browser data item."""

from __future__ import annotations

from typing import TYPE_CHECKING

from qgis.core import Qgis, QgsDataItem
from qgis.PyQt.QtWidgets import QAction

from rana_qgis_plugin.api_error_signals import ApiErrorSignals
from rana_qgis_plugin.data_items.file_actions import FileAction
from rana_qgis_plugin.utils.data_models import OpenLayerRequest
from rana_qgis_plugin.utils.generic import get_file_icon_name
from rana_qgis_plugin.widgets.utils_icons import get_icon_from_theme

if TYPE_CHECKING:
    from rana_qgis_plugin.loader import Loader


class RanaLayerDataItem(QgsDataItem):
    """Leaf item representing a layer within a vector file."""

    def __init__(
        self,
        parent: QgsDataItem,
        loader: Loader,
        descriptor_id: str,
        layer_id: str,
        display_name: str,
        geometry_type: str | None,
        error_signals: ApiErrorSignals,
    ):
        self.loader = loader
        self.descriptor_id = descriptor_id
        self.layer_id = layer_id
        self.geometry_type = geometry_type
        self.error_signals = error_signals
        super().__init__(
            Qgis.BrowserItemType.Custom,
            parent,
            display_name,
            f"{parent.path()}/{layer_id}",
            "Rana",
        )
        self.setIcon(
            get_icon_from_theme(get_file_icon_name((geometry_type or "").lower()))
        )
        self.setState(Qgis.BrowserItemState.Populated)

    def actions(self, parent) -> list:
        """Return the Open in QGIS action."""
        q_action = QAction(FileAction.OPEN_IN_QGIS.value, parent)
        q_action.triggered.connect(lambda: self.handleDoubleClick())
        return [q_action]

    def handleDoubleClick(self) -> bool:
        """Download the parent file and open this single layer."""
        from rana_qgis_plugin.data_items.file_item import RanaFileDataItem

        file_item = self.parent()
        if not isinstance(file_item, RanaFileDataItem):
            return False

        self.loader.open_items(
            [
                OpenLayerRequest(
                    project=file_item.project,
                    file_item=file_item.file_item,
                    layer_name=self.name(),
                    layer_id=self.layer_id,
                )
            ]
        )
        return True
