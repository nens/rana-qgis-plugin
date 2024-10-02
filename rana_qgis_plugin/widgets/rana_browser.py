import os

from qgis.core import QgsMessageLog
from qgis.PyQt import uic
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QStandardItem, QStandardItemModel

from rana_qgis_plugin.utils import get_tenant_projects, get_tenant_project_files
from rana_qgis_plugin.constant import TENANT

base_dir = os.path.dirname(__file__)
uicls, basecls = uic.loadUiType(os.path.join(base_dir, "ui", "projects.ui"))
browser_uicls, browser_basecls = uic.loadUiType(os.path.join(base_dir, "ui", "browser.ui"))

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

class RanaFileBrowser(browser_uicls, browser_basecls):
    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.parent = parent
        self.project_id = project["id"]
        self.files_model = QStandardItemModel()
        self.files_tv.setModel(self.files_model)
        self.files = []
        self.files_tv.doubleClicked.connect(self.open_directory)
        self.fetch_files()

    def fetch_files(self, path: str = None):
        self.files = get_tenant_project_files(TENANT, self.project_id, {"path": path} if path else None)
        self.files_model.clear()
        header = ["Filename"]
        self.files_model.setHorizontalHeaderLabels(header)
        for file in self.files:
            name_item = QStandardItem(file["id"])
            name_item.setData(file, role=Qt.UserRole)
            file_items = [
                name_item
            ]
            self.files_model.appendRow(file_items)
        for i in range(len(header)):
            self.files_tv.resizeColumnToContents(i)

    def open_directory(self, index):
        file_item = self.files_model.itemFromIndex(index)
        file = file_item.data(Qt.UserRole)
        if file["type"] == "directory":
            self.fetch_files(file["id"])
        else:
            QgsMessageLog.logMessage(f"Open file: {file['id']}")
