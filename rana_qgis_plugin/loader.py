import os
from copy import deepcopy
from functools import partial
from pathlib import Path
from typing import Optional

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
from threedi_api_client.openapi import ApiException, SchematisationRevision
from threedi_mi_utils import bypass_max_path_limit, list_local_schematisations

from rana_qgis_plugin.auth import get_authcfg_id
from rana_qgis_plugin.communication import UICommunication
from rana_qgis_plugin.constant import RANA_SETTINGS_ENTRY, SUPPORTED_DATA_TYPES
from rana_qgis_plugin.persistent_workers import (
    PersistentTaskScheduler,
    ProjectJobMonitorWorker,
    PublicationMonitorWorker,
)
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
    UploadFileStatus,
    UploadFileType,
    extract_error_message,
    load_local_schematisation,
    load_remote_schematisation,
)
from rana_qgis_plugin.simulation.workers import SchematisationUploadProgressWorker
from rana_qgis_plugin.utils import (
    add_layer_to_qgis,
    get_local_file_path,
    get_threedi_api,
    get_threedi_organisations,
    get_threedi_schematisation_simulation_results_folder,
)
from rana_qgis_plugin.utils_api import (
    add_threedi_schematisation,
    create_folder,
    delete_tenant_project_directory,
    delete_tenant_project_file,
    get_process_id_for_tag,
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
    convert_vectorfile_to_geopackage,
    get_threedi_results_analysis_tool_instance,
    is_loaded_in_schematisation_editor,
)
from rana_qgis_plugin.utils_settings import hcc_working_dir
from rana_qgis_plugin.widgets.result_browser import ResultBrowser
from rana_qgis_plugin.widgets.schematisation_browser import SchematisationBrowser
from rana_qgis_plugin.widgets.schematisation_new_wizard import NewSchematisationWizard
from rana_qgis_plugin.workers import (
    AvatarWorker,
    ExistingFileUploadWorker,
    FileDownloadWorker,
    FileUploadWorker,
    LizardResultDownloadWorker,
    RasterStyleWorker,
    VectorStyleWorker,
)

