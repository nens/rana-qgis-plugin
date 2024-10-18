import math
import os

from qgis.PyQt import uic
from qgis.PyQt.QtCore import QSettings, Qt
from qgis.PyQt.QtGui import QStandardItem, QStandardItemModel
from qgis.PyQt.QtWidgets import QLabel, QTableWidgetItem

from rana_qgis_plugin.communication import UICommunication
from rana_qgis_plugin.constant import TENANT
from rana_qgis_plugin.utils import display_bytes, elide_text, open_file_in_qgis, save_file_to_rana
from rana_qgis_plugin.utils_api import get_tenant_project_files, get_tenant_projects, get_threedi_schematisation

base_dir = os.path.dirname(__file__)
uicls, basecls = uic.loadUiType(os.path.join(base_dir, "ui", "rana.ui"))


class RanaBrowser(uicls, basecls):
    SUPPORTED_DATA_TYPES = ["vector", "raster", "threedi_schematisation"]

    def __init__(self, communication: UICommunication, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.communication = communication
        self.settings = QSettings()
        self.paths = ["Projects"]

        # Breadcrumbs
        self.breadcrumbs_layout.setAlignment(Qt.AlignLeft)
        self.update_breadcrumbs()

        # Pagination
        self.items_per_page = 25
        self.current_page = 1
        self.btn_previous.clicked.connect(self.to_previous_page)
        self.btn_next.clicked.connect(self.to_next_page)

        # Projects widget
        self.projects = []
        self.filtered_projects = []
        self.project = None
        self.projects_model = QStandardItemModel()
        self.projects_tv.setModel(self.projects_model)
        self.projects_tv.doubleClicked.connect(self.select_project)
        self.projects_search.textChanged.connect(self.filter_projects)
        self.fetch_projects()
        self.populate_projects(self.projects)

        # Files widget
        self.files = []
        self.files_model = QStandardItemModel()
        self.files_tv.setModel(self.files_model)
        self.files_tv.doubleClicked.connect(self.select_file_or_directory)

        # File details widget
        self.selected_file = None
        self.schematisation = None
        self.btn_open.clicked.connect(
            lambda: open_file_in_qgis(
                communication=self.communication,
                project=self.project,
                file=self.selected_file,
                schematisation_instance=self.schematisation,
                supported_data_types=self.SUPPORTED_DATA_TYPES,
            )
        )
        self.btn_save.clicked.connect(lambda: save_file_to_rana(self.communication, self.project, self.selected_file))

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
            label_text = elide_text(self.font(), path, 100)
            link = f"<a href='{i}'>{label_text}</a>"
            label = QLabel(label_text if i == len(self.paths) - 1 else link)
            label.setTextFormat(Qt.RichText)
            label.setTextInteractionFlags(Qt.TextBrowserInteraction)
            label.linkActivated.connect(lambda _, i=i: self.on_breadcrumb_click(i))
            self.breadcrumbs_layout.addWidget(label)
            if i != len(self.paths) - 1:
                separator = QLabel(">")
                self.breadcrumbs_layout.addWidget(separator)

    def on_breadcrumb_click(self, index: int):
        self.paths = self.paths[: index + 1]
        if index == 0:
            self.rana_widget.setCurrentIndex(0)
            self.update_breadcrumbs()
        else:
            only_directory_paths = self.paths[2:]  # Skip the first two paths: Projects and project_name
            path = "/".join(only_directory_paths) + ("/" if only_directory_paths else "")
            self.fetch_and_populate_files(path)
            self.show_files_widget()

    def update_pagination(self, projects: list):
        total_items = len(projects)
        total_pages = math.ceil(total_items / self.items_per_page)
        self.label_page_number.setText(f"Page {self.current_page}/{total_pages}")
        self.btn_previous.setDisabled(self.current_page == 1)
        self.btn_next.setDisabled(self.current_page == total_pages)

    def to_previous_page(self):
        self.current_page -= 1
        self.populate_projects(self.filtered_projects if self.filtered_projects else self.projects)

    def to_next_page(self):
        self.current_page += 1
        self.populate_projects(self.filtered_projects if self.filtered_projects else self.projects)

    def fetch_projects(self):
        self.projects = get_tenant_projects(self.communication, TENANT)

    def populate_projects(self, projects: list):
        self.projects_model.clear()
        header = ["Project Name"]
        self.projects_model.setHorizontalHeaderLabels(header)

        # Paginate projects
        start_index = (self.current_page - 1) * self.items_per_page
        end_index = start_index + self.items_per_page
        paginated_projects = projects[start_index:end_index]

        # Add paginated projects to the project model
        for project in paginated_projects:
            name_item = QStandardItem(project["name"])
            name_item.setData(project, role=Qt.UserRole)
            self.projects_model.appendRow([name_item])
        for i in range(len(header)):
            self.projects_tv.resizeColumnToContents(i)
        self.update_pagination(projects)

    def filter_projects(self, text: str):
        self.current_page = 1
        self.filtered_projects = [project for project in self.projects if text.lower() in project["name"].lower()]
        self.populate_projects(self.filtered_projects)

    def select_project(self, index: int):
        project_item = self.projects_model.itemFromIndex(index)
        self.project = project_item.data(Qt.UserRole)
        self.paths.append(self.project["name"])
        self.fetch_and_populate_files()
        self.show_files_widget()

    def fetch_and_populate_files(self, path: str = None):
        self.files = get_tenant_project_files(
            self.communication, TENANT, self.project["id"], {"path": path} if path else None
        )
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

    def select_file_or_directory(self, index: int):
        file_item = self.files_model.itemFromIndex(index)
        self.selected_file = file_item.data(Qt.UserRole)
        file_path = self.selected_file["id"]
        if self.selected_file["type"] == "directory":
            directory_name = os.path.basename(file_path.rstrip("/"))
            self.paths.append(directory_name)
            self.fetch_and_populate_files(file_path)
            self.rana_widget.setCurrentIndex(1)
        else:
            file_name = os.path.basename(file_path.rstrip("/"))
            self.paths.append(file_name)
            self.show_selected_file_details()
            self.rana_widget.setCurrentIndex(2)
        self.update_breadcrumbs()

    def show_selected_file_details(self):
        self.file_table_widget.clearContents()
        username = self.selected_file["user"]["given_name"] + " " + self.selected_file["user"]["family_name"]
        data_type = self.selected_file["descriptor"]["data_type"] if self.selected_file["descriptor"] else "Unknown"
        file_details = [
            ("Name", os.path.basename(self.selected_file["id"].rstrip("/"))),
            ("Size", display_bytes(self.selected_file["size"])),
            ("File type", self.selected_file["media_type"]),
            ("Data type", data_type),
            ("Added by", username),
            ("Last modified", self.selected_file["last_modified"]),
        ]
        if data_type == "threedi_schematisation":
            self.schematisation = get_threedi_schematisation(
                self.communication, TENANT, self.selected_file["descriptor_id"]
            )
            if self.schematisation:
                schematisation = self.schematisation["schematisation"]
                revision = self.schematisation["latest_revision"]
                schematisation_details = [
                    ("Schematisation ID", schematisation["id"]),
                    ("Latest revision ID", revision["id"] if revision else None),
                ]
                file_details.extend(schematisation_details)
            else:
                self.communication.show_error("Failed to download 3Di schematisation.")
        self.file_table_widget.setRowCount(len(file_details))
        self.file_table_widget.horizontalHeader().setStretchLastSection(True)
        for i, (label, value) in enumerate(file_details):
            self.file_table_widget.setItem(i, 0, QTableWidgetItem(label))
            self.file_table_widget.setItem(i, 1, QTableWidgetItem(str(value)))
        self.file_table_widget.resizeColumnsToContents()

        # Show/hide the buttons based on the file data type
        if data_type == "threedi_schematisation":
            self.btn_open.show()
            self.btn_save.hide()
        elif data_type in self.SUPPORTED_DATA_TYPES:
            self.btn_open.show()
            self.btn_save.show()
        else:
            self.btn_open.hide()
            self.btn_save.hide()
