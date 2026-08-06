"""Rana file descriptor layer Browser data item."""

from __future__ import annotations

from qgis.core import Qgis, QgsDataItem

from rana_qgis_plugin.api_error_signals import ApiErrorSignals
from rana_qgis_plugin.legacy.widgets.utils_icons import get_icon_from_theme
from rana_qgis_plugin.utils.generic import get_file_icon_name


class RanaLayerDataItem(QgsDataItem):
    """Leaf item representing a layer within a vector file."""

    def __init__(
        self,
        parent: QgsDataItem,
        descriptor_id: str,
        layer_id: str,
        display_name: str,
        geometry_type: str | None,
        error_signals: ApiErrorSignals,
    ):
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
