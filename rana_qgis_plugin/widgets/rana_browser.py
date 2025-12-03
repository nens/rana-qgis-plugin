import math
import os
from collections import namedtuple
from enum import Enum
from pathlib import Path
from typing import List

from qgis.PyQt.QtCore import QModelIndex, QSettings, Qt, pyqtSignal, pyqtSlot
from qgis.PyQt.QtGui import QAction, QPixmap, QStandardItem, QStandardItemModel
from qgis.PyQt.QtSvg import QSvgWidget
from qgis.PyQt.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QStackedWidget,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QToolButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from rana_qgis_plugin.auth_3di import get_3di_auth
from rana_qgis_plugin.communication import UICommunication
from rana_qgis_plugin.constant import SUPPORTED_DATA_TYPES
from rana_qgis_plugin.icons import ICONS_DIR, dir_icon, file_icon, refresh_icon
from rana_qgis_plugin.simulation.threedi_calls import (
    ThreediCalls,
    get_api_client_with_personal_api_token,
)
from rana_qgis_plugin.utils import (
    NumericItem,
    convert_to_local_time,
    convert_to_relative_time,
    convert_to_timestamp,
    display_bytes,
    elide_text,
)
from rana_qgis_plugin.utils_api import (
    get_frontend_settings,
    get_tenant_file_descriptor,
    get_tenant_project_file,
    get_tenant_project_file_history,
    get_tenant_project_files,
    get_tenant_projects,
    get_threedi_schematisation,
)


class RevisionsView(QWidget):
    new_simulation_clicked = pyqtSignal(int)
    busy = pyqtSignal()
    ready = pyqtSignal()

    def __init__(self, communication, parent=None):
        super().__init__(parent)
        self.communication = communication
        self.revisions = []
        self.selected_file = None
        self.project = None
        self.setup_ui()

    def setup_ui(self):
        revisions_refreash_btn = QToolButton()
        revisions_refreash_btn.setToolTip("Refresh")
        revisions_refreash_btn.clicked.connect(self.show_revisions)
        revisions_refreash_btn.setIcon(refresh_icon)
        self.revisions_table = QTableView()
        self.revisions_table.setSortingEnabled(True)
        self.revisions_table.verticalHeader().hide()
        self.revisions_model = QStandardItemModel()
        self.revisions_model.setColumnCount(3)
        self.revisions_model.setHorizontalHeaderLabels(["Timestamp", "Event", ""])
        self.revisions_table.setModel(self.revisions_model)
        self.revisions_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        layout = QVBoxLayout(self)
        layout.addWidget(revisions_refreash_btn)
        layout.addWidget(self.revisions_table)
        self.setLayout(layout)

    def show_revisions_for_file(self, project: dict, selected_file: dict):
        self.project = project
        self.selected_file = selected_file
        self.show_revisions()

    def show_revisions(self):
        self.busy.emit()
        selected_file = self.selected_file
        self.revisions_model.clear()
        # collect rows to show in widget, format: [date_str, event, (button_label, signal_func)]
        rows = []
        if selected_file.get("data_type") == "threedi_schematisation":
            # retrieve schematisation and revisions
            schematisation = get_threedi_schematisation(
                self.communication, selected_file["descriptor_id"]
            )
            _, personal_api_token = get_3di_auth()
            frontend_settings = get_frontend_settings()
            api_url = frontend_settings["hcc_url"].rstrip("/")
            threedi_api = get_api_client_with_personal_api_token(
                personal_api_token, api_url
            )
            tc = ThreediCalls(threedi_api)
            revisions = tc.fetch_schematisation_revisions(
                schematisation["schematisation"]["id"]
            )
            # Extract data from each revision
            for i, revision in enumerate(revisions):
                date_str = revision.commit_date.strftime("%d-%m-%y %H:%M")
                if revision.id == schematisation["latest_revision"]["id"]:
                    date_str += " (latest)"
                if revision.has_threedimodel:
                    btn_data = (
                        "New simulation",
                        lambda _: self.new_simulation_clicked.emit(revision.id),
                    )
                else:
                    btn_data = None
                rows.append([date_str, revision.commit_message, btn_data])
        else:
            history = get_tenant_project_file_history(
                self.project["id"], {"path": self.selected_file["id"]}
            )
            for item in history["items"]:
                date_str = convert_to_local_time(item["created_at"])
                rows.append([date_str, item["message"], None])

        # Populate table
        self.revisions_model.setHorizontalHeaderLabels(["Timestamp", "Event", ""])
        for i, (date_str, event, btn_data) in enumerate(rows):
            self.revisions_model.appendRow(
                [
                    QStandardItem(date_str),
                    QStandardItem(event),
                    QStandardItem(""),
                ]
            )
            if btn_data:
                btn_label, btn_func = btn_data
                btn = QPushButton(btn_label)
                btn.clicked.connect(btn_func)
                self.revisions_table.setIndexWidget(
                    self.revisions_model.index(i, 2), btn
                )
        self.ready.emit()


