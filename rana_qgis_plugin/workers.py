import io
import os
import shutil
import zipfile
from functools import cached_property
from pathlib import Path
from time import sleep
from typing import List, Optional

import requests
from qgis.core import Qgis, QgsMessageLog
from qgis.PyQt.QtCore import (
    QObject,
    QRunnable,
    QSettings,
    QThread,
    pyqtSignal,
    pyqtSlot,
)
from qgis.PyQt.QtGui import QPixmap
from threedi_mi_utils import bypass_max_path_limit

from rana_qgis_plugin.widgets.utils_avatars import get_avatar

from .utils import (
    build_vrt,
    get_local_file_path,
    get_publication_layer_path,
    split_scenario_extent,
)
from .utils_api import (
    finish_file_upload,
    get_publication_style,
    get_raster_file_link,
    get_raster_style_file,
    get_tenant_file_descriptor,
    get_tenant_file_descriptor_view,
    get_tenant_file_url,
    get_tenant_project_file,
    get_vector_style_file,
    map_result_to_file_name,
    request_raster_generate,
    start_file_upload,
)

CHUNK_SIZE = 1024 * 1024  # 1 MB


class FileDownloadWorkerSignals(QObject):
    progress = pyqtSignal(
        int, str
    )  # Progress signal: emits progress percentage and additional info
    finished = pyqtSignal(
        dict, dict, str
    )  # Finished signal: emits project, file, and local file path
    failed = pyqtSignal(str)  # Failed signal: emits error messages
    all_finished = pyqtSignal()


class FileDownloadBase:
    """Base class that handles the common download logic."""

    # Note: The signals are removed from FileDownloadBase as they will now exist in the worker classes.
    def __init__(self, project, file):
        self.project = project
        self.file = file

    def get_local_file_path(self) -> tuple[str, str]:
        raise NotImplementedError

    def get_style_zip(self):
        raise NotImplementedError

    def download_file(self, signals: FileDownloadWorkerSignals, download_file=True):
        """Handles the core logic for downloading a file and emits signals from the worker."""
        path = self.file["id"]
        descriptor_id = self.file["descriptor_id"]
        url = get_tenant_file_url(self.project["id"], {"path": path})
        local_dir_structure, local_file_path = self.get_local_file_path()
        os.makedirs(local_dir_structure, exist_ok=True)
        try:
            if download_file:
                with requests.get(url, stream=True) as response:
                    response.raise_for_status()
                    total_size = int(response.headers.get("content-length", 0))
                    downloaded_size = 0
                    previous_progress = -1
                    with open(local_file_path, "wb") as local_file:
                        for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                            local_file.write(chunk)
                            downloaded_size += len(chunk)
                            progress = int((downloaded_size / total_size) * 100)
                            if progress > previous_progress:
                                signals.progress.emit(progress, local_file_path)
                                previous_progress = progress
            # Handle QML files for vector and raster data
            self._handle_qml_extraction(descriptor_id, local_dir_structure)
            # Emit finished signal from the worker
            signals.finished.emit(self.project, self.file, local_file_path)
        except requests.exceptions.RequestException as e:
            signals.failed.emit(f"Failed to download file: {str(e)}")
        except Exception as e:
            signals.failed.emit(f"An error occurred: {str(e)}")

    def _handle_qml_extraction(self, descriptor_id, local_dir_structure):
        """Handles the extraction of QML zip file if required."""
        if self.file["data_type"] in ["vector", "raster"]:
            qml_zip_content = self.get_style_zip()
            if qml_zip_content:
                stream = io.BytesIO(qml_zip_content)
                if zipfile.is_zipfile(stream):
                    with zipfile.ZipFile(stream, "r") as zip_file:
                        zip_file.extractall(local_dir_structure)


class FileDownloadForFileTree(FileDownloadBase):
    def get_local_file_path(self) -> str:
        return get_local_file_path(self.project["slug"], self.file["id"])

    def get_style_zip(self):
        if self.file["data_type"] == "raster":
            return get_raster_style_file(self.file["descriptor_id"], "qml.zip")
        else:
            return get_vector_style_file(self.file["descriptor_id"], "qml.zip")


