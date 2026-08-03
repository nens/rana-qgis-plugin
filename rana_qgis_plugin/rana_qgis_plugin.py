"""Rana QGIS plugin entrypoint."""

from typing import Optional

from qgis.core import (
    Qgis,
    QgsApplication,
    QgsDataItem,
    QgsDataItemProvider,
)
from qgis.PyQt.QtCore import QEvent, QObject
from qgis.PyQt.QtWidgets import QApplication

from rana_qgis_plugin.communication import UICommunication
from rana_qgis_plugin.data_items.rana_item import RanaRootDataItem
from rana_qgis_plugin.utils.settings import initialize_settings

PLUGIN_NAME = "Rana"


class RanaDataItemProvider(QgsDataItemProvider):
    """Registers the Rana root item in the QGIS Browser panel."""

    def __init__(self, communication: UICommunication):
        super().__init__()
        self._communication = communication
        self.root_item: Optional[RanaRootDataItem] = None

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
            self.root_item = RanaRootDataItem(self._communication, parentItem)
            self.connect_signals()
            return self.root_item
        return None

    def connect_signals(self) -> None:
        if self.root_item is None:
            return
        self.root_item.fetch_error_occurred.connect(self._communication.show_error)
        self.root_item.connection_lost.connect(
            lambda: self._communication.bar_warn("No connection to Rana")
        )


class RanaQgisPlugin(QObject):
    def __init__(self, iface):
        super().__init__()
        self.iface = iface
        self.communication = UICommunication(iface, PLUGIN_NAME)
        self._data_item_provider = RanaDataItemProvider(self.communication)
        self._externally_deactivated = False

    def initGui(self):
        initialize_settings()
        app = QgsApplication.instance()
        if app is not None:
            registry = app.dataItemProviderRegistry()
            if registry is not None:
                registry.addProvider(self._data_item_provider)
        self.iface.mainWindow().installEventFilter(self)

    def unload(self):
        self.iface.mainWindow().removeEventFilter(self)
        app = QgsApplication.instance()
        if app is not None:
            registry = app.dataItemProviderRegistry()
            if registry is not None:
                registry.removeProvider(self._data_item_provider)

    def eventFilter(self, obj, event) -> bool:
        if event.type() == QEvent.Type.WindowDeactivate:
            if QApplication.activeWindow() is None:
                self._externally_deactivated = True
        elif event.type() == QEvent.Type.WindowActivate:
            if self._externally_deactivated:
                self._externally_deactivated = False
                if self._data_item_provider.root_item is not None:
                    self._data_item_provider.root_item.refresh()
        return False