class FileView(QWidget):
    file_showed = pyqtSignal()
    show_revisions_clicked = pyqtSignal(dict, dict)

    def __init__(self, communication, parent=None):
        super().__init__(parent)
        self.communication = communication
        self.selected_file = None
        self.project = None
        self.setup_ui()

    def update_project(self, project: dict):
        self.project = project

    def setup_ui(self):
        file_refresh_btn = QToolButton()
        file_refresh_btn.setToolTip("Refresh")
        file_refresh_btn.clicked.connect(self.refresh)
        file_refresh_btn.setIcon(refresh_icon)
        self.file_table_widget = QTableWidget(1, 2)
        self.file_table_widget.horizontalHeader().setVisible(False)
        self.file_table_widget.verticalHeader().setVisible(False)
        button_layout = QHBoxLayout()
        self.btn_start_simulation = QPushButton("Start Simulation")
        self.btn_create_model = QPushButton("Create 3Di Model")
        self.btn_show_revisions = QPushButton("Show Revisions")
        self.btn_show_revisions.clicked.connect(
            lambda _: self.show_revisions_clicked.emit(self.project, self.selected_file)
        )
        button_layout.addWidget(self.btn_start_simulation)
        button_layout.addWidget(self.btn_create_model)
        button_layout.addWidget(self.btn_show_revisions)
        layout = QVBoxLayout(self)
        layout.addWidget(file_refresh_btn)
        layout.addWidget(self.file_table_widget)
        layout.addLayout(button_layout)
        self.setLayout(layout)

    def show_selected_file_details(self, selected_file):
        self.selected_file = selected_file
        self.file_table_widget.clearContents()
        schematisation_button = None
        self.btn_create_model.hide()
        self.btn_start_simulation.hide()
        filename = os.path.basename(selected_file["id"].rstrip("/"))
        username = (
            selected_file["user"]["given_name"]
            + " "
            + selected_file["user"]["family_name"]
        )
        data_type = selected_file["data_type"]
        meta = None
        descriptor = get_tenant_file_descriptor(selected_file["descriptor_id"])
        meta = descriptor["meta"] if descriptor else None
        description = descriptor["description"] if descriptor else None

        last_modified = convert_to_local_time(selected_file["last_modified"])
        size = (
            display_bytes(selected_file["size"])
            if data_type != "threedi_schematisation"
            else "N/A"
        )
        file_details = [
            ("Name", filename),
            ("Size", size),
            ("File type", selected_file["media_type"]),
            ("Data type", SUPPORTED_DATA_TYPES.get(data_type, data_type)),
            ("Added by", username),
            ("Last modified", last_modified),
            ("Description", description),
        ]
        if data_type == "scenario" and meta:
            simulation = meta["simulation"]
            schematisation = meta["schematisation"]
            interval = simulation["interval"]
            if interval:
                start = convert_to_local_time(interval[0])
                end = convert_to_local_time(interval[1])
            else:
                start = "N/A"
                end = "N/A"
            scenario_details = [
                ("Simulation name", simulation["name"]),
                ("Simulation ID", simulation["id"]),
                ("Schematisation name", schematisation["name"]),
                ("Schematisation ID", schematisation["id"]),
                ("Schematisation version", schematisation["version"]),
                ("Revision ID", schematisation["revision_id"]),
                ("Model ID", schematisation["model_id"]),
                ("Model software", simulation["software"]["id"]),
                ("Software version", simulation["software"]["version"]),
                ("Start", start),
                ("End", end),
            ]
            file_details.extend(scenario_details)
        if data_type == "threedi_schematisation":
            schematisation = get_threedi_schematisation(
                self.communication, selected_file["descriptor_id"]
            )
            if schematisation:
                revision = schematisation["latest_revision"]
                schematisation_details = [
                    ("Schematisation ID", schematisation["schematisation"]["id"]),
                    ("Latest revision ID", revision["id"] if revision else None),
                    (
                        "Latest revision number",
                        revision["number"] if revision else None,
                    ),
                ]
                if revision.get("has_threedimodel"):
                    schematisation_button = self.btn_start_simulation
                else:
                    schematisation_button = self.btn_create_model
                file_details.extend(schematisation_details)
            else:
                self.communication.show_error("Failed to download 3Di schematisation.")
        self.file_table_widget.setRowCount(len(file_details))
        self.file_table_widget.horizontalHeader().setStretchLastSection(True)
        for i, (label, value) in enumerate(file_details):
            label_item = QTableWidgetItem(label)
            label_item.setFlags(
                Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
            )
            value_item = QTableWidgetItem(str(value))
            value_item.setFlags(
                Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
            )
            self.file_table_widget.setItem(i, 0, label_item)
            self.file_table_widget.setItem(i, 1, value_item)
        self.file_table_widget.resizeColumnsToContents()

        # Show/hide the buttons based on the file data type
        if schematisation_button:
            schematisation_button.show()
        self.file_showed.emit()

    def refresh(self):
        assert self.selected_file
        self.selected_file = get_tenant_project_file(
            self.project["id"], {"path": self.selected_file["id"]}
        )
        last_modified_key = (
            f"{self.project['name']}/{self.selected_file['id']}/last_modified"
        )
        QSettings().setValue(last_modified_key, self.selected_file["last_modified"])
        self.show_selected_file_details(self.selected_file)


