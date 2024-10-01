import os

from qgis.core import QgsMessageLog
from qgis.PyQt import uic
from qgis.PyQt.QtGui import QStandardItem, QStandardItemModel

from rana_qgis_plugin.utils import get_tenant_projects
from rana_qgis_plugin.constant import TENANT

base_dir = os.path.dirname(__file__)
rana_uicls, rana_basecls = uic.loadUiType(os.path.join(base_dir, "ui", "rana.ui"))

class RanaBrowser(rana_uicls, rana_basecls):
    def __init__(self, plugin, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.plugin = plugin
        self.projects_model = QStandardItemModel()
        self.projects_tv.setModel(self.projects_model)
        self.projects = []
        self.fetch_projects()

    def fetch_projects(self):
        self.projects = get_tenant_projects(tenant=TENANT)
        QgsMessageLog.logMessage(f"Projects: {self.projects}")

        self.projects_model.clear()

        header = ["Name"]
        self.projects_model.setHorizontalHeaderLabels(header)
        for project in self.projects:
            name_item = QStandardItem(project["name"])
            project_items = [
                name_item
            ]
            self.projects_model.appendRow(project_items)
        for i in range(len(header)):
            self.projects_tv.resizeColumnToContents(i)
