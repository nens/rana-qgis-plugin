import os
from functools import partial
from pathlib import Path

from qgis.core import QgsDataSourceUri, QgsProject, QgsRasterLayer, QgsSettings
from qgis.PyQt.QtCore import QObject, QSettings, QThread, pyqtSignal, pyqtSlot
from qgis.PyQt.QtWidgets import QDialog, QFileDialog
from threedi_mi_utils import bypass_max_path_limit

from rana_qgis_plugin.auth import get_authcfg_id
from rana_qgis_plugin.constant import RANA_SETTINGS_ENTRY, SUPPORTED_DATA_TYPES
from rana_qgis_plugin.utils import (
    add_layer_to_qgis,
    get_threedi_schematisation_simulation_results_folder,
)
from rana_qgis_plugin.utils_api import (
    get_tenant_file_descriptor,
    get_tenant_file_descriptor_view,
    get_tenant_project_file,
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


class Loader(QObject):
    file_download_finished = pyqtSignal(str)
    file_download_failed = pyqtSignal(str)
    file_download_progress = pyqtSignal(int, str)
    file_upload_finished = pyqtSignal()
    file_upload_failed = pyqtSignal(str)
    file_upload_progress = pyqtSignal(int)
    file_upload_conflict = pyqtSignal()
    new_file_upload_finished = pyqtSignal(str)
    vector_style_finished = pyqtSignal()
    vector_style_failed = pyqtSignal(str)

    def __init__(self, communication, parent=None):
        super().__init__(parent)
        self.file_download_worker: QThread = None
        self.file_upload_worker: QThread = None
        self.vector_style_worker: QThread = None
        self.new_file_upload_worker: QThread = None
        self.communication = communication

    @pyqtSlot(dict, dict)
    def open_wms(self, _: dict, file: dict) -> bool:
        descriptor = get_tenant_file_descriptor(file["descriptor_id"])
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
                return True

        return False

    @pyqtSlot(dict, dict)
    def open_in_qgis(self, project: dict, file: dict):
        """Start the worker to download and open files in QGIS"""
        data_type = file["data_type"]
        if data_type in SUPPORTED_DATA_TYPES.keys():
            self.initialize_file_download_worker(project, file)
            self.file_download_worker.start()
        else:
            self.communication.show_warn(f"Unsupported data type: {data_type}")

    def on_file_download_finished(self, project, file, local_file_path: str):
        self.communication.clear_message_bar()
        self.communication.bar_info(f"File(s) downloaded to: {local_file_path}")
        sender = self.sender()
        assert isinstance(sender, QThread)
        sender.wait()

        if file["data_type"] == "scenario":
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
                            None,
                            "Rana",
                            "Do you want to add the results of this simulation to the current project so you can analyse them with 3Di Results Analysis?",
                        ):
                            ra_tool.load_result(result_path, admin_path)
        else:
            schematisation = None
            if file["data_type"] == "threedi_schematisation":
                schematisation = get_threedi_schematisation(
                    self.communication, file["descriptor_id"]
                )
            add_layer_to_qgis(
                self.communication,
                local_file_path,
                project["name"],
                file,
                get_tenant_file_descriptor(file["descriptor_id"]),
                schematisation,
            )
        self.file_download_finished.emit(local_file_path)

    def on_file_download_failed(self, error: str):
        self.communication.clear_message_bar()
        self.communication.show_error(error)
        self.file_download_failed.emit(error)

    def on_file_download_progress(self, progress: int, file_name: str = ""):
        self.communication.progress_bar(
            f"Downloading file {file_name}...", 0, 100, progress, clear_msg_bar=True
        )
        self.file_download_progress.emit(progress, file_name)

    def initialize_file_download_worker(self, project, file):
        self.communication.bar_info("Start downloading file...")
        self.file_download_worker = FileDownloadWorker(
            project,
            file,
        )
        self.file_download_worker.finished.connect(self.on_file_download_finished)
        self.file_download_worker.failed.connect(self.on_file_download_failed)
        self.file_download_worker.progress.connect(self.on_file_download_progress)

    @pyqtSlot(dict, dict)
    def upload_file_to_rana(self, project, file):
        """Start the worker for uploading files"""
        self.initialize_file_upload_worker(project, file)
        self.file_upload_worker.start()

    @pyqtSlot(dict, dict)
    def download_results(self, project, file):
        if not QgsSettings().contains("threedi/working_dir"):
            self.communication.show_warn(
                "3Di working directory not yet set, please configure this in 3Di Models & Simulations plugin."
            )

        descriptor = get_tenant_file_descriptor(file["descriptor_id"])
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
                    file["descriptor_id"], "lizard-scenario-results"
                )
                result_browser = ResultBrowser(None, results)
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
                                None,
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
                        project,
                        file,
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

    @pyqtSlot(dict, dict)
    def download_file(self, project, file):
        assert file["data_type"] == "scenario"

        self.initialize_file_download_worker(project, file)
        self.file_download_worker.start()

    @pyqtSlot(dict, dict)
    def upload_new_file_to_rana(self, project, file):
        """Upload a local (new) file to Rana"""
        last_saved_dir = QSettings().value(
            f"{RANA_SETTINGS_ENTRY}/last_upload_folder", ""
        )
        local_path, _ = QFileDialog.getOpenFileName(
            None,
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
        online_dir = ""
        if file:
            assert file["type"] == "directory"
            online_dir = file["id"]

        online_path = online_dir + Path(local_path).name
        self.new_file_upload_worker = FileUploadWorker(
            project,
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

    def initialize_file_upload_worker(self, project, file):
        self.communication.bar_info("Start uploading file to Rana...")
        self.file_upload_worker = ExistingFileUploadWorker(
            project,
            file,
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

    def on_file_upload_finished(self):
        self.communication.clear_message_bar()
        self.communication.bar_info(f"File uploaded to Rana successfully!")
        sender = self.sender()
        assert isinstance(sender, QThread)
        sender.wait()

        self.file_upload_finished.emit()

    def on_new_file_upload_finished(self, online_path: str, project):
        self.on_file_upload_finished()
        if self.communication.ask(
            None, "Load", "Would you like to load the uploaded file from Rana?"
        ):
            file = get_tenant_project_file(project["id"], {"path": online_path})
            self.initialize_file_download_worker(project, file)
            self.file_download_worker.finished.connect(self.on_file_download_finished)
            self.file_download_worker.start()
        self.new_file_upload_finished.emit(online_path)

    def on_file_upload_failed(self, error: str):
        self.communication.clear_message_bar()
        self.communication.show_error(error)
        self.file_upload_failed.emit(error)

    def on_file_upload_progress(self, progress: int):
        self.communication.progress_bar(
            "Uploading file to Rana...", 0, 100, progress, clear_msg_bar=True
        )
        self.file_upload_progress.emit(progress)

    @pyqtSlot(dict, dict)
    def save_vector_style(self, project, file):
        """Start the worker for saving vector styling files"""
        self.communication.progress_bar(
            "Generating and saving vector styling files...", clear_msg_bar=True
        )
        self.vector_style_worker = VectorStyleWorker(
            project,
            file,
        )
        self.vector_style_worker.finished.connect(self.on_vector_style_finished)
        self.vector_style_worker.failed.connect(self.on_vector_style_failed)
        self.vector_style_worker.warning.connect(self.communication.show_warn)
        self.vector_style_worker.start()

    def on_vector_style_finished(self, msg: str):
        self.communication.clear_message_bar()
        self.communication.show_info(msg)
        self.vector_style_finished.emit()

    def on_vector_style_failed(self, msg: str):
        self.communication.clear_message_bar()
        self.communication.show_error(msg)
        self.vector_style_failed.emit(msg)