STYLE_DIR = Path(__file__).parent / "styles"


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
    raster_style_finished = pyqtSignal()
    raster_style_failed = pyqtSignal(str)
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
    rename_finished = pyqtSignal(str)
    rename_aborted = pyqtSignal()
    folder_created = pyqtSignal()
    schematisation_uploaded = pyqtSignal()
    schematisation_upload_failed = pyqtSignal()
    model_created = pyqtSignal()
    revision_saved = pyqtSignal()
    model_deleted = pyqtSignal()
    project_jobs_added = pyqtSignal(list)
    project_job_updated = pyqtSignal(dict)
    project_publications_added = pyqtSignal(list)
    project_publication_updated = pyqtSignal(dict)
    avatar_updated = pyqtSignal(str, "QPixmap")
    file_opened = pyqtSignal(dict)

    def __init__(self, communication, parent):
        super().__init__(parent)
        self.file_download_worker: QThread = None
        self.file_upload_worker: QThread = None
        self.vector_style_worker: QThread = None
        self.raster_style_worker: QThread = None
        self.new_file_upload_worker: QThread = None
        self.communication = communication

        # For simulations
        self.simulation_runner_pool = QThreadPool()
        self.simulation_runner_pool.setMaxThreadCount(1)

        # For collecting avatars
        self.avatar_runner_pool = QThreadPool()
        self.avatar_runner_pool.setMaxThreadCount(1)

        # For upload of schematisations
        self.upload_thread_pool = QThreadPool()
        self.upload_thread_pool.setMaxThreadCount(1)

        # Create persistent scheduler that handles background monitoring
        self.persistent_scheduler = PersistentTaskScheduler()
        self.persistent_scheduler.start()

    def cleanup(self):
        self.persistent_scheduler.stop()

    def __del__(self):
        self.cleanup()

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
                self.file_opened.emit(file)
                return True

        return False

    @pyqtSlot(dict, dict)
    def open_in_qgis(self, project: dict, file: dict):
        """Start the worker to download and open files in QGIS"""
        data_type = file["data_type"]
        if data_type in SUPPORTED_DATA_TYPES.keys():
            _, local_file_path = get_local_file_path(project["slug"], file["id"])
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
        self.file_opened.emit(file)
        self.file_download_finished.emit(None)

    def on_file_download_finished(
        self, project, file, local_file_path: str, from_thread=True
    ):
        self.communication.clear_message_bar()
        self.communication.bar_info(
            f"File(s) downloaded to: {local_file_path}", dur=240
        )
        if from_thread:
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
                waterdepth_path = os.path.join(local_file_path, "max_waterdepth.tif")
                if os.path.exists(result_path) and os.path.exists(admin_path):
                    if hasattr(ra_tool, "load_result"):
                        if self.communication.ask(
                            self.parent(),
                            "Rana",
                            "Do you want to add the results of this simulation to the current project so you can analyse them with Results Analysis?",
                        ):
                            ra_tool.load_result(result_path, admin_path)
                            if not ra_tool.dockwidget.isVisible():
                                ra_tool.toggle_results_manager.run()  # also does some initialisation
                            if os.path.exists(waterdepth_path):
                                # we only download non-temporal rasters, so always pick the first band
                                waterdepth_layer = QgsRasterLayer(
                                    waterdepth_path, "max_waterdepth.tif", "gdal"
                                )
                                waterdepth_layer.loadNamedStyle(
                                    str(STYLE_DIR / "water_depth.qml")
                                )
                                if hasattr(waterdepth_layer.renderer(), "setBand"):
                                    waterdepth_layer.renderer().setBand(1)
                                waterdepth_layer.setName("max_waterdepth.tif")
                                QgsProject.instance().addMapLayer(waterdepth_layer)

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
        self.file_opened.emit(file)
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
        confirm = QMessageBox.question(
            self.parent(),
            "Confirm Delete",
            f"Are you sure you want to remove {file['id']}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if confirm == QMessageBox.StandardButton.No:
            return
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
            self.rename_aborted.emit()
            return
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
            msg = f"Unable to rename directory {Path(source_path).name} to {Path(target_path).name}"
        else:
            existing_file = get_tenant_project_file(
                project["id"], {"path": target_path}
            )
            if existing_file:
                QMessageBox.warning(
                    self.parent(), "Warning", f"File {new_name} already exists."
                )
                return
            success = move_file(
                project["id"],
                params={"source_path": source_path, "destination_path": target_path},
            )
            msg = f"Unable to rename file {Path(source_path).name} to {Path(target_path).name}"
        if success:
            self.rename_finished.emit(new_name)
        else:
            self.communication.show_warn(msg)
            self.rename_aborted.emit()

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

    @pyqtSlot(dict, dict)
    @pyqtSlot(dict, dict, int)
    def create_schematisation_revision_3di_model(self, project, file, revision_id=None):
        # Retrieve schematisation info
        schematisation = get_threedi_schematisation(
            self.communication, file["descriptor_id"]
        )
        if not revision_id:
            revision_id = schematisation["latest_revision"]["id"]
        self.start_model_tracker_process(
            project, schematisation["schematisation"], revision_id
        )

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
        allowed_org_ids = get_threedi_organisations(self.communication)
        organisations = {
            org.unique_id: org for org in tc.fetch_organisations(allowed_org_ids)
        }

        if len(organisations) == 0:
            self.communication.show_warn(
                "No organisation available for this simulation"
            )
            self.simulation_started_failed.emit()
            return

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

        # Retrieve models
        current_models = tc.fetch_schematisation_revision_3di_models(
            schematisation["schematisation"]["id"], revision["id"]
        )
        # Retrieve the active model (Disabled=False)
        current_model = next(
            (x for x in current_models if (not x.disabled) and x.is_valid), None
        )
        if not current_model:
            self.communication.show_warn(
                "No enabled valid model for this schematisation revision"
            )
            self.simulation_started_failed.emit()

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
                partial(self.start_simulation_tracker_process, project, file)
            )
            simulation_wizard.simulation_created_failed.connect(
                self.simulation_started_failed
            )

            if simulation_wizard.exec() == QDialog.Rejected:
                self.simulation_cancelled.emit()

    def start_model_tracker_process(
        self,
        project,
        schematisation,
        revision_id: int,
        inherit_from_previous_revision: bool = True,
    ):
        track_process = get_process_id_for_tag(self.communication, "model_tracker")
        if track_process is None:
            self.communication.log_err("No model tracker available")
            return
        params = {
            "project_id": project["id"],
            "inputs": {
                "schematisation_id": schematisation["id"],
                "revision_id": revision_id,
                "inherit_from_previous_model": True,
                "inherit_from_previous_revision": inherit_from_previous_revision,
            },
            "name": f"model_tracker_{schematisation['name']}_rev{revision_id}",
        }
        _ = start_tenant_process(self.communication, track_process, params)
        self.model_created.emit()

    def start_simulation_tracker_process(self, project, file, simulations):
        # Find the simulation tracker processes
        track_process = get_process_id_for_tag(self.communication, "simulation_tracker")

        if track_process is None:
            self.communication.log_err("No simulation tracker available")
            return

        # Store the result in the same folder as the file
        output_file_path = file["id"].rpartition("/")[0] + file["id"].rpartition("/")[1]

        for sim in simulations:
            params = {
                "project_id": project["id"],
                "inputs": {"simulation_id": sim.simulation.id_to_start},
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
        assert descriptor["data_type"] == "scenario"
        meta = descriptor.get("meta", {})
        if not meta.get("id"):
            self.communication.show_warn("Post-processing results not yet available")
            self.download_results_cancelled.emit()
            return
        if descriptor.get("status", {}).get("id") not in ["completed", "processing"]:
            self.communication.show_warn(f"Post-processing results cannot be retrieved")
            self.download_results_cancelled.emit()
            return

        tc = ThreediCalls(get_threedi_api())
        schematisation_name = meta["schematisation"]["name"]
        schematisation_id = meta["schematisation"]["id"]
        revision_number = meta["schematisation"]["version"]
        simulation_name = meta["simulation"]["name"]
        # Simulation name is only set after post-processing is fully finished
        if not simulation_name:
            if meta["simulation"].get("id"):
                simulation_name = tc.fetch_simulation(meta["simulation"].get("id")).name
            else:
                self.communication.show_warn(
                    "Post-processing results not yet available"
                )
                self.download_results_cancelled.emit()
                return
        # Revision number is only set after post-processing is fully finished
        if not revision_number:
            if meta["schematisation"].get("revision_id"):
                revision_id = meta["schematisation"]["revision_id"]
                revision_number = tc.fetch_schematisation_revision(
                    schematisation_id, revision_id
                ).number
            else:
                self.communication.show_warn(
                    "Post-processing results not yet available"
                )
                self.download_results_cancelled.emit()
                return
        # Determine local target folder for simulation
        target_folder = get_threedi_schematisation_simulation_results_folder(
            QgsSettings().value("threedi/working_dir"),
            schematisation_id,
            schematisation_name.replace("/", "-").replace("\\", "-"),
            revision_number,
            simulation_name.replace("/", "-").replace("\\", "-"),
        )
        os.makedirs(target_folder, exist_ok=True)
        link = next(
            (
                link
                for link in descriptor["links"]
                if link["rel"] == "lizard-scenario-results"
            ),
            None,
        )
        if link:
            grid = deepcopy(descriptor["meta"]["grid"])
            results = get_tenant_file_descriptor_view(
                file["descriptor_id"], "lizard-scenario-results"
            )
            crs = grid["crs"]
        else:
            results = {}
            # grid and crs are not used when results is empty
            grid = {}
            crs = "EPSG:28992"
        pixel_size = grid.get("x", {}).get("cell_size", 1)
        result_browser = ResultBrowser(None, results, crs, pixel_size)
        if result_browser.exec() == QDialog.DialogCode.Accepted:
            result_ids, nodata, pixelsize, crs = result_browser.get_selected_results()
            if len(result_ids) == 0 and not result_browser.get_download_raw_result():
                self.download_results_cancelled.emit()
                return
            filtered_result_ids = []
            for result_id in result_ids:
                result = [r for r in results if r.get("id") == result_id][0]
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
                        self.download_results_cancelled.emit()
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
                download_raw=result_browser.get_download_raw_result(),
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
            return
        else:
            self.download_results_cancelled.emit()
            return

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
            "All supported files (*.tif *.tiff *.gpkg *.sqlite *.geojson *.shp);;"
            "Rasters (*.tif *.tiff);;"
            "Vector files (*.gpkg *.sqlite *.geojson *.shp)",
        )
        if not local_paths:
            self.loading_cancelled.emit()
            return

        QSettings().setValue(
            f"{RANA_SETTINGS_ENTRY}/last_upload_folder",
            str(Path(local_paths[0]).parent),
        )

        # Check whether something needs to be converted
        try:
            converted_paths = []
            convert_all_files = False
            for local_path in local_paths:
                _, ext = os.path.splitext(local_path)
                if ext == ".shp":
                    if convert_all_files:
                        converted_paths.append(
                            convert_vectorfile_to_geopackage(local_path)
                        )
                    else:
                        file_convert = UICommunication.custom_ask(
                            self.parent(),
                            "Shapefile not supported",
                            f"Rana does not natively support shapefiles, would you like to convert it before uploading or cancel?",
                            "Cancel",
                            "Convert this file only",
                            "Convert all shapefiles",
                        )
                        if file_convert == "Cancel":
                            self.loading_cancelled.emit()
                            return
                        elif file_convert == "Convert all shapefiles":
                            convert_all_files = True
                            converted_paths.append(
                                convert_vectorfile_to_geopackage(local_path)
                            )
                        else:
                            converted_paths.append(
                                convert_vectorfile_to_geopackage(local_path)
                            )
                else:
                    # no conversion necessary
                    converted_paths.append(local_path)

        except Exception as e:
            self.communication.bar_error(f"Error converting shapefiles: {str(e)}")
            self.file_upload_failed.emit(str(e))
            return

        local_paths = converted_paths.copy()

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
        sender.deleteLater()
        self.file_upload_finished.emit()

    def on_new_file_upload_finished(self, online_path: str, project):
        self.on_file_upload_finished()
        if online_path and self.communication.ask(
            self.parent(), "Load", "Would you like to load the uploaded file from Rana?"
        ):
            file = get_tenant_project_file(project["id"], {"path": online_path})
            self.initialize_file_download_worker(project, file)
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

    @pyqtSlot(dict, dict)
    def save_raster_style(self, project, file):
        """Start the worker for saving raster styling files"""
        self.communication.progress_bar(
            "Generating and saving raster styling files...", clear_msg_bar=True
        )
        self.raster_style_worker = RasterStyleWorker(
            project,
            file,
        )
        self.raster_style_worker.finished.connect(self.on_raster_style_finished)
        self.raster_style_worker.failed.connect(self.on_raster_style_failed)
        self.raster_style_worker.warning.connect(self.communication.show_warn)
        self.raster_style_worker.start()

    def on_vector_style_finished(self, msg: str):
        self.communication.clear_message_bar()
        self.communication.show_info(msg)
        self.vector_style_finished.emit()

    def on_vector_style_failed(self, msg: str):
        self.communication.clear_message_bar()
        self.communication.show_error(msg)
        self.vector_style_failed.emit(msg)

    def on_raster_style_finished(self, msg: str):
        self.communication.clear_message_bar()
        self.communication.show_info(msg)
        self.raster_style_finished.emit()

    def on_raster_style_failed(self, msg: str):
        self.communication.clear_message_bar()
        self.communication.show_error(msg)
        self.raster_style_failed.emit(msg)

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

    @pyqtSlot(dict, dict)
    def upload_new_schematisation_to_rana(self, project, selected_item):
        assert selected_item["type"] == "directory"
        rana_path = selected_item["id"]
        threedi_api = get_threedi_api()
        tenant_details = get_tenant_details(self.communication)
        if not tenant_details:
            return
        tc = ThreediCalls(threedi_api)
        allowed_org_ids = get_threedi_organisations(self.communication)
        organisations = {
            org.unique_id: org for org in tc.fetch_organisations(allowed_org_ids)
        }

        if len(organisations) == 0:
            self.communication.show_error(
                "No 3Di organisations available for this Rana organisation; please make sure your API endpoint is configured."
            )
            self.schematisation_upload_failed.emit()
            return

        work_dir = QSettings().value("threedi/working_dir", "")
        new_schematisation_wizard = NewSchematisationWizard(
            threedi_api, work_dir, self.communication, organisations
        )
        response = new_schematisation_wizard.exec()
        if response != QDialog.DialogCode.Accepted:
            self.schematisation_upload_cancelled.emit()
            return

        local_schematisation = new_schematisation_wizard.new_local_schematisation
        new_schematisation = new_schematisation_wizard.new_schematisation
        if new_schematisation is None or local_schematisation is None:
            self.communication.bar_error("Schematisation creation failed")
            self.schematisation_upload_failed.emit()
            return

        db_path = local_schematisation.schematisation_db_filepath
        if not db_path or not local_schematisation.wip_revision:
            self.communication.bar_warning(
                "Revision creation failed; please create one manually later in the Rana browser"
            )
        else:
            # Search GeoPackage database tables for attributes with file paths.
            paths = new_schematisation_wizard.get_paths_from_geopackage(db_path)

            self.save_initial_revision(
                project, new_schematisation, local_schematisation, paths
            )

        if rana_path:
            file_path = rana_path + new_schematisation.name
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
                f"Rana schematisation {new_schematisation.name} added to Rana project"
            )
            if rana_path:
                message += f" in directory {rana_path}"
            self.communication.bar_info(message)
        else:
            self.schematisation_upload_failed.emit()
            self.communication.bar_error(
                f"Could not add Rana schematisation {new_schematisation.name} to Rana project {project['name']}!"
            )
            return
        self.schematisation_upload_finished.emit()
        load_local_schematisation(
            communication=self.communication,
            local_schematisation=local_schematisation.wip_revision,
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
        self.organisations = {org.unique_id: org for org in tc.fetch_organisations()}
        organisation = self.organisations.get(schematisation.owner)

        local_schematisations = list_local_schematisations(
            hcc_working_dir(), use_config_for_revisions=False
        )

        # Check whether we have this schematisation locally
        local_schematisation = local_schematisations.get(schematisation.id)
        if local_schematisation is None:
            self.communication.show_warn(
                "Current schematisation not yet stored locally, please download a revision first."
            )
            self.schematisation_upload_cancelled.emit()
            return
        if local_schematisation.wip_revision is None:
            # Let the user select a local revision
            load_dialog = SchematisationLoad(
                hcc_working_dir(),
                self.communication,
                local_schematisation,
                self.parent(),
            )
            if load_dialog.exec() == QDialog.DialogCode.Accepted:
                # Upload that revision as new revision
                local_schematisation = load_dialog.selected_local_schematisation
            else:
                self.schematisation_upload_cancelled.emit()
                return

        schematisation_filepath = local_schematisation.schematisation_db_filepath

        schema_gpkg_loaded = is_loaded_in_schematisation_editor(schematisation_filepath)
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
                self.schematisation_upload_cancelled.emit()
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
            upload_worker.signals.create_model_requested.connect(
                lambda revision_id,
                inherit_from_previous_revision: self.start_model_tracker_process(
                    project,
                    schematisation.to_dict(),
                    revision_id,
                    inherit_from_previous_revision,
                )
            )
            upload_worker.signals.thread_finished.connect(
                self.on_schematisation_upload_finished
            )
            upload_worker.signals.upload_failed.connect(
                self.schematisation_upload_failed
            )
            upload_worker.signals.upload_progress.connect(
                self.on_schematisation_upload_progress
            )

            self.upload_thread_pool.start(upload_worker)
            self.revision_saved.emit()
        else:
            # User presses cancel
            self.schematisation_upload_cancelled.emit()

    def on_schematisation_upload_finished(self):
        self.communication.clear_message_bar()
        self.schematisation_upload_finished.emit()

    def on_schematisation_upload_progress(
        self, task_name, task_progress, total_progress, progress_per_task
    ):
        self.communication.progress_bar(
            f"Uploading revision: ({task_name.lower()})",
            0,
            100,
            int(total_progress + ((task_progress / 100.0) * progress_per_task)),
            clear_msg_bar=True,
        )

    @pyqtSlot(dict, dict, dict, dict, dict)
    def save_initial_revision(
        self, project, schematisation, local_schematisation, raster_paths
    ):
        raster_dir = local_schematisation.wip_revision.raster_dir

        selected_files = {
            "geopackage": {
                "filepath": local_schematisation.schematisation_db_filepath,
                "make_action": True,
                "remote_raster": None,
                "status": UploadFileStatus.NEW,
                "type": UploadFileType.DB,
            }
        }

        missing_rasters = []
        for _, raster_paths_info in raster_paths.items():
            for raster_name, raster_rel_path in raster_paths_info.items():
                if not raster_rel_path:
                    continue
                raster_full_path = os.path.join(raster_dir, raster_rel_path)
                if not os.path.exists(raster_full_path):
                    missing_rasters.append((raster_name, raster_rel_path))

                selected_files[raster_name] = {
                    "filepath": raster_full_path,
                    "make_action": True,
                    "remote_raster": None,
                    "status": UploadFileStatus.NEW,
                    "type": UploadFileType.RASTER,
                }

        if missing_rasters:
            missing_rasters_string = "\n".join(
                f"{rname}: {rpath}" for rname, rpath in missing_rasters
            )
            warn_msg = f"Warning: the following raster files where not found:\n{missing_rasters_string}"
            self.communication.show_warn(warn_msg)
            self.schematisation_upload_failed.emit()
            return

        upload_template = {
            "schematisation": schematisation,
            "latest_revision": SchematisationRevision(number=0),
            "selected_files": selected_files,
            "commit_message": "Initial commit",
            "create_revision": True,
            "make_3di_model": True,
            "cb_inherit_templates": False,
        }

        threedi_api = get_threedi_api()

        upload_worker = SchematisationUploadProgressWorker(
            threedi_api,
            local_schematisation,
            upload_template,
        )
        upload_worker.signals.create_model_requested.connect(
            lambda revision_id: self.start_model_tracker_process(
                project,
                schematisation.to_dict(),
                revision_id,
            )
        )

        upload_worker.signals.thread_finished.connect(
            self.schematisation_upload_finished
        )
        upload_worker.signals.upload_failed.connect(self.schematisation_upload_failed)
        upload_worker.signals.upload_progress.connect(
            self.on_schematisation_upload_progress
        )

        self.upload_thread_pool.start(upload_worker)
        self.revision_saved.emit()

    @pyqtSlot(str)
    def update_project(self, project_id: str):
        self.persistent_scheduler.clear()
        self.start_project_job_monitoring(project_id)
        self.start_publication_monitoring(project_id)

    def start_project_job_monitoring(self, project_id):
        worker = ProjectJobMonitorWorker(project_id=project_id, parent=self)
        worker.jobs_added.connect(self.project_jobs_added)
        worker.job_updated.connect(self.project_job_updated)
        worker.failed.connect(self.communication.show_warn)
        self.persistent_scheduler.add_task(worker, 1)

    def start_publication_monitoring(self, project_id):
        worker = PublicationMonitorWorker(project_id=project_id, parent=self)
        worker.publications_added.connect(self.project_publications_added)
        worker.publication_updated.connect(self.project_publication_updated)
        # TODO: consider if this should be a warning
        worker.failed.connect(self.communication.log_warn)
        self.persistent_scheduler.add_task(worker, 60)

    @pyqtSlot()
    def update_project_publications(self):
        self.persistent_scheduler.run_task_by_type(PublicationMonitorWorker)

    @pyqtSlot()
    def run_all_persistent_tasks(self):
        self.persistent_scheduler.run_all_tasks()

    def initialize_avatar_worker(self, users):
        self.avatar_worker = AvatarWorker(self.communication, users)
        self.avatar_worker.signals.avatar_ready.connect(self.avatar_updated)

    def update_avatars(self, users):
        self.initialize_avatar_worker(users)
        self.avatar_runner_pool.start(self.avatar_worker)

    @pyqtSlot(int)
    def cancel_simulation(self, simulation_pk):
        confirm_cancel = QMessageBox.warning(
            None,
            "Cancel Simulation",
            "Are you sure you want to cancel the simulation?",
            QMessageBox.StandardButton.Yes,
            QMessageBox.StandardButton.No,
        )
        if confirm_cancel == QMessageBox.StandardButton.Yes:
            tc = ThreediCalls(get_threedi_api())
            tc.fetch_simulation_status(simulation_pk)
            try:
                tc.create_simulation_action(simulation_pk, name="shutdown")
            except ApiException as e:
                self.communication.show_error(f"Could not cancel simulation")
