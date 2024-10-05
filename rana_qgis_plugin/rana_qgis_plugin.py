from qgis.PyQt.QtWidgets import QAction

from .auth import setup_oauth2
from .constant import PLUGIN_NAME
from .widgets.rana_project_browser import RanaProjectBrowser


class RanaQgisPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.menu = PLUGIN_NAME
        self.rana_project_browser = None
        self.action = QAction(self.menu, iface.mainWindow())
        self.action.triggered.connect(self.run)

    def initGui(self):
        """Add the plugin to the QGIS menu."""
        setup_oauth2()
        self.iface.addPluginToMenu(self.menu, self.action)

    def unload(self):
        """Removes the plugin from the QGIS menu."""
        self.iface.removePluginMenu(self.menu, self.action)

    def run(self):
        """Run method that loads and starts the plugin"""
        if not self.rana_project_browser:
            self.rana_project_browser = RanaProjectBrowser()
        self.rana_project_browser.show()
        self.rana_project_browser.raise_()
        self.rana_project_browser.activateWindow()
