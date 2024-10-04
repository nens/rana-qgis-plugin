import os

from qgis.core import QgsMessageLog
from qgis.PyQt import uic
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QStandardItem, QStandardItemModel
from qgis.PyQt.QtWidgets import QLabel, QPushButton

from .rana_file_details import RanaFileDetails
from rana_qgis_plugin.utils import get_tenant_project_files
from rana_qgis_plugin.constant import TENANT

base_dir = os.path.dirname(__file__)
uicls, basecls = uic.loadUiType(os.path.join(base_dir, "ui", "browser.ui"))

class RanaFileBrowser(uicls, basecls):
    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.parent = parent
        self.file_details_widget = RanaFileDetails(self.file_table_widget)
        self.project_id = project["id"]
        self.current_path = []

        self.files = []
        self.files_model = QStandardItemModel()
        self.files_tv.setModel(self.files_model)
        self.files_tv.doubleClicked.connect(self.click_file_or_directory)
        self.fetch_files()

    def fetch_files(self, path: str = None):
        self.files = get_tenant_project_files(TENANT, self.project_id, {"path": path} if path else None)
        self.populate_file_view()
        self.update_breadcrumbs()

    def populate_file_view(self):
        self.files_model.clear()
        header = ["Filename"]
        self.files_model.setHorizontalHeaderLabels(header)
        for file in self.files:
            file_name = os.path.basename(file["id"].rstrip("/"))
            name_item = QStandardItem(file_name)
            name_item.setData(file, role=Qt.UserRole)
            file_items = [
                name_item
            ]
            self.files_model.appendRow(file_items)
        for i in range(len(header)):
            self.files_tv.resizeColumnToContents(i)

    def update_breadcrumbs(self):
        # Clear existing breadcrumbs
        for i in reversed(range(self.breadcrumbs_layout.count())):
            widget = self.breadcrumbs_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        # Align the breadcrumbs to the left
        self.breadcrumbs_layout.setAlignment(Qt.AlignLeft)

        # Add home button
        home_btn = QPushButton("Home")
        home_btn.setCursor(Qt.PointingHandCursor)
        home_btn.setDisabled(len(self.current_path) == 0)
        home_btn.clicked.connect(self.on_home_clicked)
        self.breadcrumbs_layout.addWidget(home_btn)

        # Create breadcrumbs for each directory
        for i, directory in enumerate(self.current_path):
            self.breadcrumbs_layout.addWidget(QLabel(">"))
            btn = QPushButton(directory)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setDisabled(i == len(self.current_path) - 1)
            btn.clicked.connect(lambda checked, i=i: self.on_breadcrumb_clicked(i))
            self.breadcrumbs_layout.addWidget(btn)

    def on_breadcrumb_clicked(self, index):
        self.file_details_widget.hide_file_details()
        self.files_tv.show()
        self.current_path = self.current_path[:index+1]
        path = "/".join(self.current_path) + "/"
        self.fetch_files(path)

    def on_home_clicked(self):
        self.file_details_widget.hide_file_details()
        self.files_tv.show()
        self.current_path = []
        self.fetch_files()

    def click_file_or_directory(self, index):
        file_item = self.files_model.itemFromIndex(index)
        file = file_item.data(Qt.UserRole)
        if file["type"] == "directory":
            directory_name = os.path.basename(file["id"].rstrip("/"))
            self.current_path.append(directory_name)
            self.fetch_files(file["id"])
        else:
            file_name = os.path.basename(file["id"].rstrip("/"))
            self.current_path.append(file_name)
            self.update_breadcrumbs()
            self.files_tv.hide()
            self.file_details_widget.show_file_details(file, self.project_id)
