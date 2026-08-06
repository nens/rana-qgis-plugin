"""Rana project file Browser data item."""

from __future__ import annotations

from typing import Optional, cast

from qgis.core import Qgis, QgsDataItem, QgsErrorItem

from rana_qgis_plugin.api_error_signals import ApiErrorSignals
from rana_qgis_plugin.data_items.layer_item import RanaLayerDataItem
from rana_qgis_plugin.legacy.widgets.utils_icons import get_icon_from_theme
from rana_qgis_plugin.network_manager import NetworkUnavailableError
from rana_qgis_plugin.utils.api import (
    FetchError,
    get_tenant_file_descriptor,
)
from rana_qgis_plugin.utils.generic import get_file_icon_name


class RanaFileDataItem(QgsDataItem):
    """Browser item representing one file in a Rana project."""

    def __init__(
        self,
        parent: QgsDataItem,
        project_id: str,
        file_path: str,
        display_name: str,
        data_type: str,
        descriptor_id: Optional[str],
        error_signals: ApiErrorSignals,
    ):
        self.project_id = project_id
        self.file_path = file_path
        self.data_type = data_type
        self.descriptor_id = descriptor_id
        self.error_signals = error_signals
        super().__init__(
            Qgis.BrowserItemType.Custom,
            parent,
            display_name,
            f"{parent.path()}/{file_path}",
            "Rana",
        )
        self.setIcon(get_icon_from_theme(get_file_icon_name(data_type)))
        self.setSortKey(f"1:{display_name.lower()}")
        if data_type == "vector":
            self.setCapabilitiesV2(
                cast(
                    Qgis.BrowserItemCapabilities,
                    Qgis.BrowserItemCapability.Fertile
                    | Qgis.BrowserItemCapability.Collapse,
                )
            )
        else:
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
        except FetchError as e:
            self.error_signals.fetch_error_occurred.emit(str(e))
            return [QgsErrorItem(self, "Failed to load layers", self.path())]
        if not descriptor:
            return []
        return [
            RanaLayerDataItem(
                self,
                self.descriptor_id,
                layer.get("id", ""),
                layer.get("name", ""),
                layer.get("type"),
                self.error_signals,
            )
            for layer in descriptor.get("layers", [])
        ]
