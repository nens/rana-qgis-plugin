import os

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from rana_qgis_plugin.communication import UICommunication

PLUGIN_NAME = "Rana"
ICONS_DIR = os.path.join(os.path.dirname(__file__), "icons")


class RanaQgisPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.toolbar = iface.addToolBar(PLUGIN_NAME)
        rana_icon = QIcon(os.path.join(ICONS_DIR, "rana.svg"))
        self.action = QAction(rana_icon, PLUGIN_NAME, iface.mainWindow())
        self.communication = UICommunication(iface, PLUGIN_NAME)

    def initGui(self):
        self.action.triggered.connect(self.run)
        self.toolbar.addAction(self.action)

    def unload(self):
        self.toolbar.removeAction(self.action)
        del self.toolbar

    def run(self):
        self.communication.show_info("Rana plugin stub is working!")