class FileDownloadForPublicationTree(FileDownloadBase):
    def __init__(
        self,
        project: dict,
        file: dict,
        publication_id: str,
        publication_tree: list[str],
        publication_version: int,
        style_id: Optional[str] = None,
        layer_in_file: Optional[str] = None,
    ):
        super().__init__(project, file)
        self.publication_tree = publication_tree
        self.publication_id = publication_id
        self.publication_version = publication_version
        self.layer_in_file = layer_in_file
        self.style_id = style_id

    def get_local_file_path(self) -> tuple[str, str]:
        return get_publication_layer_path(
            self.project["slug"], self.file["id"], self.publication_tree
        )

    def get_style_zip(self):
        if self.style_id and self.file["data_type"] in ["raster", "vector"]:
            style_zip = get_publication_style(
                self.publication_id,
                self.style_id,
                self.publication_version,
                "qml.zip",
            )
            return style_zip


class SingleFileDownloadWorker(QThread):
    """Worker thread for downloading a single file."""

    def __init__(self, downloader: FileDownloadBase):
        super().__init__()
        self.signals = FileDownloadWorkerSignals()
        self.downloader = downloader

    @pyqtSlot()
    def run(self):
        self.downloader.download_file(self.signals)


class BatchFileDownloadWorker(QThread):
    """Worker thread for downloading multiple files, one after the other."""

    def __init__(self, downloaders: list[FileDownloadBase]):
        super().__init__()
        self.signals = FileDownloadWorkerSignals()
        self.downloaders = downloaders
        self.downloaded_files = {str: str}

    @cached_property
    def unique_file_ids(self):
        return set([downloader.file["id"] for downloader in self.downloaders])

    @property
    def nof_files(self) -> int:
        """Count number of unique files"""
        return len(self.unique_file_ids)

    def handle_existing(self, downloader) -> bool:
        """Check if a file was already downloaded by this worker. If so, just copy the file to the required destination"""
        if downloader.file["id"] in self.downloaded_files:
            _, download_path = downloader.get_local_file_path()
            file_location = self.downloaded_files[downloader.file["id"]]
            # make sure the file didn't disappear somehow
            if file_location == download_path:
                return True
            if Path(file_location).exists():
                try:
                    Path(download_path).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(file_location, download_path)
                    return True
                except (FileNotFoundError, PermissionError, OSError) as e:
                    # Don't raise for reasonable exceptions, just return False to redownload
                    return False
        else:
            return False

    @pyqtSlot()
    def run(self):
        # Find the first downloader for each unique file id, download the file and remove the downloader
        for file_id in self.unique_file_ids:
            downloader = next(
                downloader
                for downloader in self.downloaders
                if downloader.file["id"] == file_id
            )
            downloader.download_file(self.signals)
            download_path = downloader.get_local_file_path()
            self.downloaded_files[downloader.file["id"]] = download_path
            self.downloaders.remove(downloader)
        # Iterate over the remaining downloaders and copy the existing file
        for downloader in self.downloaders:
            # copy existing, and if redownload if that was unsuccessful
            download_file = not self.handle_existing(downloader)
            downloader.download_file(self.signals, download_file)
        self.signals.all_finished.emit()


class FileUploadWorker(QThread):
    """Worker thread for uploading new (non-rana) files."""

    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)
    conflict = pyqtSignal()
    failed = pyqtSignal(str)
    warning = pyqtSignal(str)

    def __init__(self, project: dict, local_paths: list[Path], online_dir: str):
        super().__init__()
        self.project = project
        self.local_paths = local_paths
        self.online_dir = online_dir

    def handle_file_conflict(self, online_path):
        server_file = get_tenant_project_file(self.project["id"], {"path": online_path})
        if server_file:
            self.failed.emit("File already exist on server.")
            return False
        return True  # Continue to upload

    @pyqtSlot()
    def run(self):
        # For a single file finished is only emitted if upload was successfull
        if len(self.local_paths) == 1:
            success = self.upload_single_file(self.local_paths[0], 0, 100)
            if success:
                self.finished.emit(self.project)
        # For a multi upload we always emit finish
        else:
            progress_per_file = 100 // len(self.local_paths)
            for i, local_path in enumerate(self.local_paths):
                self.upload_single_file(
                    local_path, i * progress_per_file, progress_per_file
                )
            self.finished.emit(self.project)

    def upload_single_file(
        self, local_path: Path, progress_start, progress_step
    ) -> bool:
        online_path = f"{self.online_dir}{local_path.name}"
        # Check if file exists locally before uploading
        if not local_path.exists():
            self.failed.emit(f"File not found: {local_path}")
            return False

        # Handle file conflict
        continue_upload = self.handle_file_conflict(online_path)
        if not continue_upload:
            return False

        # Save file to Rana
        try:
            self.progress.emit(progress_start, "")
            # Step 1: POST request to initiate the upload
            upload_response = start_file_upload(
                self.project["id"], {"path": online_path}
            )
            if not upload_response:
                self.failed.emit("Failed to initiate file upload.")
                return False
            upload_url = upload_response["urls"][0]
            # Step 2: Upload the file to the upload_url
            self.progress.emit(int(0.2 * progress_step + progress_start), "")
            with open(local_path, "rb") as file:
                response = requests.put(upload_url, data=file)
                response.raise_for_status()
            # Step 3: Complete the upload
            self.progress.emit(int(0.8 * progress_step + progress_start), "")
            response = finish_file_upload(
                self.project["id"],
                upload_response,
            )
            if not response:
                self.failed.emit("Failed to complete file upload.")
                return False
            self.progress.emit(progress_start + progress_step, "")
        except Exception as e:
            self.failed.emit(f"Failed to upload file to Rana: {str(e)}")
            return False
        return True


