import io
import shutil
import tempfile
import warnings
import zipfile
from functools import cached_property
from pathlib import Path
from time import sleep
from typing import Optional

import requests
from qgis.core import QgsSettings
from qgis.PyQt.QtCore import (
    QObject,
    QThread,
    pyqtSignal,
    pyqtSlot,
)
from threedi_mi_utils import bypass_max_path_limit

from rana_qgis_plugin.simulation.threedi_calls import ThreediCalls
from rana_qgis_plugin.utils.api import (
    get_file_descriptor_style,
    get_publication_style,
    get_raster_file_link,
    get_tenant_file_descriptor,
    get_tenant_file_url,
    request_raster_generate,
)
from rana_qgis_plugin.utils.data_models import DataType, RanaPublicationFileData
from rana_qgis_plugin.utils.generic import (
    build_vrt,
    get_local_dir_structure,
    get_local_file_path,
    get_local_publication_dir_structure,
    get_local_publication_file_path,
    get_threedi_api,
    get_threedi_schematisation_simulation_results_folder,
    split_scenario_extent,
)
from rana_qgis_plugin.utils.qgis import rescale_qml_file
from rana_qgis_plugin.utils.scenario import ScenarioInfo

CHUNK_SIZE = 1024 * 1024  # 1 MB


class SchematisationUpgradeError(Exception):
    pass


class SchematisationWithout1DError(Exception):
    pass


class FileDownloadWorkerSignals(QObject):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal()
    failed = pyqtSignal(str)  # Failed signal: emits error messages
    all_finished = pyqtSignal()
    warning = pyqtSignal(str)


class AbstractDownloadContext:
    @property
    def local_dir(self) -> Path:
        raise NotImplementedError

    @property
    def local_file_path(self) -> Path:
        raise NotImplementedError

    def get_style_zip(self):
        raise NotImplementedError


class TempDownloadContext(AbstractDownloadContext):
    def __init__(self, file_name: str):
        self.file_name = file_name

    @cached_property
    def local_dir(self) -> Path:
        target_dir = Path(tempfile.gettempdir()).joinpath("rana_downloads")
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir.joinpath(tempfile.mkdtemp(dir=target_dir))

    @property
    def local_file_path(self) -> Path:
        return self.local_dir.joinpath(self.file_name)


class FileDownloadContext(AbstractDownloadContext):
    def __init__(
        self,
        project_slug: str,
        file_id: str,
        file_descriptor_id: str,
        file_data_type: str,
    ):
        self.project_slug = project_slug
        self.file_id = file_id
        self.file_descriptor_id = file_descriptor_id
        self.file_data_type = file_data_type

    @property
    def local_dir(self) -> Path:
        return Path(get_local_dir_structure(self.project_slug, self.file_id))

    @property
    def local_file_path(self) -> Path:
        return Path(get_local_file_path(self.project_slug, self.file_id))

    def get_style_zip(self):
        return get_file_descriptor_style(self.file_descriptor_id, "qml.zip")


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
        if self.file_data.data_type in [
            DataType.raster,
            DataType.vector,
        ]:
            if self.file_data.style_id:
                style_zip = get_publication_style(
                    self.publication_version["publication_id"],
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
                    file_data_type=self.file_data.data_type.value,
                )
                style_zip = file_context.get_style_zip()
            return style_zip


class ResultsDownloadContext(AbstractDownloadContext):
    """Download context for lizard scenario results (batch downloads).

    Resolves the target folder based on whether a 3Di simulation is linked.
    """

    def __init__(
        self,
        scenario_info: ScenarioInfo,
        project_slug: str,
        file_id: str,
        filename: str = "",
    ):
        self.scenario_info = scenario_info
        self.project_slug = project_slug
        self.file_id = file_id
        self.filename = filename

    @cached_property
    def local_dir(self) -> Path:
        if self.scenario_info.has_3di_simulation:
            return Path(
                get_threedi_schematisation_simulation_results_folder(
                    QgsSettings().value("threedi/working_dir"),
                    self.scenario_info.schematisation_id,
                    self.scenario_info.schematisation_name.replace("/", "-").replace(
                        "\\", "-"
                    ),
                    self.scenario_info.revision_number,
                    self.scenario_info.simulation_name.replace("/", "-").replace(
                        "\\", "-"
                    ),
                    self.scenario_info.simulation_id,
                )
            )
        return Path(get_local_dir_structure(self.project_slug, self.file_id))

    @property
    def local_file_path(self) -> Path:
        return Path(bypass_max_path_limit(str(self.local_dir / self.filename)))


