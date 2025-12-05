import os
from copy import deepcopy
from functools import partial
from pathlib import Path

from qgis.core import QgsDataSourceUri, QgsProject, QgsRasterLayer, QgsSettings
from qgis.PyQt.QtCore import (
    QObject,
    QSettings,
    QThread,
    QThreadPool,
    pyqtSignal,
    pyqtSlot,
)
from qgis.PyQt.QtWidgets import QApplication, QDialog, QFileDialog, QMessageBox
from threedi_api_client.openapi import ApiException
from threedi_mi_utils import LocalSchematisation, bypass_max_path_limit

from rana_qgis_plugin.auth import get_authcfg_id
from rana_qgis_plugin.auth_3di import get_3di_auth
from rana_qgis_plugin.constant import RANA_SETTINGS_ENTRY, SUPPORTED_DATA_TYPES
from rana_qgis_plugin.simulation.model_selection import ModelSelectionDialog
from rana_qgis_plugin.simulation.simulation_init import SimulationInit
from rana_qgis_plugin.simulation.simulation_wizard import SimulationWizard
from rana_qgis_plugin.simulation.threedi_calls import (
    ThreediCalls,
    get_api_client_with_personal_api_token,
)
from rana_qgis_plugin.simulation.utils import (
    CACHE_PATH,
    extract_error_message,
    load_remote_schematisation,
)
from rana_qgis_plugin.utils import (
    add_layer_to_qgis,
    get_local_file_path,
    get_threedi_api,
    get_threedi_schematisation_simulation_results_folder,
)
from rana_qgis_plugin.utils_api import (
    delete_tenant_project_directory,
    delete_tenant_project_file,
    get_frontend_settings,
    get_tenant_file_descriptor,
    get_tenant_file_descriptor_view,
    get_tenant_processes,
    get_tenant_project_file,
    get_threedi_schematisation,
    map_result_to_file_name,
    start_tenant_process,
)
from rana_qgis_plugin.utils_qgis import get_threedi_results_analysis_tool_instance
from rana_qgis_plugin.utils_settings import hcc_working_dir
from rana_qgis_plugin.widgets.result_browser import ResultBrowser
from rana_qgis_plugin.widgets.schematisation_upload_wizard import (
    SchematisationUploadWizard,
)
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
    loading_cancelled = pyqtSignal()
    download_results_cancelled = pyqtSignal()
    simulation_cancelled = pyqtSignal()
    simulation_started = pyqtSignal()
    simulation_started_failed = pyqtSignal()
    file_deleted = pyqtSignal()

    def __init__(self, communication, parent):
        super().__init__(parent)
        self.file_download_worker: QThread = None
        self.file_upload_worker: QThread = None
        self.vector_style_worker: QThread = None
        self.new_file_upload_worker: QThread = None
        self.communication = communication

        # For simulations
        self.simulation_runner_pool = QThreadPool()
        self.simulation_runner_pool.setMaxThreadCount(1)

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

    @pyqtSlot(dict, dict)
    def open_schematisation_with_revision(self, revision, schematisation):
        if not hcc_working_dir():
            self.communication.show_warn(
                "Working directory not yet set, please configure this in the plugin settings."
            )
            return

        pb = self.communication.progress_bar(
            msg="Downloading remote schematisation...", clear_msg_bar=True
        )

        load_remote_schematisation(
            self.communication,
            schematisation,
            revision,
            pb,
            hcc_working_dir(),
            get_threedi_api(),
        )
        self.file_download_finished.emit(None)

    def on_file_download_finished(self, project, file, local_file_path: str):
        self.communication.clear_message_bar()
        self.communication.bar_info(
            f"File(s) downloaded to: {local_file_path}", dur=240
        )
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
                            self.parent(),
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
            f"Generating/downloading file {file_name}...",
            0,
            100,
            progress,
            clear_msg_bar=True,
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
    def delete_file(self, project, file):
        if file["type"] == "directory":
            if delete_tenant_project_directory(project["id"], {"path": file["id"]}):
                self.file_deleted.emit()
            else:
                self.communication.show_warn(f"Unable to delete directory {file['id']}")
        else:
            if delete_tenant_project_file(project["id"], {"path": file["id"]}):
                self.file_deleted.emit()
            else:
                self.communication.show_warn(f"Unable to delete file {file['id']}")

    @pyqtSlot(dict)
    @pyqtSlot(dict, int)
    def create_schematisation_revision_3di_model(self, file, revision_id=None):
        tc = ThreediCalls(get_threedi_api())
        # Retrieve schematisation info
        schematisation = get_threedi_schematisation(
            self.communication, file["descriptor_id"]
        )
        if not revision_id:
            revision_id = schematisation["latest_revision"]["id"]
        schematisation_id = schematisation["schematisation"]["id"]
        try:
            tc.create_schematisation_revision_3di_model(schematisation_id, revision_id)
        except ApiException as e:
            if e.status == 400:
                QMessageBox.warning(
                    QApplication.activeWindow(), "Warning", eval(e.body)[0]
                )
            else:
                raise

    @pyqtSlot(dict, dict)
    @pyqtSlot(dict, dict, int)
    def start_simulation(self, project, file, revision_id=None):
        os.makedirs(CACHE_PATH, exist_ok=True)
        if not hcc_working_dir():
            self.communication.show_warn(
                "Working directory not yet set, please configure this in the plugin settings."
            )
            self.simulation_started_failed.emit()
            return

        threedi_api = get_threedi_api()
        tc = ThreediCalls(threedi_api)
        organisations = {org.unique_id: org for org in tc.fetch_organisations()}

        # Retrieve schematisation info
        schematisation = get_threedi_schematisation(
            self.communication, file["descriptor_id"]
        )

        # Pick latest revision if no revision is provided
        if revision_id:
            revision = tc.fetch_schematisation_revision(
                schematisation["schematisation"]["id"], revision_id
            ).to_dict()
        else:
            revision = schematisation["latest_revision"]

        if not revision["has_threedimodel"]:
            self.communication.show_warn("Generate a model first")
            self.simulation_started_failed.emit()
            return

        # Retrieve templates
        current_model = tc.fetch_schematisation_revision_3di_models(
            schematisation["schematisation"]["id"], revision["id"]
        )[0]

        template_dialog = ModelSelectionDialog(
            self.communication,
            current_model.id,
            threedi_api,
            organisations,
            schematisation["schematisation"]["id"],
            self.parent(),
        )
        if template_dialog.exec() == QDialog.Rejected:
            self.simulation_cancelled.emit()
            return

        simulation_template = template_dialog.get_selected_template()
        organisation = template_dialog.get_selected_organisation()

        (
            simulation,
            settings_overview,
            events,
            lizard_post_processing_overview,
        ) = self.get_simulation_data_from_template(tc, simulation_template)

        simulation_init_wizard = SimulationInit(
            current_model,
            simulation_template,
            settings_overview,
            events,
            lizard_post_processing_overview,
            organisation,
            api=tc,
            parent=self.parent(),
        )
        if simulation_init_wizard.exec() == QDialog.Rejected:
            self.simulation_cancelled.emit()
            return

        if simulation_init_wizard.open_wizard:
            simulation_wizard = SimulationWizard(
                self.simulation_runner_pool,
                hcc_working_dir(),
                simulation_template,
                organisation,
                current_model,
                threedi_api,
                self.communication,
                simulation_init_wizard,
                self.parent(),
            )
            if simulation:
                simulation_wizard.load_template_parameters(
                    simulation,
                    settings_overview,
                    events,
                    lizard_post_processing_overview,
                )
            simulation_wizard.simulation_created.connect(
                partial(self.start_process, project, file)
            )
            simulation_wizard.simulation_created_failed.connect(
                self.simulation_started_failed
            )

            if simulation_wizard.exec() == QDialog.Rejected:
                self.simulation_cancelled.emit()

    def start_process(self, project, file, simulations):
        # Find the simulation tracker processes
        processes = get_tenant_processes(self.communication)
        track_process = None
        for process in processes:
            if "simulation_tracker" in process["tags"]:
                track_process = process["id"]
                break

        if track_process is None:
            self.communication.log_err("No simulation tracker available")
            return

        # Store the result in the same folder as the file
        output_file_path = file["id"].rpartition("/")[0] + file["id"].rpartition("/")[1]

        for sim in simulations:
            params = {
                "project_id": project["id"],
                "inputs": {"simulation_id": sim.simulation.id},
                "outputs": {
                    "results": {
                        "id": f"{output_file_path}{sim.simulation.name}_{sim.simulation.id}_results.zip"
                    }
                },
                "name": f"simulation_tracker_{sim.simulation.name}",
            }
            _ = start_tenant_process(self.communication, track_process, params)

        self.simulation_started.emit()

    def get_simulation_data_from_template(self, tc, template):
        simulation, settings_overview, events, lizard_post_processing_overview = (
            None,
            None,
            None,
            None,
        )
        try:
            simulation = template.simulation
            sim_id = simulation.id
            settings_overview = tc.fetch_simulation_settings_overview(str(sim_id))
            events = tc.fetch_simulation_events(sim_id)
            cloned_from_url = simulation.cloned_from
            if cloned_from_url:
                source_sim_id = cloned_from_url.strip("/").split("/")[-1]
                lizard_post_processing_overview = (
                    tc.fetch_simulation_lizard_postprocessing_overview(source_sim_id)
                )
        except ApiException as e:
            error_msg = extract_error_message(e)
            if "No basic post-processing resource found" not in error_msg:
                self.communication.bar_error(error_msg)
        except Exception as e:
            error_msg = f"Error: {e}"
            self.communication.bar_error(error_msg)
        return simulation, settings_overview, events, lizard_post_processing_overview

    @pyqtSlot(dict, dict)
    def download_results(self, project, file):
        if not QgsSettings().contains("threedi/working_dir"):
            self.communication.show_warn(
                "Working directory not yet set, please configure this in the plugin settings."
            )
        descriptor = get_tenant_file_descriptor(file["descriptor_id"])
        if (
            not descriptor["meta"]
            or not descriptor["meta"]["simulation"]
            or not descriptor["meta"]["simulation"]["name"]
        ):
            self.communication.show_error(
                "Scenario is corrupt; did you upload a zip directly?"
            )
            self.download_results_cancelled.emit()
            return
        schematisation_name = descriptor["meta"]["schematisation"]["name"]
        schematisation_id = descriptor["meta"]["schematisation"]["id"]
        schematisation_version = descriptor["meta"]["schematisation"]["version"]
        assert descriptor["data_type"] == "scenario"

        # Determine local target folder for simulatuon
        target_folder = get_threedi_schematisation_simulation_results_folder(
            QgsSettings().value("threedi/working_dir"),
            schematisation_id,
            schematisation_name.replace("/", "-").replace("\\", "-"),
            schematisation_version,
            descriptor["meta"]["simulation"]["name"]
            .replace("/", "-")
            .replace("\\", "-"),
        )
        os.makedirs(target_folder, exist_ok=True)

        for link in descriptor["links"]:
            if link["rel"] == "lizard-scenario-results":
                grid = deepcopy(descriptor["meta"]["grid"])
                results = get_tenant_file_descriptor_view(
                    file["descriptor_id"], "lizard-scenario-results"
                )
                result_browser = ResultBrowser(None, results, grid["crs"])
                if result_browser.exec() == QDialog.DialogCode.Accepted:
                    result_ids, nodata, pixelsize, crs = (
                        result_browser.get_selected_results()
                    )
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
                                self.parent(),
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
                        project=project,
                        file=file,
                        result_ids=filtered_result_ids,
                        target_folder=target_folder,
                        grid=grid,
                        nodata=nodata,
                        crs=crs,
                        pixelsize=pixelsize,
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
                else:
                    self.download_results_cancelled.emit()

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
            self.loading_cancelled.emit()
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
        file_overwrite = self.communication.ask(
            self.parent(), "File conflict", warn_and_ask_msg
        )
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
            self.parent(), "Load", "Would you like to load the uploaded file from Rana?"
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

    @pyqtSlot(dict, dict)
    def save_revision(self, project, file):
        if file["data_type"] != "threedi_schematisation":
            return
        self.communication.bar_info("Start uploading revision to Rana...")
        schematisation = get_threedi_schematisation(
            self.communication, file["descriptor_id"]
        )
        _, schematisation_filepath = get_local_file_path(project["slug"], file["id"])
        current_local_schematisation = LocalSchematisation.initialize_from_location(
            schematisation_filepath, use_config_for_revisions=False
        )
        # todo: replace with convenience function
        _, personal_api_token = get_3di_auth()
        frontend_settings = get_frontend_settings()
        api_url = frontend_settings["hcc_url"].rstrip("/")
        threedi_api = get_api_client_with_personal_api_token(
            personal_api_token, api_url
        )
        tc = ThreediCalls(threedi_api)
        # TODO: this needs to be fixed!!!!!!!!!!!!!
        organisation = tc.fetch_organisations()[0]
        SchematisationUploadWizard(
            current_local_schematisation=current_local_schematisation,
            schematisation=schematisation["schematisation"],
            schematisation_filepath=schematisation_filepath,
            threedi_api=threedi_api,
            organisation=organisation,
            communication=self.communication,
            parent=None,
        )
        SchematisationUploadWizard.exec()