class ExistingFileUploadWorker(FileUploadWorker):
    """Worker thread for uploading files."""

    def __init__(self, project: dict, file: dict):
        local_file = Path(get_local_file_path(project["slug"], file["id"])[1])
        if "/" not in file["id"]:
            online_dir = ""
        else:
            online_dir = file["id"][: file["id"].rindex("/") + 1]
        super().__init__(project, [local_file], online_dir)

        self.file_overwrite = False
        self.last_modified = None
        self.last_modified_key = f"{project['name']}/{file['id']}/last_modified"
        self.finished.connect(self._finish)

    def handle_file_conflict(self, online_path):
        local_last_modified = QSettings().value(self.last_modified_key)
        server_file = get_tenant_project_file(self.project["id"], {"path": online_path})
        if not server_file:
            self.failed.emit(
                "Failed to get file from server. Check if file has been moved or deleted."
            )
            return False
        self.last_modified = server_file["last_modified"]
        if self.last_modified != local_last_modified:
            self.conflict.emit()
            while self.file_overwrite is None:
                self.msleep(100)
            if self.file_overwrite is False:
                self.failed.emit("File upload aborted.")
                return False
        return True  # Continue to upload

    def _finish(self):
        QSettings().setValue(self.last_modified_key, self.last_modified)


