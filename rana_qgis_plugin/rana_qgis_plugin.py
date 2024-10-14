import os.path

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QDockWidget, QSizePolicy

from .auth import setup_oauth2
from .communication import UICommunication
from .constant import PLUGIN_NAME
from .widgets.rana_browser import RanaBrowser


class RanaQgisPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.menu = PLUGIN_NAME
        self.dock_widget = None
        self.rana_browser = None
        self.toolbar = self.iface.addToolBar(self.menu)
        self.toolbar.setObjectName(self.menu)
        self.icon = QIcon(os.path.join(os.path.dirname(__file__), "icon.svg"))
        self.action = QAction(self.icon, self.menu, iface.mainWindow())
        self.action.triggered.connect(self.run)
        self.communication = UICommunication(self.iface, self.menu)

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""
        # Setup OAuth2 authentication
        setup_oauth2(self.communication)

        # Add the menu item and toolbar icon
        self.iface.addPluginToMenu(self.menu, self.action)
        self.toolbar.addAction(self.action)

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        self.iface.removePluginMenu(self.menu, self.action)
        self.iface.removeToolBarIcon(self.action)
        if self.dock_widget:
            self.iface.removeDockWidget(self.dock_widget)
            self.dock_widget.deleteLater()

    def run(self):
        """Run method that loads and starts the plugin"""
        if not self.dock_widget:
            self.dock_widget = QDockWidget(self.menu, self.iface.mainWindow())
            self.dock_widget.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
            self.dock_widget.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable)
            self.dock_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.dock_widget.setObjectName(self.menu)
            self.rana_browser = RanaBrowser(self.communication)
            self.dock_widget.setWidget(self.rana_browser)
        self.iface.addTabifiedDockWidget(Qt.RightDockWidgetArea, self.dock_widget)
        self.dock_widget.show()
