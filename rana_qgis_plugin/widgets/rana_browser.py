import math
import os

from qgis.PyQt import uic
from qgis.PyQt.QtCore import QModelIndex, QSettings, Qt, pyqtSignal, pyqtSlot
from qgis.PyQt.QtGui import QPixmap, QStandardItem, QStandardItemModel
from qgis.PyQt.QtWidgets import QLabel, QTableWidgetItem

from rana_qgis_plugin.communication import UICommunication
from rana_qgis_plugin.constant import SUPPORTED_DATA_TYPES
from rana_qgis_plugin.icons import ICONS_DIR, dir_icon, file_icon, refresh_icon
from rana_qgis_plugin.utils import (
    NumericItem,
    convert_to_local_time,
    convert_to_relative_time,
    convert_to_timestamp,
    display_bytes,
    elide_text,
)
from rana_qgis_plugin.utils_api import (
    get_tenant_file_descriptor,
    get_tenant_project_file,
    get_tenant_project_files,
    get_tenant_projects,
    get_threedi_schematisation,
)

base_dir = os.path.dirname(__file__)
uicls, basecls = uic.loadUiType(os.path.join(base_dir, "ui", "rana.ui"))


class RanaBrowser(uicls, basecls):
    open_wms_selected = pyqtSignal(dict, dict)
    open_in_qgis_selected = pyqtSignal(dict, dict)
    upload_file_selected = pyqtSignal(dict, dict)
    save_vector_styling_selected = pyqtSignal(dict, dict)
    upload_new_file_selected = pyqtSignal(dict, dict)
    download_file_selected = pyqtSignal(dict, dict)
    download_results_selected = pyqtSignal(dict, dict)

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

        banner = QPixmap(os.path.join(ICONS_DIR, "banner.svg"))
        # banner = banner.scaledToHeight(20)
        self.logo_label.setPixmap(banner)

        # Projects widget
        self.projects = []
        self.filtered_projects = []
        self.project = None
        self.projects_model = QStandardItemModel()
        self.projects_tv.setModel(self.projects_model)
        self.projects_tv.setSortingEnabled(True)
        self.projects_tv.header().setSortIndicatorShown(True)
        self.projects_tv.header().sortIndicatorChanged.connect(self.sort_projects)
        self.projects_tv.clicked.connect(self.select_project)
        self.projects_search.textChanged.connect(self.filter_projects)
        self.overview_refresh_btn.setIcon(refresh_icon)
        self.overview_refresh_btn.clicked.connect(self.refresh)
        self.project_refresh_btn.setIcon(refresh_icon)
        self.project_refresh_btn.clicked.connect(self.refresh)
        self.file_refresh_btn.setIcon(refresh_icon)
        self.file_refresh_btn.clicked.connect(self.refresh)
        self.fetch_projects()
        self.populate_projects()
        self.projects_tv.header().setSortIndicator(1, Qt.AscendingOrder)

        # Files widget
        self.files = []
        self.files_model = QStandardItemModel()
        self.files_tv.setModel(self.files_model)
        self.files_tv.setSortingEnabled(True)
        self.files_tv.header().setSortIndicatorShown(True)
        self.files_tv.doubleClicked.connect(self.select_file_or_directory)

        # File details widget
        self.selected_file = None
        self.btn_open.clicked.connect(
            lambda _,: self.open_in_qgis_selected.emit(self.project, self.selected_file)
        )
        self.btn_save.clicked.connect(
            lambda _,: self.upload_file_selected.emit(self.project, self.selected_file)
        )
        self.btn_save_vector_style.clicked.connect(
            lambda _,: self.save_vector_styling_selected.emit(
                self.project, self.selected_file
            )
        )
        self.btn_upload.clicked.connect(
            lambda _,: self.upload_new_file_selected.emit(
                self.project, self.selected_file
            )
        )
        self.btn_wms.clicked.connect(
            lambda _,: self.open_wms_selected.emit(self.project, self.selected_file)
        )
        self.btn_download.clicked.connect(
            lambda _,: self.download_file_selected.emit(
                self.project, self.selected_file
            )
        )
        self.btn_download_results.clicked.connect(
            lambda _,: self.download_results_selected.emit(
                self.project, self.selected_file
            )
        )

    def show_files_widget(self):
        self.rana_widget.setCurrentIndex(1)
        self.update_breadcrumbs()

    def update_breadcrumbs(self):
        # Clear existing breadcrumbs
        for i in reversed(range(self.breadcrumbs_layout.count())):
            widget = self.breadcrumbs_layout.itemAt(i).widget()
            if widget:
                self.breadcrumbs_layout.removeWidget(widget)
                del widget

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
            self.selected_file = None
        else:
            self.rana_widget.setEnabled(False)
            self.communication.progress_bar("Loading files...", clear_msg_bar=True)
            try:
                only_directory_paths = self.paths[
                    2:
                ]  # Skip the first two paths: Projects and project_name
                path = "/".join(only_directory_paths) + (
                    "/" if only_directory_paths else ""
                )
                self.selected_file = {"id": path, "type": "directory"}
                self.fetch_and_populate_files(path)
                self.show_files_widget()
            finally:
                self.communication.clear_message_bar()
                self.rana_widget.setEnabled(True)

    def update_pagination(self, projects: list):
        total_items = len(projects)
        total_pages = (
            math.ceil(total_items / self.items_per_page) if total_items > 0 else 1
        )
        self.label_page_number.setText(f"Page {self.current_page}/{total_pages}")
        self.btn_previous.setDisabled(self.current_page == 1)
        self.btn_next.setDisabled(self.current_page == total_pages)

    def to_previous_page(self):
        self.current_page -= 1
        self.populate_projects()

    def to_next_page(self):
        self.current_page += 1
        self.populate_projects()

    def fetch_projects(self):
        self.projects = get_tenant_projects(self.communication)

    def refresh_projects(self):
        self.current_page = 1
        self.fetch_projects()
        search_text = self.projects_search.text()
        if search_text:
            self.filter_projects(search_text, clear=True)
            return
        self.populate_projects(clear=True)
        self.projects_tv.header().setSortIndicator(1, Qt.AscendingOrder)
        self.paths = ["Projects"]
        self.update_breadcrumbs()
        self.rana_widget.setCurrentIndex(0)

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
            project_name = project["name"]
            name_item = QStandardItem(project_name)
            name_item.setToolTip(project_name)
            name_item.setData(project, role=Qt.UserRole)
            last_activity = project["last_activity"]
            last_activity_timestamp = convert_to_timestamp(last_activity)
            last_activity_localtime = convert_to_local_time(last_activity)
            last_activity_relative = convert_to_relative_time(last_activity)
            last_activity_item = NumericItem(last_activity_relative)
            last_activity_item.setData(last_activity_timestamp, role=Qt.UserRole)
            last_activity_item.setToolTip(last_activity_localtime)
            # Add items to the model
            self.projects_model.appendRow([name_item, last_activity_item])
        for i in range(len(header)):
            self.projects_tv.resizeColumnToContents(i)
        self.projects_tv.setColumnWidth(0, 300)
        self.update_pagination(projects)

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
        self.projects.sort(key=key_func, reverse=(order == Qt.DescendingOrder))
        search_text = self.projects_search.text()
        if search_text:
            self.filter_projects(search_text)
            return
        self.populate_projects()

    @pyqtSlot()
    def enable(self):
        self.rana_widget.setEnabled(True)
        self.refresh()

    @pyqtSlot()
    def disable(self):
        self.rana_widget.setEnabled(False)

    def select_project(self, index: QModelIndex):
        self.rana_widget.setEnabled(False)
        self.communication.progress_bar("Loading project...", clear_msg_bar=True)
        try:
            # Only allow selection of the first column (project name)
            if index.column() != 0:
                return
            project_item = self.projects_model.itemFromIndex(index)
            self.project = project_item.data(Qt.UserRole)
            self.selected_file = {"id": "", "type": "directory"}
            self.paths.append(self.project["name"])
            self.paths = self.paths[:2]
            self.fetch_and_populate_files()
            self.show_files_widget()
        finally:
            self.communication.clear_message_bar()
            self.rana_widget.setEnabled(True)

    def fetch_and_populate_files(self, path: str = None):
        self.files = get_tenant_project_files(
            self.communication,
            self.project["id"],
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
            name_item.setData(directory, role=Qt.UserRole)
            self.files_model.appendRow([name_item])

        # Add files second
        for file in files:
            file_name = os.path.basename(file["id"].rstrip("/"))
            name_item = QStandardItem(file_icon, file_name)
            name_item.setToolTip(file_name)
            name_item.setData(file, role=Qt.UserRole)
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
                role=Qt.UserRole,
            )
            last_modified = convert_to_local_time(file["last_modified"])
            last_modified_timestamp = convert_to_timestamp(file["last_modified"])
            last_modified_item = NumericItem(last_modified)
            last_modified_item.setData(last_modified_timestamp, role=Qt.UserRole)
            # Add items to the model
            self.files_model.appendRow(
                [name_item, data_type_item, size_item, last_modified_item]
            )

        for i in range(len(header)):
            self.files_tv.resizeColumnToContents(i)
        self.files_tv.setColumnWidth(0, 300)

    def select_file_or_directory(self, index: QModelIndex):
        self.rana_widget.setEnabled(False)
        self.communication.progress_bar("Loading files...", clear_msg_bar=True)
        # Only allow selection of the first column (filename)
        if index.column() != 0:
            return
        file_item = self.files_model.itemFromIndex(index)
        self.selected_file = file_item.data(Qt.UserRole)
        self._update_file_UI()

    def _update_file_UI(self, append_path: bool = True):
        file_path = self.selected_file["id"]
        if self.selected_file["type"] == "directory":
            directory_name = os.path.basename(file_path.rstrip("/"))
            if append_path:
                self.paths.append(directory_name)
            self.fetch_and_populate_files(file_path)
            self.rana_widget.setCurrentIndex(1)
        else:
            file_name = os.path.basename(file_path.rstrip("/"))
            if append_path:
                self.paths.append(file_name)
            self.show_selected_file_details()
            self.rana_widget.setCurrentIndex(2)

        self.update_breadcrumbs()
        self.communication.clear_message_bar()
        self.rana_widget.setEnabled(True)

    def show_selected_file_details(self):
        self.file_table_widget.clearContents()
        filename = os.path.basename(self.selected_file["id"].rstrip("/"))
        username = (
            self.selected_file["user"]["given_name"]
            + " "
            + self.selected_file["user"]["family_name"]
        )
        data_type = self.selected_file["data_type"]
        meta = None
        descriptor = get_tenant_file_descriptor(self.selected_file["descriptor_id"])
        meta = descriptor["meta"] if descriptor else None
        description = descriptor["description"] if descriptor else None

        last_modified = convert_to_local_time(self.selected_file["last_modified"])
        size = (
            display_bytes(self.selected_file["size"])
            if data_type != "threedi_schematisation"
            else "N/A"
        )
        file_details = [
            ("Name", filename),
            ("Size", size),
            ("File type", self.selected_file["media_type"]),
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
                self.communication, self.selected_file["descriptor_id"]
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
                file_details.extend(schematisation_details)
            else:
                self.communication.show_error("Failed to download 3Di schematisation.")
        self.file_table_widget.setRowCount(len(file_details))
        self.file_table_widget.horizontalHeader().setStretchLastSection(True)
        for i, (label, value) in enumerate(file_details):
            label_item = QTableWidgetItem(label)
            label_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            value_item = QTableWidgetItem(str(value))
            value_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.file_table_widget.setItem(i, 0, label_item)
            self.file_table_widget.setItem(i, 1, value_item)
        self.file_table_widget.resizeColumnsToContents()

        # Show/hide the buttons based on the file data type
        if data_type == "threedi_schematisation":
            self.btn_open.show()
            self.btn_save.hide()
            self.btn_save_vector_style.hide()
            self.btn_wms.hide()
            self.btn_download.hide()
            self.btn_download_results.hide()
        elif data_type == "scenario":
            self.btn_open.hide()
            self.btn_save.hide()
            self.btn_save_vector_style.hide()
            if meta["simulation"]["software"]["id"] == "3Di":
                self.btn_wms.show()
                self.btn_download.show()
                self.btn_download_results.show()
            else:
                self.btn_wms.hide()
                self.btn_download.hide()
                self.btn_download_results.hide()
        elif data_type in SUPPORTED_DATA_TYPES.keys():
            self.btn_open.show()
            self.btn_save.show()
            self.btn_save_vector_style.hide()
            if data_type == "vector":
                self.btn_save_vector_style.show()
            self.btn_wms.hide()
            self.btn_download.hide()
            self.btn_download_results.hide()
        else:
            self.btn_open.hide()
            self.btn_save.hide()
            self.btn_wms.hide()
            self.btn_save_vector_style.hide()
            self.btn_download.hide()
            self.btn_download_results.hide()

    def refresh_file_data(self):
        assert self.selected_file
        self.selected_file = get_tenant_project_file(
            self.project["id"], {"path": self.selected_file["id"]}
        )
        last_modified_key = (
            f"{self.project['name']}/{self.selected_file['id']}/last_modified"
        )
        QSettings().setValue(last_modified_key, self.selected_file["last_modified"])
        self._update_file_UI(append_path=False)

    def refresh(self):
        current_index = self.rana_widget.currentIndex()
        if current_index == 0:
            self.refresh_projects()
        elif current_index == 1:
            self._update_file_UI(append_path=False)
        elif current_index == 2:
            self.refresh_file_data()
        else:
            raise Exception("cannot refresh; rana_widget index must be 0, 1, or 2")
