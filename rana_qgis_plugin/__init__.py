from qgis.core import QgsMessageLog
from qgis.PyQt.QtWidgets import QAction

from .utils import get_tenant, get_tenant_projects
from .constant import PLUGIN_NAME, TENANT
from .widgets.rana_browser import RanaBrowser


def classFactory(iface):
    return RanaQgisPlugin(iface)


class RanaQgisPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.menu = PLUGIN_NAME
        self.rana_browser = None
        self.action = QAction(self.menu, iface.mainWindow())
        self.action.triggered.connect(self.run)

    def initGui(self):
        """Add the plugin to the QGIS menu."""
        self.iface.addPluginToMenu(self.menu, self.action)

    def unload(self):
        """Removes the plugin from the QGIS menu."""
        self.iface.removePluginMenu(self.menu, self.action)

    def run(self):
        """Run method that loads and starts the plugin"""
        if not self.rana_browser:
            self.rana_browser = RanaBrowser(self)
        self.rana_browser.show()
        self.rana_browser.raise_()
        self.rana_browser.activateWindow()

        tenant = get_tenant(tenant=TENANT)
        QgsMessageLog.logMessage(f"Tenant: {tenant}")

        projects = get_tenant_projects(tenant=TENANT)
        QgsMessageLog.logMessage(f"Projects: {projects}")
