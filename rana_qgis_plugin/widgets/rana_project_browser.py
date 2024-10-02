import os

from qgis.core import QgsMessageLog
from qgis.PyQt import uic
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QStandardItem, QStandardItemModel

from .rana_file_browser import RanaFileBrowser
from rana_qgis_plugin.utils import get_tenant_projects
from rana_qgis_plugin.constant import TENANT

base_dir = os.path.dirname(__file__)
uicls, basecls = uic.loadUiType(os.path.join(base_dir, "ui", "projects.ui"))

class RanaProjectBrowser(uicls, basecls):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.projects_model = QStandardItemModel()
        self.projects_tv.setModel(self.projects_model)
        self.projects = []
        self.fetch_projects()

    def fetch_projects(self):
        self.projects = get_tenant_projects(TENANT)
        self.projects_model.clear()
        header = ["Name"]
        self.projects_model.setHorizontalHeaderLabels(header)
        for project in self.projects:
            name_item = QStandardItem(project["name"])
            name_item.setData(project, role=Qt.UserRole)
            project_items = [
                name_item
            ]
            self.projects_model.appendRow(project_items)
        for i in range(len(header)):
            self.projects_tv.resizeColumnToContents(i)
        self.projects_tv.doubleClicked.connect(self.select_project)

    def select_project(self, index):
        project_item = self.projects_model.itemFromIndex(index)
        project = project_item.data(Qt.UserRole)
        project_name = project["name"]
        fileBrowser = RanaFileBrowser(project)
        fileBrowser.setWindowTitle(f"Browse project files for {project_name}")
        fileBrowser.exec_()
