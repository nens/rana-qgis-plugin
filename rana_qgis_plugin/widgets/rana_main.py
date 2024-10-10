import math
import os

from qgis.PyQt import uic
from qgis.PyQt.QtCore import QSettings, Qt
from qgis.PyQt.QtGui import QStandardItem, QStandardItemModel
from qgis.PyQt.QtWidgets import QLabel, QPushButton, QTableWidgetItem

from rana_qgis_plugin.constant import TENANT
from rana_qgis_plugin.utils import (
    display_bytes,
    get_tenant_project_files,
    get_tenant_projects,
    open_file_in_qgis,
    save_file_to_rana,
)

base_dir = os.path.dirname(__file__)
uicls, basecls = uic.loadUiType(os.path.join(base_dir, "ui", "rana.ui"))


class RanaMainWidget(uicls, basecls):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.settings = QSettings()
        self.paths = ["Home"]

        # Breadcrumbs
        self.breadcrumbs_layout.setAlignment(Qt.AlignLeft)
        self.update_breadcrumbs()

        # Pagination
        self.items_per_page = 10
        self.current_page = 1
        self.btn_previous.clicked.connect(self.to_previous_page)
        self.btn_next.clicked.connect(self.to_next_page)

        # Projects widget
        self.projects = []
        self.project = None
        self.projects_model = QStandardItemModel()
        self.projects_tv.setModel(self.projects_model)
        self.fetch_and_populate_projects()

        # Files widget
        self.files = []
        self.files_model = QStandardItemModel()
        self.files_tv.setModel(self.files_model)
        self.files_tv.doubleClicked.connect(self.select_file_or_directory)

        # File details widget
        self.file = None
        self.btn_open.clicked.connect(lambda: open_file_in_qgis(self.project, self.file))
        self.btn_save.clicked.connect(lambda: save_file_to_rana(self.project, self.file))

    def show_files_widget(self):
        self.rana_widget.setCurrentIndex(1)
        self.update_breadcrumbs()

    def update_breadcrumbs(self):
        # Clear existing breadcrumbs
        for i in reversed(range(self.breadcrumbs_layout.count())):
            widget = self.breadcrumbs_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        # Add the breadcrumbs
        for i, path in enumerate(self.paths):
            btn = QPushButton(path)
            btn.setDisabled(i == len(self.paths) - 1)
            btn.clicked.connect(lambda _, i=i: self.on_breadcrumb_click(i))
            self.breadcrumbs_layout.addWidget(btn)
            if i != len(self.paths) - 1:
                separator = QLabel(">")
                self.breadcrumbs_layout.addWidget(separator)

    def on_breadcrumb_click(self, index):
        self.paths = self.paths[: index + 1]
        if index == 0:
            self.rana_widget.setCurrentIndex(0)
            self.update_breadcrumbs()
        else:
            only_directory_paths = self.paths[2:]  # Skip the first two paths: Home and Project
            path = "/".join(only_directory_paths) + ("/" if only_directory_paths else "")
            self.fetch_and_populate_files(path)
            self.show_files_widget()

    def update_pagination(self):
        total_items = len(self.projects)
        total_pages = math.ceil(total_items / self.items_per_page)
        self.label_page_number.setText(f"{self.current_page}/{total_pages}")
        self.btn_previous.setDisabled(self.current_page == 1)
        self.btn_next.setDisabled(self.current_page == total_pages)

    def to_previous_page(self):
        self.current_page -= 1
        self.fetch_and_populate_projects()

    def to_next_page(self):
        self.current_page += 1
        self.fetch_and_populate_projects()

    def fetch_and_populate_projects(self):
        self.projects = get_tenant_projects(TENANT)
        self.projects_model.clear()
        header = ["Project Name"]
        self.projects_model.setHorizontalHeaderLabels(header)

        # Paginate the projects
        start_index = (self.current_page - 1) * self.items_per_page
        end_index = start_index + self.items_per_page
        paginated_projects = self.projects[start_index:end_index]

        # Add paginated projects to the project model
        for project in paginated_projects:
            name_item = QStandardItem(project["name"])
            name_item.setData(project, role=Qt.UserRole)
            project_items = [name_item]
            self.projects_model.appendRow(project_items)
        for i in range(len(header)):
            self.projects_tv.resizeColumnToContents(i)
        self.projects_tv.doubleClicked.connect(self.select_project)
        self.update_pagination()

    def select_project(self, index):
        project_item = self.projects_model.itemFromIndex(index)
        self.project = project_item.data(Qt.UserRole)
        self.paths.append(self.project["name"])
        self.fetch_and_populate_files()
        self.show_files_widget()

    def fetch_and_populate_files(self, path: str = None):
        self.files = get_tenant_project_files(TENANT, self.project["id"], {"path": path} if path else None)
        self.files_model.clear()
        header = ["Filename"]
        self.files_model.setHorizontalHeaderLabels(header)

        directories = [file for file in self.files if file["type"] == "directory"]
        files = [file for file in self.files if file["type"] == "file"]

        # Add directories first
        for directory in directories:
            dir_name = os.path.basename(directory["id"].rstrip("/"))
            display_name = f"📁 {dir_name}"
            name_item = QStandardItem(display_name)
            name_item.setData(directory, role=Qt.UserRole)
            self.files_model.appendRow([name_item])

        # Add files second
        for file in files:
            file_name = os.path.basename(file["id"].rstrip("/"))
            display_name = f"📄 {file_name}"
            name_item = QStandardItem(display_name)
            name_item.setData(file, role=Qt.UserRole)
            self.files_model.appendRow([name_item])

        for i in range(len(header)):
            self.files_tv.resizeColumnToContents(i)

    def select_file_or_directory(self, index):
        file_item = self.files_model.itemFromIndex(index)
        self.file = file_item.data(Qt.UserRole)
        file_path = self.file["id"]
        if self.file["type"] == "directory":
            directory_name = os.path.basename(file_path.rstrip("/"))
            self.paths.append(directory_name)
            self.fetch_and_populate_files(file_path)
            self.rana_widget.setCurrentIndex(1)
        else:
            file_name = os.path.basename(file_path.rstrip("/"))
            self.paths.append(file_name)
            self.show_file_details()
            self.rana_widget.setCurrentIndex(2)
        self.update_breadcrumbs()

    def show_file_details(self):
        self.file_table_widget.clearContents()
        username = self.file["user"]["given_name"] + " " + self.file["user"]["family_name"]
        file_details = [
            ("Name", os.path.basename(self.file["id"].rstrip("/"))),
            ("Size", display_bytes(self.file["size"])),
            ("Type", self.file["media_type"]),
            ("Added by", username),
            ("Last modified", self.file["last_modified"]),
        ]
        for i, (label, value) in enumerate(file_details):
            self.file_table_widget.setItem(i, 0, QTableWidgetItem(label))
            self.file_table_widget.setItem(i, 1, QTableWidgetItem(value))
        self.file_table_widget.resizeColumnsToContents()
