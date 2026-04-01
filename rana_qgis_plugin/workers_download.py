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
    QThread,
    pyqtSignal,
    pyqtSlot,
)
from threedi_mi_utils import bypass_max_path_limit

from rana_qgis_plugin.utils import (
    build_vrt,
    get_local_dir_structure,
    get_local_file_path,
    get_local_publication_dir_structure,
    get_local_publication_file_path,
    split_scenario_extent,
)
from rana_qgis_plugin.utils_api import (
    get_publication_style,
    get_raster_file_link,
    get_raster_style_file,
    get_tenant_file_descriptor,
    get_tenant_file_descriptor_view,
    get_tenant_file_url,
    get_vector_style_file,
    map_result_to_file_name,
    request_raster_generate,
)
from rana_qgis_plugin.utils_data import DataType, RanaPublicationFileData
from rana_qgis_plugin.utils_scenario import ScenarioInfo

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


class AbstractDownloadContext:
    @property
    def local_dir(self) -> Path:
        raise NotImplementedError

    @property
    def local_file_path(self) -> Path:
        raise NotImplementedError

    def get_style_zip(self):
        raise NotImplementedError


class FileDownloadContext(AbstractDownloadContext):
    def __init__(self, project_slug: str, file_id: str, file_descriptor_id: str):
        self.project_slug = project_slug
        self.file_id = file_id
        self.file_descriptor_id = file_descriptor_id

    @property
    def local_dir(self) -> Path:
        return Path(get_local_dir_structure(self.project_slug, self.file_id))

    @property
    def local_file_path(self) -> Path:
        return Path(get_local_file_path(self.project_slug, self.file_id))

    def get_style_zip(self):
        if self.file["data_type"] == "raster":
            return get_raster_style_file(self.file_descriptor_id, "qml.zip")
        else:
            return get_vector_style_file(self.file_descriptor_id, "qml.zip")


class PublicationFileDownloadContext(AbstractDownloadContext):
    def __init__(
        self,
        project_slug: str,
        publication_version: dict,
        file_data: RanaPublicationFileData,
    ):
        self.project_slug = project_slug
        self.publication_version = publication_version
        self.file_data = file_data

    @property
    def local_dir(self) -> Path:
        return Path(
            get_local_publication_dir_structure(
                self.project_slug,
                self.file_data.file["id"],
                self.file_data.file_tree,
            )
        )

    @property
    def local_file_path(self) -> Path:
        return Path(
            get_local_publication_file_path(
                self.project_slug,
                self.file_data.file["id"],
                self.file_data.file_tree,
            )
        )

    def get_style_zip(self) -> Optional["bytes"]:
        if self.file_data.style_id and self.file_data.data_type in [
            DataType.raster,
            DataType.vector,
        ]:
            if self.file_data.style_id:
                style_zip = get_publication_style(
                    self.publication_version["id"],
                    self.file_data.style_id,
                    self.publication_version["version"],
                    "qml.zip",
                )
            else:
                # fallback to file styling when there is no style set in the publication
                file_context = FileDownloadContext(
                    self.project_slug,
                    file_id=self.file_data.file["id"],
                    file_descriptor_id=self.file_data.file["descriptor_id"],
                )
                style_zip = file_context.get_style_zip()
            return style_zip


class RanaDownloader:
    def __init__(
        self, project: dict, file: dict, download_context: AbstractDownloadContext
    ):
        self.project = project
        self.file = file
        self.download_context = download_context

    @property
    def url(self) -> str:
        raise NotImplementedError

    @property
    def local_dir(self) -> Path:
        return self.download_context.local_dir

    @property
    def local_file_path(self) -> Path:
        return self.download_context.local_file_path

    def download_file(self, signals: FileDownloadWorkerSignals, download_file=True):
        """Handles the core logic for downloading a file and emits signals from the worker."""
        self.local_dir.mkdir(parents=True, exist_ok=True)
        try:
            if download_file:
                with requests.get(self.url, stream=True) as response:
                    response.raise_for_status()
                    total_size = int(response.headers.get("content-length", 0))
                    downloaded_size = 0
                    previous_progress = -1
                    with open(self.local_file_path, "wb") as local_file:
                        for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                            local_file.write(chunk)
                            downloaded_size += len(chunk)
                            progress = int((downloaded_size / total_size) * 100)
                            if progress > previous_progress:
                                signals.progress.emit(
                                    progress, str(self.local_file_path)
                                )
                                previous_progress = progress
            # Handle QML files for vector and raster data
            self._handle_qml_extraction(self.local_dir)
            # Emit finished signal from the worker
            signals.finished.emit(self.project, self.file, str(self.local_file_path))
        except requests.exceptions.RequestException as e:
            signals.failed.emit(f"Failed to download file: {str(e)}")
        except Exception as e:
            # failure to retrieve url will raise a ValueError or FetchError and end up here
            signals.failed.emit(f"An error occurred: {str(e)}")

    def _handle_qml_extraction(self, local_dir_structure: Path):
        """Handles the extraction of QML zip file if required."""
        if self.file["data_type"] in ["vector", "raster"]:
            qml_zip_content = self.download_context.get_style_zip()
            if qml_zip_content:
                stream = io.BytesIO(qml_zip_content)
                if zipfile.is_zipfile(stream):
                    with zipfile.ZipFile(stream, "r") as zip_file:
                        zip_file.extractall(str(local_dir_structure))


class RanaFileDownloader(RanaDownloader):
    @property
    def url(self) -> Optional[str]:
        return get_tenant_file_url(self.project["id"], {"path": self.file["id"]})


class SingleFileDownloadWorker(QThread):
    """Worker thread for downloading a single file."""

    def __init__(self, downloader: RanaDownloader):
        super().__init__()
        self.signals = FileDownloadWorkerSignals()
        self.downloader = downloader

    @pyqtSlot()
    def run(self):
        self.downloader.download_file(self.signals)


class BatchFileDownloadWorker(QThread):
    """Worker thread for downloading multiple files, one after the other."""

    def __init__(self, downloaders: list[RanaDownloader]):
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
            _, download_path = downloader.get_local_file_paths()
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
            download_path = downloader.download_context.local_file_path
            self.downloaded_files[downloader.file["id"]] = download_path
            self.downloaders.remove(downloader)
        # Iterate over the remaining downloaders and copy the existing file
        for downloader in self.downloaders:
            # copy existing, and if redownload if that was unsuccessful
            download_file = not self.handle_existing(downloader)
            downloader.download_file(self.signals, download_file)
        self.signals.all_finished.emit()


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
            local_dir_structure = get_local_dir_structure(project_slug, path)
            local_file_path = get_local_file_path(project_slug, path)
            os.makedirs(local_dir_structure, exist_ok=True)
            try:
                url = get_tenant_file_url(self.project["id"], {"path": path})
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
