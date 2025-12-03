import math
import os
from pathlib import Path

from qgis.PyQt.QtCore import QModelIndex, QSettings, Qt, pyqtSignal, pyqtSlot
from qgis.PyQt.QtGui import QAction, QPixmap, QStandardItem, QStandardItemModel
from qgis.PyQt.QtSvg import QSvgWidget
from qgis.PyQt.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
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
    file_showed = pyqtSignal()

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
        button_layout = QVBoxLayout()
        self.btn_start_simulation = QPushButton("Start Simulation")
        button_layout.addWidget(self.btn_start_simulation)
        layout = QVBoxLayout(self)
        layout.addWidget(file_refresh_btn)
        layout.addWidget(self.file_table_widget)
        layout.addLayout(button_layout)
        self.setLayout(layout)

    def show_selected_file_details(self, selected_file):
        self.selected_file = selected_file
        self.file_table_widget.clearContents()
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
            self.btn_start_simulation.show()
        else:
            self.btn_start_simulation.hide()
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
    folder_selected = pyqtSignal()
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
        # todo: move refresh to far right
        layout.addWidget(project_refresh_btn)
        layout.addWidget(self.files_tv)
        layout.addWidget(self.btn_upload)
        self.setLayout(layout)

    def refresh(self):
        self.update(append_path=False)

    def update(self, append_path: bool = True):
        selected_path = self.selected_item["id"]
        selected_name = Path(selected_path.rstrip("/")).name
        if self.selected_item["type"] == "directory":
            self.fetch_and_populate(self.project, selected_path)
            self.folder_selected.emit()
        else:
            self.file_selected.emit(self.selected_item)
        if append_path:
            self.path_changed.emit(selected_name)
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
        self.projects = get_tenant_projects(self.communication)
        from qgis.core import Qgis, QgsMessageLog

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


class BreadCrumbsWidget(QWidget):
    folder_selected = pyqtSignal(str)

    def __init__(self, rana_widget, communication, parent=None):
        super().__init__(parent)
        self.rana_widget = rana_widget
        self.communication = communication
        self.paths = ["Projects"]
        self.selected_file = None
        self.setup_ui()
        self.update()

    def set_selected_file_from_path(self, project_id: str, online_path: str):
        self.update_selected_file(
            get_tenant_project_file(project_id, {"path": online_path})
        )

    def update_selected_file(self, file: dict):
        self.selected_file = file
        self.update()

    def add_path(self, path: str, update: bool = True):
        self.paths.append(path)
        if update:
            self.update()

    def set_paths(self, paths: list[str], update: bool = True):
        self.paths = paths
        if update:
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
    start_simulation_selected = pyqtSignal(dict, dict)
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
            rana_widget=self.rana_files, communication=self.communication, parent=self
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
        # Add browsers and file view to rana widget
        self.rana_files.addWidget(self.projects_browser)
        self.rana_files.addWidget(self.files_browser)
        self.rana_files.addWidget(self.file_view)
        # Disable/enable widgets
        self.projects_browser.busy.connect(lambda: self.disable)
        self.projects_browser.ready.connect(lambda: self.enable)
        self.files_browser.busy.connect(lambda: self.disable)
        self.files_browser.ready.connect(lambda: self.enable)
        # On selecting a project in the project view
        # - update selected project in file browser and file_view
        # - set breadcrumbs path
        self.projects_browser.project_selected.connect(
            self.files_browser.update_project
        )
        self.projects_browser.project_selected.connect(self.file_view.update_project)
        self.projects_browser.project_selected.connect(
            lambda project: self.breadcrumbs.set_paths(["Projects", project["name"]])
        )
        # Show file details on selecting file
        self.files_browser.file_selected.connect(
            self.file_view.show_selected_file_details
        )
        # Update breadcrumbs when file browser path changes
        self.files_browser.path_changed.connect(self.breadcrumbs.add_path)
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
        # Connect start simulation button
        self.file_view.btn_start_simulation.clicked.connect(
            lambda _,: self.start_simulation_selected.emit(
                self.project, self.selected_item
            )
        )
        # Ensure correct page is shown
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
        self.breadcrumbs.folder_selected.connect(
            lambda: self.rana_files.setCurrentIndex(1)
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
            paths = [
                "Projects",
                self.projects_browser.project["name"],
            ] + online_path.split("/")[:-1]
            self.breadcrumbs.set_paths(paths)
            # handle item as it was selected in the UI
            self.files_browser.update()
            # open in qgis; note that selected_item is either None or a file
            self.communication.log_info(f"Opening file {str(self.selected_item)}")
            self.open_in_qgis_selected.emit(
                self.projects_browser.project, self.selected_item
            )
        else:
            self.project = None
            self.breadcrumbs.set_paths(["Projects"], update=False)
