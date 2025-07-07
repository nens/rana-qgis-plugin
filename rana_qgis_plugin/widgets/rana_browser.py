import math
import os
from functools import partial
from pathlib import Path

from qgis.core import QgsDataSourceUri, QgsProject, QgsRasterLayer, QgsSettings
from qgis.PyQt import uic
from qgis.PyQt.QtCore import QModelIndex, QSettings, Qt, QThread
from qgis.PyQt.QtGui import QStandardItem, QStandardItemModel
from qgis.PyQt.QtWidgets import QDialog, QFileDialog, QLabel, QTableWidgetItem
from threedi_mi_utils import bypass_max_path_limit

from rana_qgis_plugin.auth import get_authcfg_id
from rana_qgis_plugin.communication import UICommunication
from rana_qgis_plugin.constant import RANA_SETTINGS_ENTRY
from rana_qgis_plugin.icons import dir_icon, file_icon, refresh_icon
from rana_qgis_plugin.utils import (
    NumericItem,
    add_layer_to_qgis,
    convert_to_local_time,
    convert_to_relative_time,
    convert_to_timestamp,
    display_bytes,
    elide_text,
    get_threedi_schematisation_simulation_results_folder,
)
from rana_qgis_plugin.utils_api import (
    get_tenant_file_descriptor,
    get_tenant_file_descriptor_view,
    get_tenant_project_file,
    get_tenant_project_files,
    get_tenant_projects,
    get_threedi_schematisation,
    map_result_to_file_name,
)
from rana_qgis_plugin.utils_qgis import get_threedi_results_analysis_tool_instance
from rana_qgis_plugin.widgets.result_browser import ResultBrowser
from rana_qgis_plugin.workers import (
    ExistingFileUploadWorker,
    FileDownloadWorker,
    FileUploadWorker,
    LizardResultDownloadWorker,
    VectorStyleWorker,
)

base_dir = os.path.dirname(__file__)
uicls, basecls = uic.loadUiType(os.path.join(base_dir, "ui", "rana.ui"))