class BaseDownloader:
    def __init__(self, download_context: AbstractDownloadContext):
        self.download_context = download_context

    @property
    def file_id(self) -> str:
        raise NotImplementedError

    @property
    def url(self) -> str:
        raise NotImplementedError

    @property
    def downloaded_file_path(self) -> Path:
        return self.download_context.local_file_path

    def postprocess(self):
        raise NotImplementedError

    @staticmethod
    def download_url(
        url, target_file: Path, progress_signal, progress_min=0, progress_max=100
    ):
        """Download a URL to a file, emitting progress signals."""
        with requests.get(url, stream=True) as response:
            response.raise_for_status()
            target_file.parent.mkdir(parents=True, exist_ok=True)
            total_size = int(response.headers.get("content-length", 0))
            progress_frac = (
                (progress_max - progress_min) / total_size if total_size > 0 else 0
            )
            downloaded_size = 0
            previous_progress = -1
            with open(target_file, "wb") as f:
                for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                    f.write(chunk)
                    downloaded_size += len(chunk)
                    progress = progress_min + int(downloaded_size * progress_frac)
                    if progress > previous_progress:
                        progress_signal.emit(progress, str(target_file))
                        previous_progress = progress

    def download_file(self, signals: FileDownloadWorkerSignals, download_file=True):
        """Handles the core logic for downloading a file and emits signals from the worker."""
        self.download_context.local_dir.mkdir(parents=True, exist_ok=True)
        try:
            if download_file:
                self.download_url(
                    self.url,
                    self.download_context.local_file_path,
                    signals.progress,
                )
            self.postprocess()
            # Emit finished signal from the worker
            signals.finished.emit()
        except requests.exceptions.RequestException as e:
            signals.failed.emit(f"Failed to download file: {str(e)}")
        except SchematisationWithout1DError:
            signals.failed.emit(
                "Cancelled export because exporting a pure 2D schematisation will create a geopackage without vector layers"
            )
        except Exception as e:
            # failure to retrieve url will raise a ValueError or FetchError and end up here
            signals.failed.emit(f"An error occurred: {str(e)}")


class RanaDownloader(BaseDownloader):
    """Base downloader for files stored in a Rana project.

    Provides the download URL (via tenant file API) and file_id.
    Subclasses implement postprocess() for file-type-specific handling.
    """

    def __init__(
        self, project: dict, file: dict, download_context: AbstractDownloadContext
    ):
        super().__init__(download_context)
        self.project = project
        self.file = file

    @property
    def url(self) -> Optional[str]:
        return get_tenant_file_url(self.project["id"], {"path": self.file["id"]})

    @property
    def file_id(self) -> str:
        return self.file["id"]