class FilesBrowser(QWidget):
    folder_selected = pyqtSignal(str)
    file_selected = pyqtSignal(dict)
    path_changed = pyqtSignal(str)
    busy = pyqtSignal()
    ready = pyqtSignal()
    file_deletion_requested = pyqtSignal(dict)
    open_in_qgis_requested = pyqtSignal(dict)
    upload_file_requested = pyqtSignal(dict)
    save_vector_styling_requested = pyqtSignal(dict)
    open_wms_requested = pyqtSignal(dict)
    download_file_requested = pyqtSignal(dict)
    download_results_requested = pyqtSignal(dict)

    def __init__(self, communication, parent=None):
        super().__init__(parent)
        self.project = None
        self.communication = communication
        self.selected_item = None
        self.setup_ui()

    def update_project(self, project: dict):
        self.project = project
        self.selected_item = {"id": "", "type": "directory"}
        self.fetch_and_populate(project)

    def setup_ui(self):
        project_refresh_btn = QToolButton()
        project_refresh_btn.setToolTip("Refresh")
        project_refresh_btn.setIcon(refresh_icon)
        project_refresh_btn.clicked.connect(self.update)
        self.files_tv = QTreeView()
        self.files_tv.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.files_tv.customContextMenuRequested.connect(self.menu_requested)
        self.files_model = QStandardItemModel()
        self.files_tv.setModel(self.files_model)
        self.files_tv.setSortingEnabled(True)
        self.files_tv.header().setSortIndicatorShown(True)
        self.files_tv.doubleClicked.connect(self.select_file_or_directory)
        self.btn_upload = QPushButton("Upload Files to Rana")
        layout = QVBoxLayout(self)
        # todo: move refresh to far right (some day)
        layout.addWidget(project_refresh_btn)
        layout.addWidget(self.files_tv)
        layout.addWidget(self.btn_upload)
        self.setLayout(layout)

    def refresh(self):
        self.update()

    def update(self):
        selected_path = self.selected_item["id"]
        selected_name = Path(selected_path.rstrip("/")).name
        if self.selected_item["type"] == "directory":
            self.fetch_and_populate(self.project, selected_path)
            self.folder_selected.emit(selected_name)
        else:
            self.file_selected.emit(self.selected_item)
        self.communication.clear_message_bar()

    def menu_requested(self, pos):
        index = self.files_tv.indexAt(pos)
        file_item = self.files_model.itemFromIndex(index)
        if not file_item:
            return
        selected_item = file_item.data(Qt.ItemDataRole.UserRole)
        data_type = selected_item["data_type"]
        # Add delete option files and folders
        actions = [("Delete", self.file_deletion_requested)]
        # Add open in QGIS is supported for all supported data types
        if data_type in SUPPORTED_DATA_TYPES:
            actions.append(("Open in QGIS", self.open_in_qgis_requested))
        # Add save only for vector and raster files
        if data_type in ["vector", "raster"]:
            actions.append(("Save data to Rana", self.upload_file_requested))
        # Add save vector style only for vector files
        if data_type == "vector":
            actions.append(
                ("Save vector style to Rana", self.save_vector_styling_requested)
            )
        # Add options to open WMS and download file and results only for 3Di scenarios
        if data_type == "scenario":
            descriptor = get_tenant_file_descriptor(selected_item["descriptor_id"])
            meta = descriptor["meta"] if descriptor else None
            if meta and meta["simulation"]["software"]["id"] == "3Di":
                actions.append(("Open WMS in QGIS", self.open_wms_requested))
                actions.append(("Download", self.download_file_requested))
                actions.append(("Download results", self.download_results_requested))
        # populate menu
        menu = QMenu(self)
        for action_label, action_signal in actions:
            action = QAction(action_label, self)
            action.triggered.connect(
                lambda _, signal=action_signal: signal.emit(selected_item)
            )
            menu.addAction(action)
        menu.popup(self.files_tv.viewport().mapToGlobal(pos))

    def select_file_or_directory(self, index: QModelIndex):
        self.busy.emit()
        self.communication.progress_bar("Loading files...", clear_msg_bar=True)
        # Only allow selection of the first column (filename)
        if index.column() != 0:
            return
        file_item = self.files_model.itemFromIndex(index)
        self.selected_item = file_item.data(Qt.ItemDataRole.UserRole)
        self.update()
        self.ready.emit()

    def fetch_and_populate(self, project: dict, path: str = None):
        self.files = get_tenant_project_files(
            self.communication,
            project["id"],
            {"path": path} if path else None,
        )
        self.files_model.clear()
        header = ["Filename", "Data type", "Size", "Last modified"]
        self.files_model.setHorizontalHeaderLabels(header)

        directories = [file for file in self.files if file["type"] == "directory"]
        files = [file for file in self.files if file["type"] == "file"]

        # Add directories first
        for directory in directories:
            dir_name = os.path.basename(directory["id"].rstrip("/"))
            name_item = QStandardItem(dir_icon, dir_name)
            name_item.setToolTip(dir_name)
            name_item.setData(directory, role=Qt.ItemDataRole.UserRole)
            self.files_model.appendRow([name_item])

        # Add files second
        for file in files:
            file_name = os.path.basename(file["id"].rstrip("/"))
            name_item = QStandardItem(file_icon, file_name)
            name_item.setToolTip(file_name)
            name_item.setData(file, role=Qt.ItemDataRole.UserRole)
            data_type = file["data_type"]
            data_type_item = QStandardItem(
                SUPPORTED_DATA_TYPES.get(data_type, data_type)
            )
            size_display = (
                display_bytes(file["size"])
                if data_type != "threedi_schematisation"
                else "N/A"
            )
            size_item = NumericItem(size_display)
            size_item.setData(
                file["size"] if data_type != "threedi_schematisation" else -1,
                role=Qt.ItemDataRole.UserRole,
            )
            last_modified = convert_to_local_time(file["last_modified"])
            last_modified_timestamp = convert_to_timestamp(file["last_modified"])
            last_modified_item = NumericItem(last_modified)
            last_modified_item.setData(
                last_modified_timestamp, role=Qt.ItemDataRole.UserRole
            )
            # Add items to the model
            self.files_model.appendRow(
                [name_item, data_type_item, size_item, last_modified_item]
            )

        for i in range(len(header)):
            self.files_tv.resizeColumnToContents(i)
        self.files_tv.setColumnWidth(0, 300)


