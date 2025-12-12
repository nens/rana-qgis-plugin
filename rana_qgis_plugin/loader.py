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
from threedi_mi_utils import bypass_max_path_limit, list_local_schematisations

from rana_qgis_plugin.auth import get_authcfg_id
from rana_qgis_plugin.constant import RANA_SETTINGS_ENTRY, SUPPORTED_DATA_TYPES
from rana_qgis_plugin.simulation.load_schematisation.schematisation_load_local import (
    SchematisationLoad,
)
from rana_qgis_plugin.simulation.model_selection import ModelSelectionDialog
from rana_qgis_plugin.simulation.simulation_init import SimulationInit
from rana_qgis_plugin.simulation.simulation_wizard import SimulationWizard
from rana_qgis_plugin.simulation.threedi_calls import ThreediCalls
from rana_qgis_plugin.simulation.upload_wizard.model_deletion import ModelDeletionDialog
from rana_qgis_plugin.simulation.upload_wizard.upload_wizard import UploadWizard
from rana_qgis_plugin.simulation.utils import (
    CACHE_PATH,
    BuildOptionActions,
    extract_error_message,
    load_local_schematisation,
    load_remote_schematisation,
)
from rana_qgis_plugin.simulation.workers import SchematisationUploadProgressWorker
from rana_qgis_plugin.utils import (
    add_layer_to_qgis,
    get_threedi_api,
    get_threedi_schematisation_simulation_results_folder,
)
from rana_qgis_plugin.utils_api import (
    add_threedi_schematisation,
    create_folder,
    create_tenant_project_directory,
    delete_tenant_project_directory,
    delete_tenant_project_file,
    get_tenant_details,
    get_tenant_file_descriptor,
    get_tenant_file_descriptor_view,
    get_tenant_processes,
    get_tenant_project_file,
    get_tenant_project_files,
    get_threedi_schematisation,
    map_result_to_file_name,
    move_directory,
    move_file,
    start_tenant_process,
)
from rana_qgis_plugin.utils_qgis import (
    get_threedi_results_analysis_tool_instance,
    is_loaded_in_schematisation_editor,
)
from rana_qgis_plugin.utils_settings import hcc_working_dir
from rana_qgis_plugin.widgets.result_browser import ResultBrowser
from rana_qgis_plugin.widgets.schematisation_browser import SchematisationBrowser
from rana_qgis_plugin.widgets.schematisation_new_wizard import NewSchematisationWizard
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
    schematisation_upload_cancelled = pyqtSignal()
    schematisation_upload_finished = pyqtSignal()
    schematisation_import_finished = pyqtSignal()
    schematisation_upload_failed = pyqtSignal()
    simulation_cancelled = pyqtSignal()
    simulation_started = pyqtSignal()
    simulation_started_failed = pyqtSignal()
    file_deleted = pyqtSignal()
    rename_finished = pyqtSignal()
    folder_created = pyqtSignal()
    model_deleted = pyqtSignal()

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

        # For upload of schematisations
        self.upload_thread_pool = QThreadPool()
        self.upload_thread_pool.setMaxThreadCount(1)

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

    @pyqtSlot(dict, dict, str)
    def rename_file(self, project, file, new_name):
        # create names without trailing /
        source_path = file["id"].rstrip("/")
        try:
            target_path = str(Path(source_path).with_name(new_name))
        except ValueError:
            self.communication.show_warn(f"Cannot rename to invalid name '{new_name}'")
            self.rename_finished.emit()
        if file["type"] == "directory":
            # check for duplicates
            if len(Path(source_path).parents) > 1:
                root_path = Path(source_path).parent.as_posix()
            else:
                root_path = None
            names = [
                file["id"].strip("/")
                for file in get_tenant_project_files(
                    self.communication,
                    project["id"],
                    params={"path": root_path} if root_path else None,
                )
                if file["type"] == "directory"
            ]
            if new_name in names:
                QMessageBox.warning(
                    self.parent(), "Warning", f"Folder {new_name} already exists."
                )
                return
            success = move_directory(
                project["id"],
                params={
                    "source_path": source_path + "/",
                    "destination_path": target_path + "/",
                },
            )
            if not success:
                self.communication.show_warn(f"Unable to rename directory {file['id']}")
        else:
            file = get_tenant_project_file(project["id"], {"path": target_path})
            if file:
                QMessageBox.warning(
                    self.parent(), "Warning", f"Folder {new_name} already exists."
                )
                return
            success = move_file(
                project["id"],
                params={"source_path": source_path, "destination_path": target_path},
            )
            if not success:
                self.communication.show_warn(f"Unable to rename file {file['id']}")
        self.rename_finished.emit()

    @pyqtSlot(dict, dict, str)
    def create_new_folder_on_rana(self, project, selected_item, folder_name: str):
        """Create new folder on Rana and show warning when folder already exists"""

        root_path = selected_item["id"]
        names = [
            file["id"].strip("/")
            for file in get_tenant_project_files(
                self.communication,
                project["id"],
                params={"path": root_path} if root_path else None,
            )
            if file["type"] == "directory"
        ]
        if folder_name in names:
            QMessageBox.warning(
                self.parent(), "Warning", f"Folder {folder_name} already exists."
            )
            return
        folder_path = root_path + folder_name + "/"
        success = create_folder(project["id"], params={"path": folder_path})
        if success:
            self.folder_created.emit()
        else:
            self.communication.show_warn(f"Unable to create folder {folder_name}")

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

    @pyqtSlot(dict, int)
    def delete_schematisation_revision_3di_model(self, file, revision_id):
        tc = ThreediCalls(get_threedi_api())
        # Retrieve schematisation info
        schematisation = get_threedi_schematisation(
            self.communication, file["descriptor_id"]
        )
        # Make sure the revision has a model that can be deleted
        revision = tc.fetch_schematisation_revision(
            schematisation["schematisation"]["id"], revision_id
        )
        if not revision or not revision.has_threedimodel:
            return
        # fetch_schematisation_revision_3di_models only returns enabled models
        # and there can only be one active model, so we can safely take the first
        current_model = tc.fetch_schematisation_revision_3di_models(
            schematisation["schematisation"]["id"], revision_id
        )[0]
        tc.delete_3di_model(current_model.id)
        revision = tc.fetch_schematisation_revision(
            schematisation["schematisation"]["id"], revision_id
        )
        if not revision.has_threedimodel:
            self.model_deleted.emit()

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
            self.download_results_cancelled.emit()
            return
        descriptor = get_tenant_file_descriptor(file["descriptor_id"])
        if (
            not descriptor["meta"]
            or not descriptor["meta"]["simulation"]
            or not descriptor["meta"]["simulation"]["name"]
        ):
            if descriptor["status"]["id"] == "processing":
                self.communication.show_warn(
                    "Scenario is still processing; please try again later"
                )
            else:
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
        local_paths, _ = QFileDialog.getOpenFileNames(
            None,
            "Open file(s)",
            last_saved_dir,
            "All supported files (*.tif *.tiff *.gpkg *.sqlite);;"
            "Rasters (*.tif *.tiff);;"
            "Vector files (*.gpkg *.sqlite)",
        )
        if not local_paths:
            self.loading_cancelled.emit()
            return

        QSettings().setValue(
            f"{RANA_SETTINGS_ENTRY}/last_upload_folder",
            str(Path(local_paths[0]).parent),
        )
        self.communication.bar_info("Start uploading file(s) to Rana...")
        online_dir = ""
        if file:
            assert file["type"] == "directory"
            online_dir = file["id"]

        self.new_file_upload_worker = FileUploadWorker(
            project,
            [Path(local_path) for local_path in local_paths],
            online_dir,
        )
        online_path = (
            online_dir + Path(local_paths[0]).name if len(local_paths) == 1 else None
        )
        self.new_file_upload_worker.finished.connect(
            partial(self.on_new_file_upload_finished, online_path)
        )
        self.new_file_upload_worker.finished.connect(self.on_file_upload_finished)
        self.new_file_upload_worker.failed.connect(self.on_file_upload_failed)
        if len(local_paths) == 1:
            self.new_file_upload_worker.failed.connect(
                lambda error: self.file_upload_failed.emit(error)
            )
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
        self.file_upload_worker.failed.connect(
            lambda error: self.file_upload_failed.emit(error)
        )
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
        if online_path and self.communication.ask(
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
    def import_schematisation_to_rana(self, project, selected_file):
        dialog = SchematisationBrowser(self.parent(), self.communication)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_schematisation = dialog.selected_schematisation
            assert selected_schematisation
            add_threedi_schematisation(
                self.communication,
                project["id"],
                selected_schematisation["id"],
                selected_file["id"] + selected_schematisation["name"],
            )
            self.schematisation_import_finished.emit()

    @pyqtSlot(dict)
    def upload_new_schematisation_to_rana(self, project):
        threedi_api = get_threedi_api()
        tenant_details = get_tenant_details(self.communication)
        if not tenant_details:
            return
        available_organisations = [
            org.replace("-", "") for org in tenant_details["threedi_organisations"]
        ]
        tc = ThreediCalls(threedi_api)
        organisations = {
            org.unique_id: org
            for org in tc.fetch_organisations()
            if org.unique_id in available_organisations
        }

        work_dir = QSettings().value("threedi/working_dir", "")
        new_schematisation_wizard = NewSchematisationWizard(
            threedi_api, work_dir, self.communication, organisations
        )
        response = new_schematisation_wizard.exec()
        if response != QDialog.DialogCode.Accepted:
            self.schematisation_upload_cancelled.emit()
            return

        new_schematisation = new_schematisation_wizard.new_schematisation
        if new_schematisation is None:
            self.communication.bar_error("Schematisation creation failed")
            self.schematisation_upload_failed.emit()
            return
        rana_path = new_schematisation_wizard.rana_path.replace("\\", "/").rstrip("/")
        # check if directory path exists, otherwise make it
        path_info = get_tenant_project_files(
            communication=self.communication,
            project_id=project["id"],
            params={"path": rana_path},
        )
        if not path_info:
            # don't continue if path creation fails for some reason
            assert create_tenant_project_directory(
                project_id=project["id"], path=rana_path
            )
            path_info = get_tenant_project_files(
                communication=self.communication,
                project_id=project["id"],
                params={"path": rana_path},
            )
        if rana_path != "" and path_info[0]["type"] != "directory":
            self.communication.bar_info(
                f"Adding schematisation {new_schematisation.name} to main directory in Rana project {project['name']} since specified path is unavailable"
            )
            rana_path = ""

        if rana_path:
            file_path = rana_path + "/" + new_schematisation.name
        else:
            file_path = new_schematisation.name
        response = add_threedi_schematisation(
            communication=self.communication,
            project_id=project["id"],
            schematisation_id=new_schematisation.id,
            path=file_path,
        )
        if response:
            message = (
                f"3Di schematisation {new_schematisation.name} added to Rana project"
            )
            if rana_path:
                message += f" in directory {rana_path}"
            self.communication.bar_info(message)
        else:
            self.schematisation_upload_failed.emit()
            self.communication.bar_error(
                f"Could not add 3Di schematisation {new_schematisation.name} to Rana project {project['name']}!"
            )
        self.schematisation_upload_finished.emit()
        local_schematisation = new_schematisation_wizard.new_local_schematisation
        load_local_schematisation(
            communication=self.communication,
            local_schematisation=local_schematisation,
            action=BuildOptionActions.CREATED,
        )

    @pyqtSlot(dict, dict)
    def save_revision(self, project, file):
        if file["data_type"] != "threedi_schematisation":
            return

        rana_schematisation = get_threedi_schematisation(
            self.communication, file["descriptor_id"]
        )

        threedi_api = get_threedi_api()
        tc = ThreediCalls(threedi_api)
        schematisation = tc.fetch_schematisation(
            rana_schematisation["schematisation"]["id"]
        )

        local_schematisations = list_local_schematisations(
            hcc_working_dir(), use_config_for_revisions=False
        )

        # Check whether we have this schematisation locally
        local_schematisation = local_schematisations.get(schematisation.id)
        if local_schematisation is None:
            self.communication.show_warn(
                "Current schematisation not yet stored locally, please download a revision first."
            )
            return

        self.organisations = {org.unique_id: org for org in tc.fetch_organisations()}
        organisation = self.organisations.get(schematisation.owner)

        # Let the user select a local revision
        load_dialog = SchematisationLoad(
            hcc_working_dir(), self.communication, local_schematisation, self.parent()
        )
        if load_dialog.exec() == QDialog.DialogCode.Accepted:
            # Upload that revision as new revision
            local_schematisation = load_dialog.selected_local_schematisation
            schematisation_filepath = local_schematisation.schematisation_db_filepath

            schema_gpkg_loaded = is_loaded_in_schematisation_editor(
                schematisation_filepath
            )
            if schema_gpkg_loaded is False:
                question = "Warning: the revision you are about to upload is not loaded in the Rana Schematisation Editor. Do you want to continue?"
                if not self.communication.ask(
                    self.parent(), "Warning", question, QMessageBox.Warning
                ):
                    self.schematisation_upload_cancelled.emit()
                    return

            upload_dial = UploadWizard(
                local_schematisation,
                schematisation,
                schematisation_filepath,
                organisation,
                self.communication,
                tc,
                self.parent(),
            )
            if upload_dial.exec() == QDialog.DialogCode.Accepted:
                new_upload = upload_dial.new_upload
                if not new_upload:
                    return
                if new_upload["make_3di_model"]:
                    user_profile = threedi_api.auth_profile_list()
                    current_user = {
                        "username": user_profile.username,
                        "first_name": user_profile.first_name,
                        "last_name": user_profile.last_name,
                    }
                    deletion_dlg = ModelDeletionDialog(
                        self.communication,
                        threedi_api,
                        local_schematisation,
                        organisation,
                        current_user,
                        self.parent(),
                    )

                    if deletion_dlg.threedi_models_to_show:
                        if deletion_dlg.exec() == QDialog.DialogCode.Rejected:
                            self.communication.bar_warn("Uploading canceled...")
                            self.schematisation_upload_cancelled.emit()
                        return

                # Do the actual upload
                upload_worker = SchematisationUploadProgressWorker(
                    threedi_api,
                    local_schematisation,
                    new_upload,
                )

                upload_worker.signals.thread_finished.connect(
                    self.schematisation_upload_finished
                )
                upload_worker.signals.upload_failed.connect(
                    self.schematisation_upload_failed
                )
                upload_worker.signals.upload_progress.connect(
                    self.on_schematisation_upload_progress
                )

                self.upload_thread_pool.start(upload_worker)

    def on_schematisation_upload_progress(
        self, task_name, task_progress, total_progress
    ):
        self.communication.progress_bar(
            f"Uploading revision",
            0,
            100,
            total_progress,
            clear_msg_bar=True,
        )
