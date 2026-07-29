"""Rana QGIS plugin entrypoint."""

from typing import Optional

from qgis.core import (
    Qgis,
    QgsApplication,
    QgsDataItem,
    QgsDataItemProvider,
)

from rana_qgis_plugin.communication import UICommunication
from rana_qgis_plugin.data_items.rana_item import RanaRootDataItem
from rana_qgis_plugin.utils.settings import initialize_settings

PLUGIN_NAME = "Rana"


class RanaDataItemProvider(QgsDataItemProvider):
    """Registers the Rana root item in the QGIS Browser panel."""

    def __init__(self, communication: UICommunication):
        super().__init__()
        self._communication = communication

    def name(self) -> str:
        return "Rana"

    def capabilities(self) -> Qgis.DataItemProviderCapabilities:
        return Qgis.DataItemProviderCapabilities(
            Qgis.DataItemProviderCapability.NetworkSources
        )

    def createDataItem(
        self, path: Optional[str], parentItem: Optional[QgsDataItem]
    ) -> Optional[QgsDataItem]:
        if parentItem is None:
            return RanaRootDataItem(self._communication, parentItem)
        return None


class RanaQgisPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.communication = UICommunication(iface, PLUGIN_NAME)
        self._data_item_provider = RanaDataItemProvider(self.communication)

    def initGui(self):
        initialize_settings()
        app = QgsApplication.instance()
        if app is not None:
            registry = app.dataItemProviderRegistry()
            if registry is not None:
                registry.addProvider(self._data_item_provider)

    def unload(self):
        app = QgsApplication.instance()
        if app is not None:
            registry = app.dataItemProviderRegistry()
            if registry is not None:
                registry.removeProvider(self._data_item_provider)