class ProjectsBrowser(QWidget):
    projects_refreshed = pyqtSignal()
    project_selected = pyqtSignal(dict)
    busy = pyqtSignal()
    ready = pyqtSignal()

    def __init__(self, communication, parent=None):
        super().__init__(parent)
        self.communication = communication
        self.projects = []
        self.filtered_projects = []
        self.current_page = 1
        self.items_per_page = 25
        self.project = None
        self.setup_ui()
        self.fetch_projects()
        self.populate_projects()

    def set_project_from_id(self, project_id: str):
        for project in self.projects:
            if project["id"] == project_id:
                self.project = project
                return

    def setup_ui(self):
        # Create search box
        self.projects_search = QLineEdit()
        self.projects_search.setPlaceholderText("🔍 Search for project by name")
        self.projects_search.textChanged.connect(self.filter_projects)
        # Create refresh button
        overview_refresh_btn = QToolButton()
        overview_refresh_btn.setToolTip("Refresh")
        overview_refresh_btn.clicked.connect(self.refresh)
        overview_refresh_btn.setIcon(refresh_icon)
        # Create tree view with project files and model
        self.projects_model = QStandardItemModel()
        self.projects_tv = QTreeView()
        self.projects_tv.setModel(self.projects_model)
        self.projects_tv.setSortingEnabled(True)
        self.projects_tv.header().setSortIndicatorShown(True)
        self.projects_tv.header().setSortIndicator(1, Qt.SortOrder.AscendingOrder)
        # self.projects_tv.clicked.connect(self.select_project)
        self.projects_tv.doubleClicked.connect(self.select_project)
        # Create navigation buttons
        self.btn_previous = QPushButton("<")
        self.label_page_number = QLabel("Page 1/1")
        self.btn_next = QPushButton(">")
        self.btn_previous.clicked.connect(self.to_previous_page)
        self.btn_next.clicked.connect(self.to_next_page)
        # Organize widgets in layouts
        top_layout = QHBoxLayout()
        top_layout.addWidget(self.projects_search)
        top_layout.addWidget(overview_refresh_btn)
        pagination_layout = QHBoxLayout()
        pagination_layout.addWidget(self.btn_previous)
        pagination_layout.addWidget(self.label_page_number)
        pagination_layout.addWidget(self.btn_next)
        layout = QVBoxLayout(self)
        layout.addLayout(top_layout)
        layout.addWidget(self.projects_tv)
        layout.addLayout(pagination_layout)
        self.setLayout(layout)

    def fetch_projects(self):
        self.projects = get_tenant_projects(self.communication)

    def refresh(self):
        self.current_page = 1
        self.fetch_projects()
        search_text = self.projects_search.text()
        if search_text:
            self.filter_projects(search_text, clear=True)
            return
        self.populate_projects(clear=True)
        self.projects_tv.header().setSortIndicator(1, Qt.SortOrder.AscendingOrder)
        self.projects_refreshed.emit()

    def filter_projects(self, text: str, clear: bool = False):
        self.current_page = 1
        if text:
            self.filtered_projects = [
                project
                for project in self.projects
                if text.lower() in project["name"].lower()
            ]
        else:
            self.filtered_projects = []
        self.populate_projects(clear=clear)

    def sort_projects(self, column_index: int, order: Qt.SortOrder):
        self.current_page = 1
        key_funcs = [
            lambda project: project["name"].lower(),
            lambda project: -convert_to_timestamp(project["last_activity"]),
        ]
        key_func = key_funcs[column_index]
        self.projects.sort(
            key=key_func, reverse=(order == Qt.SortOrder.DescendingOrder)
        )
        search_text = self.projects_search.text()
        if search_text:
            self.filter_projects(search_text)
            return
        self.populate_projects()

    @staticmethod
    def _process_project_item(project: dict) -> list[QStandardItem, NumericItem]:
        project_name = project["name"]
        name_item = QStandardItem(project_name)
        name_item.setToolTip(project_name)
        name_item.setData(project, role=Qt.ItemDataRole.UserRole)
        last_activity = project["last_activity"]
        last_activity_timestamp = convert_to_timestamp(last_activity)
        last_activity_localtime = convert_to_local_time(last_activity)
        last_activity_relative = convert_to_relative_time(last_activity)
        last_activity_item = NumericItem(last_activity_relative)
        last_activity_item.setData(
            last_activity_timestamp, role=Qt.ItemDataRole.UserRole
        )
        last_activity_item.setToolTip(last_activity_localtime)
        return [name_item, last_activity_item]

    def populate_projects(self, clear: bool = False):
        if clear:
            self.projects_model.clear()
        self.projects_model.removeRows(0, self.projects_model.rowCount())
        header = ["Project Name", "Last activity"]
        self.projects_model.setHorizontalHeaderLabels(header)

        # Paginate projects
        search_text = self.projects_search.text()
        projects = self.filtered_projects if search_text else self.projects
        start_index = (self.current_page - 1) * self.items_per_page
        end_index = start_index + self.items_per_page
        paginated_projects = projects[start_index:end_index]

        # Add paginated projects to the project model
        for project in paginated_projects:
            self.projects_model.appendRow(self._process_project_item(project))
        for i in range(len(header)):
            self.projects_tv.resizeColumnToContents(i)
        self.projects_tv.setColumnWidth(0, 300)
        self.update_pagination(projects)

    def update_pagination(self, projects: list):
        total_items = len(projects)
        total_pages = (
            math.ceil(total_items / self.items_per_page) if total_items > 0 else 1
        )
        self.label_page_number.setText(f"Page {self.current_page}/{total_pages}")
        self.btn_previous.setDisabled(self.current_page == 1)
        self.btn_next.setDisabled(self.current_page == total_pages)

    def change_page(self, increment: int):
        self.current_page += increment
        self.populate_projects()

    def to_previous_page(self):
        self.change_page(-1)

    def to_next_page(self):
        self.change_page(1)

    def select_project(self, index: QModelIndex):
        self.setEnabled(False)
        self.busy.emit()
        self.communication.progress_bar("Loading project...", clear_msg_bar=True)
        try:
            # Only allow selection of the first column (project name)
            if index.column() != 0:
                return
            project_item = self.projects_model.itemFromIndex(index)
            new_project = project_item.data(Qt.ItemDataRole.UserRole)
            self.project = new_project
            self.project_selected.emit(self.project)
        finally:
            self.communication.clear_message_bar()
            self.ready.emit()
            self.setEnabled(True)