class LizardResultDownloadWorker(QThread):
    """Worker thread for downloading files from ."""

    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict, dict, str)
    failed = pyqtSignal(str)

    def __init__(
        self,
        project: dict,
        file: dict,
        result_ids: List[int],
        target_folder: str,
        grid: dict,
        nodata: int,
        pixelsize: float,
        crs: str,
        download_raw: bool,
    ):
        super().__init__()
        self.project = project
        self.file = file
        self.result_ids = result_ids
        self.target_folder = target_folder
        self.grid = grid
        self.nodata = nodata
        self.pixelsize = pixelsize
        self.crs = crs
        self.download_raw = download_raw

    @pyqtSlot()
    def run(self):
        if self.download_raw:
            project_slug = self.project["slug"]
            path = self.file["id"]
            descriptor_id = self.file["descriptor_id"]
            url = get_tenant_file_url(self.project["id"], {"path": path})
            local_dir_structure, local_file_path = get_local_file_path(
                project_slug, path
            )
            os.makedirs(local_dir_structure, exist_ok=True)
            try:
                with requests.get(url, stream=True) as response:
                    response.raise_for_status()
                    total_size = int(response.headers.get("content-length", 0))
                    downloaded_size = 0
                    previous_progress = -1
                    with open(local_file_path, "wb") as file:
                        for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                            file.write(chunk)
                            downloaded_size += len(chunk)
                            progress = int((downloaded_size / total_size) * 100)
                            if progress > previous_progress:
                                self.progress.emit(progress, "Downloading raw data")
                                previous_progress = progress
            except requests.exceptions.RequestException as e:
                self.failed.emit(f"Failed to download file: {str(e)}")
                return
            except Exception as e:
                self.failed.emit(f"An error occurred: {str(e)}")
                return

            # unzip the raw results in the working directory
            with zipfile.ZipFile(local_file_path, "r") as zip_ref:
                zip_ref.extractall(self.target_folder)
                # check if there is a zip containing log files, these need to be extracted as well
                descriptor = get_tenant_file_descriptor(self.file["descriptor_id"])
                try:
                    sim_id = descriptor["meta"]["simulation"]["id"]
                    log_zip_path = os.path.join(
                        self.target_folder, f"log_files_sim_{sim_id}.zip"
                    )
                    if os.path.isfile(log_zip_path):
                        with zipfile.ZipFile(log_zip_path, "r") as log_zip_ref:
                            log_zip_ref.extractall(self.target_folder)
                    else:
                        QgsMessageLog.logMessage(
                            "Subarchive containing log files not present, ignoring.",
                            level=Qgis.MessageLevel.Warning,
                        )
                except KeyError:
                    QgsMessageLog.logMessage(
                        "Subarchive info missing, ignoring.",
                        level=Qgis.MessageLevel.Critical,
                    )

        descriptor_id = self.file["descriptor_id"]
        task_failed = False
        for result_id in self.result_ids:
            # Retrieve URLS from file descriptors (again), presigned url might be expired
            results = get_tenant_file_descriptor_view(
                descriptor_id, "lizard-scenario-results"
            )
            result = [r for r in results if r["id"] == result_id][0]
            file_name = map_result_to_file_name(result)
            # if raster can be downloaded directly from rana
            if result["attachment_url"]:
                target_file = bypass_max_path_limit(
                    os.path.join(self.target_folder, file_name)
                )
                try:
                    with requests.get(
                        result["attachment_url"], stream=True
                    ) as response:
                        response.raise_for_status()
                        total_size = int(response.headers.get("content-length", 0))
                        downloaded_size = 0
                        previous_progress = -1
                        with open(target_file, "wb") as file:
                            for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                                file.write(chunk)
                                downloaded_size += len(chunk)
                                progress = int((downloaded_size / total_size) * 100)
                                if progress > previous_progress:
                                    self.progress.emit(progress, file_name)
                                    previous_progress = progress

                except requests.exceptions.RequestException as e:
                    self.failed.emit(f"Failed to download file: {str(e)}")
                    task_failed = True
                    break
                except Exception as e:
                    self.failed.emit(f"An error occurred: {str(e)}")
                    task_failed = True
                    break
            # if raster first needs to be generated
            else:
                previous_progress = -1
                spatial_bounds = split_scenario_extent(
                    grid=self.grid, resolution=self.pixelsize, max_pixel_count=1 * 10**8
                )
                # start generate task for each tile of the raster to be downloaded
                bboxes, width, height = spatial_bounds
                raster_tasks = []
                counter = 0
                for x1, y1, x2, y2 in bboxes:
                    bbox = f"{x1},{y1},{x2},{y2}"
                    payload = {
                        "width": width,
                        "height": height,
                        "bbox": bbox,
                        "projection": self.crs,
                        "format": "geotiff",
                        "async": "true",
                    }
                    if self.nodata is not None:
                        payload["nodata"] = self.nodata
                    r = request_raster_generate(
                        descriptor_id=descriptor_id,
                        raster_id=result["raster_id"],
                        payload=payload,
                    )
                    raster_tasks.append(r)
                    counter += 1
                    progress = int((counter / len(bboxes)) * 10)
                    if progress > previous_progress:
                        self.progress.emit(progress, file_name)
                        previous_progress = progress

                # multi-tile raster download
                if len(raster_tasks) > 1:

                    def download_tile(file_link, target_file):
                        with requests.get(file_link, stream=True) as response:
                            response.raise_for_status()
                            total_size = int(response.headers.get("content-length", 0))
                            with open(target_file, "wb") as file:
                                for chunk in response.iter_content(
                                    chunk_size=CHUNK_SIZE
                                ):
                                    file.write(chunk)

                    rasters = {
                        raster_task_id: {
                            "downloaded": False,
                            "filepath": bypass_max_path_limit(
                                os.path.join(
                                    self.target_folder,
                                    f"{file_name}{task_number:02d}.tif",
                                )
                            ),
                        }
                        for task_number, raster_task_id in enumerate(raster_tasks)
                    }
                    task_counter = 0

                    while (
                        False in [task["downloaded"] for task in rasters.values()]
                        and not task_failed
                    ):
                        # wait between each repoll of task statuses
                        sleep(5)
                        for raster_task_id in rasters.keys():
                            # poll all raster generate tasks to check if any is ready to download
                            if not rasters[raster_task_id]["downloaded"]:
                                try:
                                    file_link = get_raster_file_link(
                                        descriptor_id=descriptor_id,
                                        task_id=raster_task_id,
                                    )
                                    if file_link:
                                        download_tile(
                                            file_link,
                                            rasters[raster_task_id]["filepath"],
                                        )
                                        rasters[raster_task_id]["downloaded"] = True

                                        task_counter += 1
                                        # reserve last 10% of progress for raster merging
                                        progress = int(
                                            10 + (task_counter / len(raster_tasks)) * 80
                                        )
                                        if progress > previous_progress:
                                            self.progress.emit(progress, file_name)
                                        previous_progress = progress
                                except requests.exceptions.RequestException as e:
                                    self.failed.emit(
                                        f"Failed to download file: {str(e)}"
                                    )
                                    task_failed = True
                                    break
                                except Exception as e:
                                    self.failed.emit(f"An error occurred: {str(e)}")
                                    task_failed = True
                                    break
                    if not task_failed:
                        raster_filepaths = [
                            item["filepath"] for item in rasters.values()
                        ]
                        raster_filepaths.sort()
                        first_raster_filepath = raster_filepaths[0]
                        vrt_filepath = first_raster_filepath.replace("_01", "").replace(
                            ".tif", ".vrt"
                        )

                        vrt_options = {
                            "resolution": "average",
                            "resampleAlg": "nearest",
                            "srcNodata": self.nodata,
                        }
                        build_vrt(vrt_filepath, raster_filepaths, **vrt_options)
                        self.progress.emit(100, file_name)
                # single-tile raster download
                else:
                    target_file = bypass_max_path_limit(
                        os.path.join(self.target_folder, (file_name + ".tif"))
                    )
                    file_link = False
                    while not (file_link or task_failed):
                        sleep(5)
                        try:
                            file_link = get_raster_file_link(
                                descriptor_id=descriptor_id, task_id=raster_tasks[0]
                            )
                            if not file_link:
                                continue

                            with requests.get(file_link, stream=True) as response:
                                response.raise_for_status()
                                total_size = int(
                                    response.headers.get("content-length", 0)
                                )
                                downloaded_size = 0
                                with open(target_file, "wb") as file:
                                    for chunk in response.iter_content(
                                        chunk_size=CHUNK_SIZE
                                    ):
                                        file.write(chunk)
                                        downloaded_size += len(chunk)
                                        progress = int(
                                            10 + (downloaded_size / total_size) * 90
                                        )
                                        if progress > previous_progress:
                                            self.progress.emit(progress, file_name)
                                            previous_progress = progress

                        except requests.exceptions.RequestException as e:
                            self.failed.emit(f"Failed to download file: {str(e)}")
                            task_failed = True
                        except Exception as e:
                            self.failed.emit(f"An error occurred: {str(e)}")
                            task_failed = True

        if not task_failed:
            self.finished.emit(self.project, self.file, self.target_folder)