class RanaFileDownloader(RanaDownloader):
    """Downloads a tenant file and applies QML styling.

    Used for raster and vector files that have associated style data.
    """

    def postprocess(self):
        """Handles the extraction of QML zip file and matching/renaming for rasters."""
        if self.file["data_type"] in ["vector", "raster"]:
            qml_zip_content = self.download_context.get_style_zip()
            if qml_zip_content:
                stream = io.BytesIO(qml_zip_content)
                if zipfile.is_zipfile(stream):
                    with zipfile.ZipFile(stream, "r") as zip_file:
                        zip_file.extractall(str(self.download_context.local_dir))

        # For rasters, handle QML file matching and physical_quantity.qml renaming
        if self.file["data_type"] == "raster":
            self._handle_raster_qml_files()

    def _handle_raster_qml_files(self):
        # Check if physical_quantity.qml exists, if so rename to match downloaded filename
        pq_path = self.download_context.local_dir / "physical_quantity.qml"
        if pq_path.exists():
            new_name = self.download_context.local_file_path.with_suffix(".qml").name
            final_qml_path = self.download_context.local_dir / new_name
            pq_path.replace(final_qml_path)

            # Attempt to rescale the QML to match the actual raster data range
            self._rescale_qml_to_raster_range(final_qml_path)

    def _rescale_qml_to_raster_range(self, qml_path: Path) -> None:
        """Rescale QML file to match actual raster data range from descriptor.

        Gracefully skips rescaling if descriptor or range data is unavailable.
        """
        # Fetch the file descriptor to get the actual data range
        descriptor = get_tenant_file_descriptor(self.file["descriptor_id"])
        if descriptor is None:
            return

        # Extract min/max from descriptor metadata
        meta = descriptor.get("meta") or {}
        range_data = meta.get("range_type") or {}
        new_min = range_data.get("min")
        new_max = range_data.get("max")
        if new_min is None or new_max is None:
            return

        # Attempt to rescale the QML file
        rescale_qml_file(qml_path, float(new_min), float(new_max))


class RanaRawResultsDownloader(RanaDownloader):
    """Downloads and extracts the raw results zip for a scenario file."""

    def __init__(
        self, project: dict, file: dict, download_context: AbstractDownloadContext
    ):
        super().__init__(project, file, download_context)
        self._warning_signal = None

    def download_file(self, signals: FileDownloadWorkerSignals, download_file=True):
        """Store warning signal for use in postprocess, then delegate to parent."""
        self._warning_signal = signals.warning
        super().download_file(signals, download_file)

    def postprocess(self):
        """Extract zip into local_dir, handle nested log zip, remove zip."""
        zip_path = self.download_context.local_file_path
        target_dir = self.download_context.local_dir
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(str(target_dir))
        zip_path.unlink()
        descriptor = get_tenant_file_descriptor(self.file["descriptor_id"])
        try:
            sim_id = descriptor["meta"]["simulation"]["id"]
            log_zip_path = target_dir / f"log_files_sim_{sim_id}.zip"
            if log_zip_path.is_file():
                with zipfile.ZipFile(log_zip_path, "r") as log_zip_ref:
                    log_zip_ref.extractall(str(target_dir))
            else:
                self._warning_signal.emit(
                    "Subarchive containing log files not present, ignoring."
                )
        except KeyError:
            self._warning_signal.emit("Subarchive info missing, ignoring.")