class BreadcrumbType(Enum):
    PROJECTS = "projects"
    FOLDER = "folder"
    FILE = "file"
    REVISIONS = "revisions"


BreadcrumbItem = namedtuple("BreadcrumbItem", ["type", "name"])


class BreadCrumbsWidget(QWidget):
    projects_selected = pyqtSignal()
    folder_selected = pyqtSignal(str)
    file_selected = pyqtSignal()

    def __init__(self, communication, parent=None):
        super().__init__(parent)
        self.communication = communication
        self._items: List[BreadcrumbItem] = [
            BreadcrumbItem(BreadcrumbType.PROJECTS, "Projects")
        ]
        self.setup_ui()
        self.update()

    def add_file(self, file_path):
        # files can only be added after a folder
        if self._items[-1].type == BreadcrumbType.FOLDER:
            self._items.append(BreadcrumbItem(BreadcrumbType.FILE, file_path))
        self.update()

    def add_folder(self, folder_name):
        # folders can only be added after projects or a folder
        if self._items[-1].type in [BreadcrumbType.PROJECTS, BreadcrumbType.FOLDER]:
            self._items.append(BreadcrumbItem(BreadcrumbType.FOLDER, folder_name))
        self.update()

    def add_revisions(self):
        # revisions can only be added after a file
        if self._items[-1].type == BreadcrumbType.FILE:
            self._items.append(BreadcrumbItem(BreadcrumbType.REVISIONS, "Revisions"))
        self.update()

    def set_folders(self, paths):
        for item in paths:
            self._items.append(BreadcrumbItem(BreadcrumbType.FOLDER, item))
        self.update()

    def setup_ui(self):
        self.layout = QHBoxLayout(self)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.layout)

    def clear(self):
        for i in reversed(range(self.layout.count())):
            widget = self.layout.itemAt(i).widget()
            if widget:
                self.layout.removeWidget(widget)
                widget.deleteLater()

    def update(self):
        self.clear()
        for i, item in enumerate(self._items):
            label = self.get_button(i, item)
            self.layout.addWidget(label)
            if i != len(self._items) - 1:
                separator = QLabel(">")
                self.layout.addWidget(separator)

    def get_button(self, index: int, item: BreadcrumbItem) -> QLabel:
        label_text = elide_text(self.font(), item.name, 100)
        # Last item cannot be clicked
        if index == len(self._items) - 1:
            label = QLabel(label_text)
        else:
            link = f"<a href='{index}'>{label_text}</a>"
            label = QLabel(link)
            label.setTextFormat(Qt.TextFormat.RichText)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
            label.linkActivated.connect(lambda _, idx=index: self.on_click(idx))
        return label

    def on_click(self, index: int):
        # Truncate items to clicked position
        self._items = self._items[: index + 1]
        if index == 0:  # Projects
            self.projects_selected.emit()
        else:
            self.communication.progress_bar("Loading files...", clear_msg_bar=True)
            clicked_item = self._items[index]
            if clicked_item.type == BreadcrumbType.FILE:
                self.file_selected.emit()
            else:
                # path should be None for project root
                if len(self._items) == 2:
                    path = None
                else:
                    path = "/".join(item.name for item in self._items[2:]) + "/"
                self.folder_selected.emit(path)
            self.communication.clear_message_bar()
        self.update()


