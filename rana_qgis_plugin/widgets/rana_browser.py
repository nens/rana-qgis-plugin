import math
import os

from qgis.core import Qgis, QgsMessageLog
from qgis.PyQt import uic
from qgis.PyQt.QtCore import QModelIndex, QSettings, Qt, pyqtSignal, pyqtSlot
from qgis.PyQt.QtGui import QPixmap, QStandardItem, QStandardItemModel
from qgis.PyQt.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

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


class FileView(QWidget):
    def __init__(self, communication, breadcrumbs, parent=None):
        super().__init__(parent)
        self.communication = communication
        self.breadcrumbs = breadcrumbs
        self.project = None
        self.setup_ui()

    def update_project(self, project: dict):
        self.project = project

    def setup_ui(self):
        file_refresh_btn = QToolButton()
        file_refresh_btn.setToolTip("Refresh")
        file_refresh_btn.clicked.connect(self.refresh)
        self.file_table_widget = QTableWidget(1, 2)

        # self.file_table_widget.setHorizontalHeaderVisible(False)
        # self.file_table_widget.setVerticalHeaderVisible(False)
        button_layout = QVBoxLayout()
        self.btn_open = QPushButton("Open in QGIS")
        self.btn_save_vector_style = QPushButton("Save Style to Rana")
        self.btn_save = QPushButton("Save Data to Rana")
        self.btn_wms = QPushButton("Open WMS in QGIS")
        self.btn_download = QPushButton("Download")
        self.btn_download_results = QPushButton("Download Selected Results")
        for btn in [
            self.btn_open,
            self.btn_save_vector_style,
            self.btn_save,
            self.btn_wms,
            self.btn_download,
            self.btn_download_results,
        ]:
            button_layout.addWidget(btn)
        layout = QVBoxLayout(self)
        layout.addWidget(file_refresh_btn)
        layout.addWidget(self.file_table_widget)
        layout.addLayout(button_layout)
        self.setLayout(layout)

    def show_selected_file_details(self, selected_file):
        self.file_table_widget.clearContents()
        # selected_file = self.breadcrumbs.selected_file
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

    def refresh(self):
        selected_file = self.breadcrumbs.selected_file
        assert selected_file
        selected_file = get_tenant_project_file(
            self.project["id"], {"path": selected_file["id"]}
        )
        last_modified_key = (
            f"{self.project['name']}/{selected_file['id']}/last_modified"
        )
        QSettings().setValue(last_modified_key, selected_file["last_modified"])
        self.breadcrumbs.selected_file = selected_file
        self._update_file_UI(append_path=False)


