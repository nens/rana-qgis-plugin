import os.path

from qgis.PyQt import uic
from qgis.core import QgsMessageLog
from qgis.PyQt.QtWidgets import QAction, QDialog

from .utils import get_tenant, get_tenant_projects
from .constant import PLUGIN_NAME, TENANT


def classFactory(iface):
    return RanaQgisPlugin(iface)


class RanaQgisPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.menu = PLUGIN_NAME
        self.action = QAction(self.menu, iface.mainWindow())
        self.action.triggered.connect(self.run)

    def initGui(self):
        """Add the plugin to the QGIS menu."""
        self.iface.addPluginToMenu(self.menu, self.action)

    def unload(self):
        """Removes the plugin from the QGIS menu."""
        self.iface.removePluginMenu(self.menu, self.action)

    def run(self):
        # Create a dialog and load the UI
        dialog = QDialog()

        # Load the .ui file
        ui_file = os.path.join(self.plugin_dir, 'ui', 'rana.ui')
        uic.loadUi(ui_file, dialog)

        tenant = get_tenant(tenant=TENANT)
        QgsMessageLog.logMessage(f"Tenant: {tenant}")

        projects = get_tenant_projects(tenant=TENANT)
        QgsMessageLog.logMessage(f"Projects: {projects}")

        # Show the dialog
        dialog.exec_()