class SchematisationGeopackageDownloader(BaseDownloader):
    def __init__(
        self,
        schematisation_id: int,
        revision: dict,
        download_context: AbstractDownloadContext,
    ):
        super().__init__(download_context)
        self.schematisation_id = schematisation_id
        self.revision = revision
        self._downloaded_file_path: Optional[Path] = None
        self.progress_signal: Optional[pyqtSignal] = None
        self.warning_signal: Optional[pyqtSignal] = None

    @property
    def downloaded_file_path(self) -> Path:
        if not self._downloaded_file_path:
            raise ValueError(
                "Schematisation download path cannot be accessed before download is extracted"
            )
        return self._downloaded_file_path

    @cached_property
    def url(self) -> str:
        threedi_api = get_threedi_api()
        tc = ThreediCalls(threedi_api)
        schematisation_pk = self.schematisation_id
        revision_pk = self.revision["id"]
        return tc.download_schematisation_revision_sqlite(
            schematisation_pk, revision_pk
        ).get_url

    def download_file(self, signals: FileDownloadWorkerSignals, download_file=True):
        self.progress_signal = signals.progress
        self.warning_signal = signals.warning
        super().download_file(signals, download_file)

    def postprocess(self):
        # Extract schematisation from zip
        zip_file = self.download_context.local_file_path
        if zip_file.suffix == ".zip":
            with zipfile.ZipFile(zip_file, "r") as zip_ref:
                zip_ref.extractall(self.download_context.local_dir)
        zip_file.unlink()

        # Assert that there is only one file in the directory
        extracted_files = list(self.download_context.local_dir.iterdir())
        assert len(extracted_files) == 1, (
            f"Expected exactly one file in {self.download_context.local_dir}, found {len(extracted_files)}"
        )
        schematisation_file = extracted_files[0]
        # Upgrade schematisation to latest; on failure warn and continue with original gpkg
        try:
            upgraded_schematisation_path = self._upgrade_schematisation(
                schematisation_file
            )
            if upgraded_schematisation_path:
                schematisation_file = upgraded_schematisation_path
        except SchematisationUpgradeError as e:
            if self.warning_signal is not None:
                # not adding actual schema version here because import failure is one of the triggers of this error
                self.warning_signal.emit(
                    f"Schematisation upgrade failed, continuing with original schematisation version: {e}"
                )
        # Include revision number in file name
        rev_nr = self.revision["number"]
        file_name_with_rev = (
            f"{schematisation_file.stem} (rev{rev_nr}){schematisation_file.suffix}"
        )
        path_with_rev = schematisation_file.parent.joinpath(file_name_with_rev)
        schematisation_file.rename(path_with_rev)
        self._downloaded_file_path = path_with_rev

    def _upgrade_schematisation(self, schematisation_filepath: Path) -> Optional[Path]:
        # Assert signals are set properly
        assert self.progress_signal is not None, "progress signal not set"
        progress_callback = lambda progress_value, message: self.progress_signal.emit(
            int(progress_value), message
        )
        assert self.warning_signal is not None, "warning signal not set"
        try:
            from threedi_schema import ThreediDatabase, errors
            from threedi_schema.domain.models import ConnectionNode
        except ImportError:
            raise SchematisationUpgradeError(
                "Failed to upgrade schematisation: threedi-schema library could not be loaded"
            )
        threedi_db = ThreediDatabase(schematisation_filepath)
        schema = threedi_db.schema
        srid, _ = schema._get_epsg_data()
        if srid is None:
            rasters = self.revision.get("rasters", [])
            dem_raster = next((r for r in rasters if r.get("type") == "dem_file"), None)
            if dem_raster:
                srid = dem_raster.get("epsg_code")
        if srid is None:
            raise SchematisationUpgradeError(
                "Failed to upgrade schematisation: EPSG code could not be determined"
            )
        try:
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always", UserWarning)
                schema.upgrade(
                    backup=False,
                    epsg_code_override=srid,
                    progress_func=progress_callback,
                )
            if w:
                for warning in w:
                    self.warning_signal.emit(
                        f"{warning._category_name}: {warning.message}"
                    )
            # Validate that ConnectionNode table has data after upgrade
            session = threedi_db.get_session()
            connection_node_count = session.query(ConnectionNode).count()
            session.close()
            if connection_node_count > 0:
                return threedi_db.path
            else:
                raise SchematisationWithout1DError
        except errors.UpgradeFailedError as e:
            raise SchematisationUpgradeError(f"Failed to upgrade schematisation: {e}")


class RanaResultDownloader(BaseDownloader):
    """Downloads a pre-generated result raster via attachment_url."""

    def __init__(self, download_context: ResultsDownloadContext, result: dict):
        super().__init__(download_context)
        self.result = result

    @property
    def url(self) -> str:
        return self.result["attachment_url"]

    @property
    def file_id(self) -> str:
        return self.result["id"]

    def postprocess(self):
        pass


class SchematisationRevisionDownloadContext(AbstractDownloadContext):
    """Download context for schematisation revision files."""

    def __init__(self, schematisation_db_dir: Path):
        self.schematisation_db_dir = schematisation_db_dir
        # Populated after download completes
        self.local_schematisation = None
        self.geopackage_filepath = None
        self.wip_replace_requested = False

    @property
    def local_dir(self) -> Path:
        return self.schematisation_db_dir

    @property
    def local_file_path(self) -> Path:
        return self.schematisation_db_dir / "schematisation.zip"

    def get_style_zip(self):
        return None


