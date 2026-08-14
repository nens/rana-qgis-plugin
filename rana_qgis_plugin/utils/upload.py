from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import cast

import requests
from qgis.core import QgsTask
from qgis.PyQt.QtCore import QSettings, pyqtSignal

from rana_qgis_plugin.network_manager import NetworkUnavailableError
from rana_qgis_plugin.utils.api import (
    finish_file_upload,
    get_tenant_file_descriptor,
    get_tenant_project_file,
    start_file_upload,
)
from rana_qgis_plugin.utils.local_paths import get_local_file_path
from rana_qgis_plugin.utils.qgis import convert_vectorfile_to_geopackage


@dataclass
class UploadJob:
    """Prepared data needed to transfer one file."""

    project_id: str
    local_path: Path
    upload_url: str
    payload: dict

    def preprocess(self) -> None:
        """Perform any work required before transferring the file."""


@dataclass
class ShapefileUploadJob(UploadJob):
    """Upload job that converts a shapefile before transferring it."""

    source_path: Path
    transform_context: object

    @classmethod
    def from_upload_job(
        cls, job: UploadJob, source_path: Path, transform_context: object
    ) -> "ShapefileUploadJob":
        return cls(
            job.project_id,
            job.local_path,
            job.upload_url,
            job.payload,
            source_path,
            transform_context,
        )

    def preprocess(self) -> None:
        convert_vectorfile_to_geopackage(
            str(self.source_path), transform_context=self.transform_context
        )


@dataclass
class UploadPreparationResult:
    """Result of preparing one upload before background transfer."""

    job: UploadJob | None
    error: str | None = None
    conflict_path: str | None = None
    exact_conflict: bool = False


def extract_case_conflict_path(error: dict | None) -> str | None:
    """Extract a conflicting server path from an initiation error."""
    if error is None:
        return None
    try:
        return error["detail"][0]["ctx"]["path"]
    except (KeyError, IndexError, TypeError):
        return None


def prepare_new_file_upload(
    project_id: str,
    local_path: Path,
    online_dir: str,
    overwrite_exact: bool = False,
    overwrite_case: bool = False,
) -> UploadPreparationResult:
    """Prepare a new file upload after resolving supplied conflict decisions.

    Returns a result without a job when the file conflicts or initiation fails.
    """
    online_path = str(PurePosixPath(online_dir) / local_path.name)
    try:
        if (
            get_tenant_project_file(project_id, {"path": online_path})
            and not overwrite_exact
        ):
            return UploadPreparationResult(
                None,
                f"File already exists on the server and was skipped: {online_path}",
                exact_conflict=True,
            )
        response, error = start_file_upload(project_id, {"path": online_path})
    except NetworkUnavailableError as exc:
        return UploadPreparationResult(None, str(exc))
    if not response:
        conflict_path = extract_case_conflict_path(error)
        # retry if response failed because of case conflict and overwrite_case is allowed
        if conflict_path and not overwrite_case:
            return UploadPreparationResult(
                None,
                "A file with the same name already exists on the server.",
                conflict_path,
            )
        if conflict_path:
            try:
                response, error = start_file_upload(project_id, {"path": conflict_path})
            except NetworkUnavailableError as exc:
                return UploadPreparationResult(None, str(exc))
        if not response or len(response.get("urls", [])) == 0:
            return UploadPreparationResult(
                None, f"Failed to initiate file upload: {error}."
            )

    return UploadPreparationResult(
        UploadJob(project_id, local_path, response["urls"][0], response.copy())
    )


def prepare_existing_file_upload(
    project: dict,
    file: dict,
    local_file: Path | None = None,
    overwrite: bool = False,
) -> UploadPreparationResult:
    """Prepare an upload for a file already stored on the server."""
    try:
        local_file = local_file or Path(
            get_local_file_path(project["slug"], file["id"])
        )
        server_file = get_tenant_project_file(project["id"], {"path": file["id"]})
        if not server_file:
            return UploadPreparationResult(
                None,
                "Failed to get file from server. Check if it has been moved or deleted.",
            )

        timestamp_key = f"{project['name']}/{file['id']}/last_modified"
        local_timestamp = QSettings().value(timestamp_key)
        server_timestamp = server_file["last_modified"]
        if server_timestamp == local_timestamp:
            return UploadPreparationResult(
                None, "The file has not been modified on the server."
            )
        if not overwrite:
            return UploadPreparationResult(
                None, "The file has been modified on the server."
            )

        response, _ = start_file_upload(project["id"], {"path": file["id"]})
        if not response:
            return UploadPreparationResult(None, "Failed to initiate file upload.")

        payload = response.copy()
        descriptor = get_tenant_file_descriptor(file["descriptor_id"])
        if descriptor and "style_id" in descriptor.get("meta", {}):
            payload["descriptor"] = {
                "meta": {"style_id": descriptor["meta"]["style_id"]},
                "description": descriptor["description"],
                "data_type": descriptor["data_type"],
            }
        return UploadPreparationResult(
            UploadJob(project["id"], local_file, response["urls"][0], payload)
        )
    except NetworkUnavailableError as e:
        return UploadPreparationResult(None, str(e))


class UploadTask(QgsTask):
    """Upload prepared files without blocking QGIS's main thread."""

    file_failed = pyqtSignal(str, str)
    file_started = pyqtSignal(str)

    def __init__(self, jobs: list[UploadJob]):
        # QgsTask.CanCancel may not be exposed in all typed stubs; use getattr
        # and cast to the expected Flags type to satisfy mypy while keeping
        # runtime behaviour when the attribute exists.
        cancel_flag = cast("QgsTask.Flags", getattr(QgsTask, "CanCancel", 0))
        super().__init__("Upload files", flags=cancel_flag)
        self.jobs = jobs
        self.failed_files: list[tuple[Path, str]] = []
        self.successful_files: list[Path] = []

    def run(self) -> bool:
        """PUT and finish each prepared upload, stopping on cancellation."""
        for index, job in enumerate(self.jobs):
            if self.isCanceled():
                return False
            self.file_started.emit(job.local_path.name)
            try:
                job.preprocess()
                with job.local_path.open("rb") as file:
                    # timout guerds against failing to reach the server
                    # no read timeout because S3 only responds at the end of the PUT
                    response = requests.put(
                        job.upload_url, data=file, timeout=(15, None)
                    )
                    response.raise_for_status()
                if not finish_file_upload(job.project_id, job.payload):
                    raise RuntimeError("Failed to complete file upload")
                self.successful_files.append(job.local_path)
            except Exception as error:
                self.failed_files.append((job.local_path, str(error)))
                self.file_failed.emit(str(job.local_path), str(error))
            self.setProgress((index + 1) * 100 / len(self.jobs))
        return len(self.failed_files) == 0