class FilesBrowser(QWidget):
    folder_selected = pyqtSignal()
    file_selected = pyqtSignal(dict)
    busy = pyqtSignal()
    ready = pyqtSignal()

    def __init__(self, communication, breadcrumbs, parent=None):
        super().__init__(parent)
        self.breadcrumbs = breadcrumbs
        self.project = None
        self.communication = communication
        self.selected_file = None
        self.setup_ui()

    def update_project(self, project: dict):
        self.project = project
        self.selected_file = {"id": "", "type": "directory"}
        self.fetch_and_populate(project)

    def setup_ui(self):
        project_refresh_btn = QToolButton()
        project_refresh_btn.setToolTip("Refresh")
        project_refresh_btn.setIcon(refresh_icon)
        project_refresh_btn.clicked.connect(self._update_file_UI)
        self.files_tv = QTreeView()
        self.files_model = QStandardItemModel()
        self.files_tv.setModel(self.files_model)
        self.files_tv.setSortingEnabled(True)
        self.files_tv.header().setSortIndicatorShown(True)
        self.files_tv.doubleClicked.connect(self.select_file_or_directory)
        self.btn_upload = QPushButton("Upload Files to Rana")
        layout = QVBoxLayout(self)
        # todo: move refresh to far right
        layout.addWidget(project_refresh_btn)
        layout.addWidget(self.files_tv)
        layout.addWidget(self.btn_upload)
        self.setLayout(layout)

    def refresh(self):
        self._update_file_UI(append_path=False)

    def _update_file_UI(self, append_path: bool = True):
        file_path = self.selected_file["id"]
        if self.selected_file["type"] == "directory":
            directory_name = os.path.basename(file_path.rstrip("/"))
            if append_path:
                self.breadcrumbs.paths.append(directory_name)
            self.fetch_and_populate(self.project, file_path)
            self.folder_selected.emit()
        else:
            file_name = os.path.basename(file_path.rstrip("/"))
            if append_path:
                self.breadcrumbs.paths.append(file_name)
            self.file_selected.emit(self.selected_file)

        self.breadcrumbs.update()
        self.communication.clear_message_bar()

    def select_file_or_directory(self, index: QModelIndex):
        # self.rana_widget.setEnabled(False)
        self.busy.emit()
        self.communication.progress_bar("Loading files...", clear_msg_bar=True)
        # Only allow selection of the first column (filename)
        if index.column() != 0:
            return
        file_item = self.files_model.itemFromIndex(index)
        self.selected_file = file_item.data(Qt.ItemDataRole.UserRole)
        self._update_file_UI()
        self.ready.emit()

    def fetch_and_populate(self, project: dict, path: str = None):
        project = self.project
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

    def __init__(self, communication, breadcrumbs, parent=None):
        super().__init__(parent)
        self.communication = communication
        self.breadcrumbs = breadcrumbs
        self.selected_file = self.breadcrumbs.selected_file
        self.projects = []
        self.filtered_projects = []
        self.current_page = 1
        self.items_per_page = 25
        self.project = None
        self.setup_ui()
        self.fetch_projects()
        self.populate_projects()

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
        self.projects_tv.clicked.connect(self.select_project)
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
        # TODO: it make zero sense to pass the communication to the network manager!!
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
        self.breadcrumbs.update()
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
        # TODO: add method to add project item
        for project in paginated_projects:
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
            # Add items to the model
            self.projects_model.appendRow([name_item, last_activity_item])
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
        self.communication.progress_bar("Loading project...", clear_msg_bar=True)
        try:
            # Only allow selection of the first column (project name)
            if index.column() != 0:
                return
            project_item = self.projects_model.itemFromIndex(index)
            self.project = project_item.data(Qt.ItemDataRole.UserRole)
            self.breadcrumbs.paths.append(self.project["name"])
            self.breadcrumbs.paths = self.breadcrumbs.paths[:2]
            self.breadcrumbs.update()
            self.selected_file = {"id": "", "type": "directory"}
            self.project_selected.emit(self.project)
        finally:
            self.communication.clear_message_bar()
            self.setEnabled(True)


class BreadCrumbs(QWidget):
    folder_selected = pyqtSignal(str)

    def __init__(self, rana_widget, communication, parent=None):
        super().__init__(parent)
        self.rana_widget = rana_widget
        self.communication = communication
        self.paths = ["Projects"]
        self.selected_file = None
        self.setup_ui()
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
                del widget

    def update(self):
        self.clear()
        # Add the breadcrumbs
        for i, path in enumerate(self.paths):
            label = self.get_button(i, path)
            self.layout.addWidget(label)
            if i != len(self.paths) - 1:
                separator = QLabel(">")
                self.layout.addWidget(separator)

    def get_button(self, index: int, path: str) -> QLabel:
        label_text = elide_text(self.font(), path, 100)
        link = f"<a href='{index}'>{label_text}</a>"
        label = QLabel(label_text if index == len(self.paths) - 1 else link)
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        label.linkActivated.connect(lambda _, idx=index: self.on_click(idx))
        return label

    def on_click(self, index: int):
        self.paths = self.paths[: index + 1]
        if index == 0:
            self.rana_widget.setCurrentIndex(0)
            self.update()
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
                self.update()
                self.folder_selected.emit(path)
            finally:
                self.communication.clear_message_bar()
                self.rana_widget.setEnabled(True)