class RanaBrowser(uicls, basecls):
    SUPPORTED_DATA_TYPES = {
        "vector": "vector",
        "raster": "raster",
        "threedi_schematisation": "3Di schematisation",
    }

    def __init__(self, communication: UICommunication, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.communication = communication
        self.settings = QSettings()
        self.paths = ["Projects"]
        self.file_download_worker: QThread = None
        self.file_upload_worker: QThread = None
        self.vector_style_worker: QThread = None
        self.new_file_upload_worker: QThread = None

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
        self.schematisation = None
        self.btn_open.clicked.connect(self.open_file_in_qgis)
        self.btn_save.clicked.connect(self.upload_file_to_rana)
        self.btn_save_vector_style.clicked.connect(self.save_vector_styling_files)
        self.btn_upload.clicked.connect(self.upload_new_file_to_rana)
        self.btn_wms.clicked.connect(self.open_wms)
        self.btn_download.clicked.connect(self.download_file)
        self.btn_download_results.clicked.connect(self.download_results)

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
                self.SUPPORTED_DATA_TYPES.get(data_type, data_type)
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
        if self.selected_file["descriptor"]:
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
            ("Data type", self.SUPPORTED_DATA_TYPES.get(data_type, data_type)),
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
            self.schematisation = get_threedi_schematisation(
                self.communication, self.selected_file["descriptor_id"]
            )
            if self.schematisation:
                schematisation = self.schematisation["schematisation"]
                revision = self.schematisation["latest_revision"]
                schematisation_details = [
                    ("Schematisation ID", schematisation["id"]),
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
        elif data_type in self.SUPPORTED_DATA_TYPES.keys():
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

    def open_file_in_qgis(self):
        """Start the worker to download and open files in QGIS"""
        file = self.selected_file
        if file and file["descriptor"] and file["descriptor"]["data_type"]:
            data_type = file["descriptor"]["data_type"]
            if data_type not in self.SUPPORTED_DATA_TYPES:
                self.communication.show_warn(f"Unsupported data type: {data_type}")
                return
            self.initialize_file_download_worker()
            self.file_download_worker.start()
        else:
            self.communication.show_warn(f"Unsupported data type: {file['media_type']}")

    def initialize_file_download_worker(self):
        self.communication.bar_info("Start downloading file...")
        self.rana_widget.setEnabled(False)
        self.file_download_worker = FileDownloadWorker(
            self.project,
            self.selected_file,
        )
        self.file_download_worker.finished.connect(self.on_file_download_finished)
        self.file_download_worker.failed.connect(self.on_file_download_failed)
        self.file_download_worker.progress.connect(self.on_file_download_progress)

    def on_file_download_finished(self, local_file_path: str):
        self.rana_widget.setEnabled(True)
        self.communication.clear_message_bar()
        self.communication.bar_info(f"File(s) downloaded to: {local_file_path}")
        sender = self.sender()
        assert isinstance(sender, QThread)
        sender.wait()

        if self.selected_file["data_type"] == "scenario":
            # if zip file, do nothing, else try to load in results analysis
            if local_file_path.endswith(".zip"):
                pass
            elif os.path.isdir(local_file_path):
                ra_tool = get_threedi_results_analysis_tool_instance()
                # Check whether result and gridadmin exist in the target folder
                result_path = os.path.join(local_file_path, "results_3di.nc")
                admin_path = os.path.join(local_file_path, "gridadmin.h5")
                if os.path.exists(result_path) and os.path.exists(admin_path):
                    if hasattr(ra_tool, "load_result"):
                        if self.communication.ask(
                            self,
                            "Rana",
                            "Do you want to add the results of this simulation to the current project so you can analyse them with 3Di Results Analysis?",
                        ):
                            ra_tool.load_result(result_path, admin_path)
        else:
            add_layer_to_qgis(
                self.communication,
                local_file_path,
                self.project["name"],
                self.selected_file,
                self.schematisation,
            )

    def on_file_download_failed(self, error: str):
        self.rana_widget.setEnabled(True)
        self.communication.clear_message_bar()
        self.communication.show_error(error)

    def on_file_download_progress(self, progress: int, file_name: str = ""):
        self.communication.progress_bar(
            f"Downloading file {file_name}...", 0, 100, progress, clear_msg_bar=True
        )

    def upload_file_to_rana(self):
        """Start the worker for uploading files"""
        self.initialize_file_upload_worker()
        self.file_upload_worker.start()

    def download_results(self):
        if not QgsSettings().contains("threedi/working_dir"):
            self.communication.show_warn(
                "3Di working directory not yet set, please configure this in 3Di Models & Simulations plugin."
            )

        descriptor = get_tenant_file_descriptor(self.selected_file["descriptor_id"])
        schematisation_name = descriptor["meta"]["schematisation"]["name"]
        schematisation_id = descriptor["meta"]["schematisation"]["id"]
        schematisation_version = descriptor["meta"]["schematisation"]["version"]
        assert descriptor["data_type"] == "scenario"

        # Determine local target folder for simulatuon
        target_folder = get_threedi_schematisation_simulation_results_folder(
            QgsSettings().value("threedi/working_dir"),
            schematisation_id,
            schematisation_name,
            schematisation_version,
            descriptor["meta"]["simulation"]["name"],
        )
        os.makedirs(target_folder, exist_ok=True)

        for link in descriptor["links"]:
            if link["rel"] == "lizard-scenario-results":
                results = get_tenant_file_descriptor_view(
                    self.selected_file["descriptor_id"], "lizard-scenario-results"
                )
                result_browser = ResultBrowser(self, results)
                if result_browser.exec() == QDialog.Accepted:
                    result_ids = result_browser.get_selected_results_id()
                    if len(result_ids) == 0:
                        return
                    filtered_result_ids = []
                    for result_id in result_ids:
                        result = [r for r in results if r["id"] == result_id][0]
                        file_name = map_result_to_file_name(result)
                        target_file = bypass_max_path_limit(
                            os.path.join(target_folder, file_name)
                        )
                        # Check whether the files already exist locally
                        if os.path.exists(target_file):
                            file_overwrite = self.communication.custom_ask(
                                self,
                                "File exists",
                                f"Scenario file ({file_name}) has already been downloaded before. Do you want to download again and overwrite existing data?",
                                "Cancel",
                                "Download again",
                                "Continue",
                            )
                            if file_overwrite == "Download again":
                                filtered_result_ids.append(result_id)
                            elif file_overwrite == "Cancel":
                                return
                        else:
                            filtered_result_ids.append(result_id)

                    self.lizard_result_download_worker = LizardResultDownloadWorker(
                        self.project,
                        self.selected_file,
                        filtered_result_ids,
                        target_folder,
                    )

                    self.lizard_result_download_worker.finished.connect(
                        self.on_file_download_finished
                    )
                    self.lizard_result_download_worker.failed.connect(
                        self.on_file_download_failed
                    )
                    self.lizard_result_download_worker.progress.connect(
                        self.on_file_download_progress
                    )
                    self.lizard_result_download_worker.start()

    def open_wms(self):
        descriptor = get_tenant_file_descriptor(self.selected_file["descriptor_id"])
        for link in descriptor["links"]:
            if link["rel"] == "wms":
                for layer in descriptor["meta"]["layers"]:
                    quri = QgsDataSourceUri()
                    quri.setParam("layers", layer["code"])
                    quri.setParam("styles", "")
                    quri.setParam("format", "image/png")
                    quri.setParam("url", link["href"])
                    # the wms provider will take care to expand authcfg URI parameter with credential
                    # just before setting the HTTP connection.
                    quri.setAuthConfigId(get_authcfg_id())
                    rlayer = QgsRasterLayer(
                        bytes(quri.encodedUri()).decode(),
                        f"{layer['name']} ({layer['label']})",
                        "wms",
                    )
                    QgsProject.instance().addMapLayer(rlayer)
                return

        self.communication.bar_error("No WMS layer for this file.")

    def download_file(self):
        assert self.selected_file["data_type"] == "scenario"

        self.initialize_file_download_worker()
        self.file_download_worker.start()

    def upload_new_file_to_rana(self):
        """Upload a local (new) file to Rana"""
        last_saved_dir = QSettings().value(
            f"{RANA_SETTINGS_ENTRY}/last_upload_folder", ""
        )
        local_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open file",
            last_saved_dir,
            "Rasters (*.tif *.tiff);;Vector files (*.gpkg *.sqlite)",
        )
        if not local_path:
            return

        QSettings().setValue(
            f"{RANA_SETTINGS_ENTRY}/last_upload_folder", str(Path(local_path).parent)
        )
        self.communication.bar_info("Start uploading file to Rana...")
        self.rana_widget.setEnabled(False)
        online_dir = ""
        if self.selected_file:
            assert self.selected_file["type"] == "directory"
            online_dir = self.selected_file["id"]

        online_path = online_dir + Path(local_path).name
        self.new_file_upload_worker = FileUploadWorker(
            self.project,
            Path(local_path),
            online_path,
        )
        self.new_file_upload_worker.finished.connect(
            partial(self.on_new_file_upload_finished, online_path)
        )
        self.new_file_upload_worker.failed.connect(self.on_file_upload_failed)
        self.new_file_upload_worker.progress.connect(self.on_file_upload_progress)
        self.new_file_upload_worker.warning.connect(
            lambda msg: self.communication.show_warn(msg)
        )
        self.new_file_upload_worker.start()

    def initialize_file_upload_worker(self):
        self.communication.bar_info("Start uploading file to Rana...")
        self.rana_widget.setEnabled(False)
        self.file_upload_worker = ExistingFileUploadWorker(
            self.project,
            self.selected_file,
        )
        self.file_upload_worker.finished.connect(self.on_file_upload_finished)
        self.file_upload_worker.failed.connect(self.on_file_upload_failed)
        self.file_upload_worker.progress.connect(self.on_file_upload_progress)
        self.file_upload_worker.conflict.connect(self.handle_file_conflict)
        self.file_upload_worker.warning.connect(
            lambda msg: self.communication.show_warn(msg)
        )
        self.file_upload_worker.start()

    def handle_file_conflict(self):
        warn_and_ask_msg = (
            "The file has been modified on the server since it was last downloaded.\n"
            "Do you want to overwrite the server copy with the local copy?"
        )
        file_overwrite = self.communication.ask(None, "File conflict", warn_and_ask_msg)
        sender = self.sender()
        assert isinstance(sender, QThread)
        sender.file_overwrite = file_overwrite

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

    def on_file_upload_finished(self):
        self.rana_widget.setEnabled(True)
        self.communication.clear_message_bar()
        self.communication.bar_info(f"File uploaded to Rana successfully!")
        self.refresh()
        sender = self.sender()
        assert isinstance(sender, QThread)
        sender.wait()

    def on_new_file_upload_finished(self, online_path: str):
        self.on_file_upload_finished()
        if self.communication.ask(
            self, "Load", "Would you like to load the uploaded file from Rana?"
        ):
            self.selected_file = get_tenant_project_file(
                self.project["id"], {"path": online_path}
            )
            self.initialize_file_download_worker()
            self.file_download_worker.start()

    def on_file_upload_failed(self, error: str):
        self.rana_widget.setEnabled(True)
        self.communication.clear_message_bar()
        self.communication.show_error(error)

    def on_file_upload_progress(self, progress: int):
        self.communication.progress_bar(
            "Uploading file to Rana...", 0, 100, progress, clear_msg_bar=True
        )

    def start_file_in_qgis(self, project_id: str, online_path: str):
        # Properly set members
        for project in self.projects:
            if project["id"] == project_id:
                self.communication.log_warn(f"Selecting project {project_id}")
                self.project = project
        self.selected_file = get_tenant_project_file(project_id, {"path": online_path})
        self.paths = ["Projects", self.project["name"]] + online_path.split("/")[:-1]
        if self.selected_file:
            self.communication.log_warn(f"Opening file {str(self.selected_file)}")
            self.open_file_in_qgis()
            self._update_file_UI()
        else:
            self.project = None
            self.paths = ["Projects"]

    def open_file_in_qgis(self):
        """Start the worker to download and open files in QGIS"""
        data_type = self.selected_file["data_type"]
        if data_type in self.SUPPORTED_DATA_TYPES.keys():
            self.initialize_file_download_worker()
            self.file_download_worker.start()
        else:
            self.communication.show_warn(f"Unsupported data type: {data_type}")

    def save_vector_styling_files(self):
        """Start the worker for saving vector styling files"""
        self.rana_widget.setEnabled(False)
        self.communication.progress_bar(
            "Generating and saving vector styling files...", clear_msg_bar=True
        )
        self.vector_style_worker = VectorStyleWorker(
            self.project,
            self.selected_file,
        )
        self.vector_style_worker.finished.connect(self.on_vector_style_finished)
        self.vector_style_worker.failed.connect(self.on_vector_style_failed)
        self.vector_style_worker.warning.connect(self.communication.show_warn)
        self.vector_style_worker.start()

    def on_vector_style_finished(self, msg: str):
        self.rana_widget.setEnabled(True)
        self.refresh()
        self.communication.clear_message_bar()
        self.communication.show_info(msg)

    def on_vector_style_failed(self, msg: str):
        self.rana_widget.setEnabled(True)
        self.communication.clear_message_bar()
        self.communication.show_error(msg)