class SchematisationRevisionDownloader(BaseDownloader):
    """Downloads schematisation revision files via download_required_files.

    The dialog to resolve the target directory must happen before constructing
    this downloader (use resolve_schematisation_download_dir on the main thread).
    """

    def __init__(
        self,
        download_context: SchematisationRevisionDownloadContext,
        schematisation,
        revision,
        local_schematisation,
        wip_replace_requested: bool,
    ):
        super().__init__(download_context)
        self.schematisation = schematisation
        self.revision = revision
        self.local_schematisation = local_schematisation
        self.wip_replace_requested = wip_replace_requested

    @property
    def url(self) -> str:
        raise NotImplementedError(
            "SchematisationRevisionDownloader overrides download_file"
        )

    def download_file(self, signals: FileDownloadWorkerSignals, download_file=True):
        """Download schematisation revision files."""
        from rana_qgis_plugin.simulation.utils import download_required_files

        try:
            result = download_required_files(
                self.schematisation,
                self.revision,
                self.download_context.schematisation_db_dir,
                self.local_schematisation,
                self.wip_replace_requested,
                progress_fn=signals.progress.emit,
            )
            self.download_context.local_schematisation = result[0]
            self.download_context.geopackage_filepath = result[1]
            self.download_context.wip_replace_requested = result[2]
            signals.finished.emit()
        except Exception as e:
            signals.failed.emit(f"Failed to download schematisation: {str(e)}")

    def postprocess(self):
        pass

    @property
    def file_id(self) -> str:
        schematisation_id = (
            self.schematisation["id"]
            if isinstance(self.schematisation, dict)
            else self.schematisation.id
        )
        revision_number = (
            self.revision["number"]
            if isinstance(self.revision, dict)
            else self.revision.number
        )
        return f"schematisation-{schematisation_id}-rev{revision_number}"


class LizardResultDownloader(BaseDownloader):
    """Downloads a result raster that requires on-demand generation from Lizard."""

    def __init__(
        self,
        download_context: ResultsDownloadContext,
        descriptor_id: str,
        result: dict,
        grid: dict,
        nodata: int,
        pixelsize: float,
        crs: str,
    ):
        super().__init__(download_context)
        self.descriptor_id = descriptor_id
        self.result = result
        self.grid = grid
        self.nodata = nodata
        self.pixelsize = pixelsize
        self.crs = crs

    @property
    def url(self) -> str:
        raise NotImplementedError("LizardResultDownloader overrides download_file")

    @property
    def file_id(self) -> str:
        return self.result["id"]

    def postprocess(self):
        pass

    def download_file(self, signals: FileDownloadWorkerSignals, download_file=True):
        """Generate raster tiles, poll until ready, download, and build VRT."""
        file_name = self.download_context.local_file_path.stem
        target_dir = self.download_context.local_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        # Split extent into tiles
        spatial_bounds = split_scenario_extent(
            grid=self.grid, resolution=self.pixelsize, max_pixel_count=1 * 10**8
        )
        bboxes, width, height = spatial_bounds

        # Request generation for each tile
        raster_tasks = []
        for i, (x1, y1, x2, y2) in enumerate(bboxes):
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
                descriptor_id=self.descriptor_id,
                raster_id=self.result["raster_id"],
                payload=payload,
            )
            raster_tasks.append(r)
            progress = int(((i + 1) / len(bboxes)) * 10)
            signals.progress.emit(progress, file_name)

        # Multi-tile: poll and download each tile
        if len(raster_tasks) > 1:
            rasters = {
                raster_task_id: {
                    "downloaded": False,
                    "filepath": bypass_max_path_limit(
                        str(target_dir / f"{file_name}{task_number:02d}.tif")
                    ),
                }
                for task_number, raster_task_id in enumerate(raster_tasks)
            }
            task_counter = 0

            while False in [task["downloaded"] for task in rasters.values()]:
                sleep(5)
                for raster_task_id in rasters.keys():
                    if not rasters[raster_task_id]["downloaded"]:
                        try:
                            file_link = get_raster_file_link(
                                descriptor_id=self.descriptor_id,
                                task_id=raster_task_id,
                            )
                            if file_link:
                                self._download_tile(
                                    file_link, rasters[raster_task_id]["filepath"]
                                )
                                rasters[raster_task_id]["downloaded"] = True
                                task_counter += 1
                                progress = int(
                                    10 + (task_counter / len(raster_tasks)) * 80
                                )
                                signals.progress.emit(progress, file_name)
                        except requests.exceptions.RequestException as e:
                            signals.failed.emit(f"Failed to download file: {str(e)}")
                            return
                        except Exception as e:
                            signals.failed.emit(f"An error occurred: {str(e)}")
                            return

            raster_filepaths = [item["filepath"] for item in rasters.values()]
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
            signals.progress.emit(100, file_name)

        # Single-tile: poll and download
        else:
            target_file = bypass_max_path_limit(str(target_dir / (file_name + ".tif")))
            file_link = False
            while not file_link:
                sleep(5)
                try:
                    file_link = get_raster_file_link(
                        descriptor_id=self.descriptor_id, task_id=raster_tasks[0]
                    )
                    if not file_link:
                        continue
                    self.download_url(
                        file_link,
                        Path(target_file),
                        signals.progress,
                        progress_min=10,
                        progress_max=100,
                    )
                except requests.exceptions.RequestException as e:
                    signals.failed.emit(f"Failed to download file: {str(e)}")
                    return
                except Exception as e:
                    signals.failed.emit(f"An error occurred: {str(e)}")
                    return

        signals.finished.emit()

    @staticmethod
    def _download_tile(file_link: str, target_file: str):
        """Download a single tile without progress tracking."""
        with requests.get(file_link, stream=True) as response:
            response.raise_for_status()
            with open(target_file, "wb") as f:
                for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                    f.write(chunk)


