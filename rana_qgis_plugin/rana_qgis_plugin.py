import os.path

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from .auth import setup_oauth2
from .constant import PLUGIN_NAME
from .widgets.rana_project_browser import RanaProjectBrowser


class RanaQgisPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.menu = PLUGIN_NAME
        self.rana_project_browser = None
        self.toolbar = self.iface.addToolBar(self.menu)
        self.icon = QIcon(os.path.join(os.path.dirname(__file__), "icon.svg"))
        self.action = QAction(self.icon, self.menu, iface.mainWindow())
        self.action.triggered.connect(self.run)

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""
        # Setup OAuth2 authentication
        setup_oauth2()

        # Add the menu item and toolbar icon
        self.iface.addPluginToMenu(self.menu, self.action)
        self.toolbar.addAction(self.action)

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        self.iface.removePluginMenu(self.menu, self.action)
        self.iface.removeToolBarIcon(self.action)

    def run(self):
        """Run method that loads and starts the plugin"""
        if not self.rana_project_browser:
            self.rana_project_browser = RanaProjectBrowser()
        self.rana_project_browser.show()
        self.rana_project_browser.raise_()
        self.rana_project_browser.activateWindow()