class RanaBrowser(QWidget):
    open_wms_selected = pyqtSignal(dict, dict)
    open_in_qgis_selected = pyqtSignal(dict, dict)
    upload_file_selected = pyqtSignal(dict, dict)
    save_vector_styling_selected = pyqtSignal(dict, dict)
    upload_new_file_selected = pyqtSignal(dict, dict)
    download_file_selected = pyqtSignal(dict, dict)
    download_results_selected = pyqtSignal(dict, dict)

    def __init__(self, communication: UICommunication):
        super().__init__()
        self.communication = communication
        self.settings = None
        self.paths = []
        self.items_per_page = 25
        self.current_page = 1
        self.paths = ["Projects"]
        self.projects = []
        self.filtered_projects = []
        self.files = []
        self.project = None
        self.selected_file = None

        # Setup UI
        self.setup_ui()

        # Initialize other attributes and fetch data
        self.settings = QSettings()

    def setup_ui(self):
        # Create stacked widget
        self.rana_widget = QStackedWidget()

        # Create main layout for the whole widget
        layout = QVBoxLayout(self)

        # Create top section with breadcrumbs and logo
        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)

        # Create breadcrumbs container and layout - store both as instance variables
        breadcrumbs = BreadCrumbs(
            rana_widget=self.rana_widget,
            communication=self.communication,
        )

        # Setup logo
        logo_label = QLabel("LOGO")
        logo_label.setPixmap(QPixmap(os.path.join(ICONS_DIR, "banner.svg")))

        # Add widgets to top layout
        top_layout.addWidget(breadcrumbs)
        top_layout.addWidget(logo_label)

        # Add both main components to the layout
        layout.addWidget(top_widget)
        layout.addWidget(self.rana_widget)
        self.setLayout(layout)

        # Setup widgets that populate the rana widget
        projects_browser = ProjectsBrowser(
            communication=self.communication, breadcrumbs=breadcrumbs, parent=self
        )
        files_browser = FilesBrowser(
            communication=self.communication, breadcrumbs=breadcrumbs, parent=self
        )
        file_view = FileView(
            communication=self.communication, breadcrumbs=breadcrumbs, parent=self
        )
        # Link properties to this class for easy access
        self.project = projects_browser.project
        self.selected_file = breadcrumbs.selected_file

        # Update project in file browser and vies
        projects_browser.project_selected.connect(files_browser.update_project)
        projects_browser.project_selected.connect(file_view.update_project)
        # conect showing file
        files_browser.file_selected.connect(file_view.show_selected_file_details)
        files_browser.busy.connect(lambda: self.enable)
        files_browser.ready.connect(lambda: self.disable)
        # connect updating folder from breadcrumb
        breadcrumbs.folder_selected.connect(
            lambda path: files_browser.fetch_and_populate(self.project, path)
        )
        # connect upload button
        files_browser.btn_upload.clicked.connect(
            lambda _,: self.upload_new_file_selected.emit(
                self.project, self.selected_file
            )
        )
        # connect file view buttons
        file_view.btn_open.clicked.connect(
            lambda _,: self.open_in_qgis_selected.emit(self.project, self.selected_file)
        )
        file_view.btn_save.clicked.connect(
            lambda _,: self.upload_file_selected.emit(self.project, self.selected_file)
        )
        file_view.btn_save_vector_style.clicked.connect(
            lambda _,: self.save_vector_styling_selected.emit(
                self.project, self.selected_file
            )
        )
        file_view.btn_wms.clicked.connect(
            lambda _,: self.open_wms_selected.emit(self.project, self.selected_file)
        )
        file_view.btn_download.clicked.connect(
            lambda _,: self.download_file_selected.emit(
                self.project, self.selected_file
            )
        )
        file_view.btn_download_results.clicked.connect(
            lambda _,: self.download_results_selected.emit(
                self.project, self.selected_file
            )
        )
        # connect signals to select the correct page of the widget
        projects_browser.projects_refreshed.connect(
            lambda: self.rana_widget.setCurrentIndex(0)
        )
        projects_browser.project_selected.connect(
            lambda _: self.rana_widget.setCurrentIndex(1)
        )
        files_browser.folder_selected.connect(
            lambda: self.rana_widget.setCurrentIndex(1)
        )
        files_browser.file_selected.connect(lambda _: self.rana_widget.setCurrentIndex(2))
        breadcrumbs.folder_selected.connect(lambda: self.rana_widget.setCurrentIndex(1))

        # stack widgets that show the different 'pages
        self.rana_widget.addWidget(projects_browser)
        self.rana_widget.addWidget(files_browser)
        self.rana_widget.addWidget(file_view)

    @pyqtSlot()
    def enable(self):
        self.rana_widget.setEnabled(True)

    @pyqtSlot()
    def disable(self):
        self.rana_widget.setEnabled(False)

    @pyqtSlot()
    def refresh(self):
        if hasattr(self.rana_widget.currentWidget(), "refresh"):
            self.rana_widget.currentWidget().refresh()
        else:
            raise Exception("Attempted refresh on widget without refresh support")

    def start_file_in_qgis(self, project_id: str, online_path: str):
        for project in self.projects:
            if project["id"] == project_id:
                self.communication.log_warn(f"Selecting project {project_id}")
                self.project = project
        self.selected_file = get_tenant_project_file(project_id, {"path": online_path})
        self.paths = ["Projects", self.project["name"]] + online_path.split("/")[:-1]
        if self.selected_file:
            self.communication.log_info(f"Opening file {str(self.selected_file)}")
            self.open_in_qgis_selected.emit(self.project, self.selected_file)
            self._update_file_UI()
        else:
            self.project = None
            self.paths = ["Projects"]