class SingleFileDownloadWorker(QThread):
    """Worker thread for downloading a single file."""

    def __init__(self, downloader: BaseDownloader):
        super().__init__()
        self.signals = FileDownloadWorkerSignals()
        self.downloader = downloader

    @pyqtSlot()
    def run(self):
        self.downloader.download_file(self.signals)


class BatchFileDownloadWorker(QThread):
    """Worker thread for downloading multiple files, one after the other."""

    def __init__(self, downloaders: list[BaseDownloader]):
        super().__init__()
        self.signals = FileDownloadWorkerSignals()
        self.downloaders = downloaders
        self.downloaded_files = {}
        self.warning_cnt = 0
        self.fail_cnt = 0
        self.signals.warning.connect(self._on_warning)
        self.signals.failed.connect(self._on_failed)

    def _on_warning(self, msg: str):
        self.warning_cnt += 1

    def _on_failed(self, msg: str):
        self.fail_cnt += 1

    @cached_property
    def unique_file_ids(self) -> set[str]:
        return set([downloader.file_id for downloader in self.downloaders])

    @property
    def nof_files(self) -> int:
        """Count number of unique files"""
        return len(self.unique_file_ids)

    def handle_existing(self, downloader) -> bool:
        """Check if a file was already downloaded by this worker. If so, just copy the file to the required destination"""
        if downloader.file_id in self.downloaded_files:
            download_path = downloader.download_context.local_file_path
            file_location = self.downloaded_files[downloader.file["id"]]
            # make sure the file didn't disappear somehow
            if file_location == str(download_path):
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
                if downloader.file_id == file_id
            )
            try:
                downloader.download_file(self.signals)
                download_path = downloader.download_context.local_file_path
                self.downloaded_files[downloader.file_id] = download_path
            except Exception as e:
                self.signals.failed.emit(f"An error occurred: {str(e)}")
            self.downloaders.remove(downloader)
        # Iterate over the remaining downloaders and copy the existing file
        for downloader in self.downloaders:
            # copy existing, and if redownload if that was unsuccessful
            download_file = not self.handle_existing(downloader)
            try:
                downloader.download_file(self.signals, download_file)
            except Exception as e:
                self.signals.failed.emit(f"An error occurred: {str(e)}")
        self.signals.all_finished.emit()