class ProjectJobMonitorWorker(QThread):
    failed = pyqtSignal(str)
    jobs_added = pyqtSignal(list)
    job_updated = pyqtSignal(dict)

    def __init__(self, project_id, parent=None):
        super().__init__(parent)
        self.active_jobs = {}
        self.project_id = project_id
        self._stop_flag = False

    def run(self):
        # initialize active jobs
        self.update_jobs()
        while not self._stop_flag:
            self.update_jobs()
            # Process contains a single api call, so every second should be fine
            QThread.sleep(10)

    def stop(self):
        """Gracefully stop the worker"""
        self._stop_flag = True
        self.wait()

    def update_jobs(self):
        response = get_project_jobs(self.project_id)
        if not response:
            return
        current_jobs = response["items"]
        new_jobs = {
            job["id"]: job for job in current_jobs if job["id"] not in self.active_jobs
        }
        self.jobs_added.emit(list(new_jobs.values()))
        self.active_jobs.update(new_jobs)
        for job in current_jobs:
            if job["id"] in new_jobs:
                # new job cannot be updated
                continue
            if (
                job["state"] != self.active_jobs[job["id"]]["state"]
                or job["process"] != self.active_jobs[job["id"]]["process"]
            ):
                self.job_updated.emit(job)
                self.active_jobs[job["id"]] = job


# We need a separate signals class since QRunnable cannot have signals
class AvatarWorkerSignals(QObject):
    finished = pyqtSignal()
    avatar_ready = pyqtSignal(str, "QPixmap")


class AvatarWorker(QRunnable):
    def __init__(self, communication, users: list[dict]):
        super().__init__()
        self.communication = communication
        self.users = users
        self.signals = AvatarWorkerSignals()

    def run(self):
        for user in self.users:
            new_avatar = get_avatar(
                user, self.communication, create_from_initials=False
            )
            if new_avatar:
                self.signals.avatar_ready.emit(user["id"], new_avatar)
        self.signals.finished.emit()