class RanaBrowser(QWidget):
    open_wms_selected = pyqtSignal(dict, dict)
    open_in_qgis_selected = pyqtSignal(dict, dict)
    upload_file_selected = pyqtSignal(dict, dict)
    save_vector_styling_selected = pyqtSignal(dict, dict)
    upload_new_file_selected = pyqtSignal(dict, dict)
    download_file_selected = pyqtSignal(dict, dict)
    download_results_selected = pyqtSignal(dict, dict)
    start_simulation_selected = pyqtSignal(dict, dict)
    start_simulation_selected_with_revision = pyqtSignal(dict, dict, int)
    delete_file_selected = pyqtSignal(dict, dict)

    def __init__(self, communication: UICommunication):
        super().__init__()
        self.communication = communication
        self.setup_ui()

    @property
    def project(self):
        return self.projects_browser.project

    @project.setter
    def project(self, project):
        self.projects_browser.project = project

    @property
    def selected_item(self):
        return self.files_browser.selected_item

    def setup_ui(self):
        self.rana_browser = QTabWidget()
        self.rana_processes = QWidget()
        self.rana_files = QStackedWidget()
        self.rana_browser.addTab(self.rana_files, "Files")
        self.rana_browser.addTab(self.rana_processes, "Processes")
        self.rana_browser.setCurrentIndex(0)
        self.rana_browser.setTabEnabled(1, False)
        # Set up breadcrumbs, browser and file view widgets
        self.breadcrumbs = BreadCrumbsWidget(
            communication=self.communication, parent=self
        )
        # Setup top layout with logo and breadcrumbs
        top_layout = QHBoxLayout()

        banner = QSvgWidget(os.path.join(ICONS_DIR, "banner.svg"))
        renderer = banner.renderer()
        original_size = renderer.defaultSize()  # QSize
        width = 150
        height = int(original_size.height() / original_size.width() * width)
        banner.setFixedWidth(width)
        banner.setFixedHeight(height)
        logo_label = banner

        top_layout.addWidget(self.breadcrumbs)
        top_layout.addStretch()
        top_layout.addWidget(logo_label)
        # Add components to the layout
        layout = QVBoxLayout(self)
        layout.addLayout(top_layout)
        layout.addWidget(self.rana_browser)
        self.setLayout(layout)
        # Setup widgets that populate the rana widget
        self.projects_browser = ProjectsBrowser(
            communication=self.communication, parent=self
        )
        self.files_browser = FilesBrowser(communication=self.communication, parent=self)
        self.file_view = FileView(communication=self.communication, parent=self)
        self.revisions_view = RevisionsView(
            communication=self.communication, parent=self
        )
        # Disable/enable widgets
        self.projects_browser.busy.connect(lambda: self.disable)
        self.projects_browser.ready.connect(lambda: self.enable)
        self.revisions_view.busy.connect(lambda: self.disable)
        self.revisions_view.ready.connect(lambda: self.enable)
        self.files_browser.busy.connect(lambda: self.disable)
        self.files_browser.ready.connect(lambda: self.enable)
        # Add browsers and file view to rana widget
        self.rana_files.addWidget(self.projects_browser)
        self.rana_files.addWidget(self.files_browser)
        self.rana_files.addWidget(self.file_view)
        self.rana_files.addWidget(self.revisions_view)
        # On selecting a project in the project view
        # - update selected project in file browser and file_view
        # - set breadcrumbs path
        self.projects_browser.project_selected.connect(
            self.files_browser.update_project
        )
        self.projects_browser.project_selected.connect(self.file_view.update_project)
        # Show file details on selecting file
        self.files_browser.file_selected.connect(
            self.file_view.show_selected_file_details
        )
        # Update breadcrumbs when file browser path changes
        self.projects_browser.project_selected.connect(
            lambda selected_item: self.breadcrumbs.add_folder(selected_item["name"])
        )
        self.files_browser.folder_selected.connect(self.breadcrumbs.add_folder)
        self.files_browser.file_selected.connect(
            lambda selected_item: self.breadcrumbs.add_file(
                selected_item["id"].split("/")[-1]
            )
        )
        self.file_view.show_revisions_clicked.connect(self.breadcrumbs.add_revisions)
        # Connect upload button
        self.files_browser.btn_upload.clicked.connect(
            lambda _,: self.upload_new_file_selected.emit(
                self.project, self.selected_item
            )
        )
        # Connect file browser context menu signals
        context_menu_signals = (
            (self.files_browser.file_deletion_requested, self.delete_file_selected),
            (self.files_browser.open_in_qgis_requested, self.open_in_qgis_selected),
            (self.files_browser.upload_file_requested, self.upload_file_selected),
            (
                self.files_browser.save_vector_styling_requested,
                self.save_vector_styling_selected,
            ),
            (self.files_browser.open_wms_requested, self.open_wms_selected),
            (self.files_browser.download_file_requested, self.download_file_selected),
            (
                self.files_browser.download_results_requested,
                self.download_results_selected,
            ),
        )
        for file_browser_signal, rana_signal in context_menu_signals:
            file_browser_signal.connect(
                lambda file, signal=rana_signal: signal.emit(self.project, file)
            )
        # Connect updating folder from breadcrumb
        self.breadcrumbs.folder_selected.connect(
            lambda path: self.files_browser.fetch_and_populate(self.project, path)
        )
        self.breadcrumbs.file_selected.connect(self.file_view.refresh)
        self.file_view.show_revisions_clicked.connect(
            self.revisions_view.show_revisions_for_file
        )
        self.file_view.btn_start_simulation.clicked.connect(
            lambda _: self.start_simulation_selected.emit(
                self.project, self.selected_item
            )
        )
        # Start simulation for specific revision
        self.revisions_view.new_simulation_clicked.connect(
            lambda revision_id: self.start_simulation_selected_with_revision.emit(
                self.project, self.selected_item, revision_id
            )
        )
        # Ensure correct page is shown - do this last zo all updates are done
        self.projects_browser.projects_refreshed.connect(
            lambda: self.rana_files.setCurrentIndex(0)
        )
        self.projects_browser.project_selected.connect(
            lambda _: self.rana_files.setCurrentIndex(1)
        )
        self.files_browser.folder_selected.connect(
            lambda: self.rana_files.setCurrentIndex(1)
        )
        self.files_browser.file_selected.connect(
            lambda _: self.rana_files.setCurrentIndex(2)
        )
        self.file_view.file_showed.connect(lambda: self.rana_files.setCurrentIndex(2))
        self.file_view.show_revisions_clicked.connect(
            lambda _: self.rana_files.setCurrentIndex(3)
        )
        self.breadcrumbs.projects_selected.connect(
            lambda: self.rana_files.setCurrentIndex(0)
        )
        self.breadcrumbs.folder_selected.connect(
            lambda: self.rana_files.setCurrentIndex(1)
        )
        self.breadcrumbs.file_selected.connect(
            lambda: self.rana_files.setCurrentIndex(2)
        )

    @pyqtSlot()
    def enable(self):
        self.rana_browser.setEnabled(True)

    @pyqtSlot()
    def disable(self):
        self.rana_browser.setEnabled(False)

    @pyqtSlot()
    def refresh(self):
        if hasattr(self.rana_files.currentWidget(), "refresh"):
            self.rana_files.currentWidget().refresh()
        else:
            raise Exception("Attempted refresh on widget without refresh support")

    def start_file_in_qgis(self, project_id: str, online_path: str):
        self.projects_browser.set_project_from_id(project_id)
        if self.project is not None:
            self.communication.log_warn(f"Selecting project {project_id}")
            self.files_browser.selected_item = get_tenant_project_file(
                project_id, {"path": online_path}
            )
        if self.files_browser.selected_item:
            paths = [self.projects_browser.project["name"]] + online_path.split("/")[
                :-1
            ]
            self.breadcrumbs.set_folders(paths)
            # handle item as it was selected in the UI
            self.files_browser.update()
            # open in qgis; note that selected_item is either None or a file
            self.open_in_qgis_selected.emit(
                self.projects_browser.project, self.selected_item
            )
            self.communication.log_info(f"Opening file {str(self.selected_item)}")
        else:
            self.project = None
