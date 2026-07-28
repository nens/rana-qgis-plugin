from pathlib import Path
from typing import Optional

import requests
from qgis.PyQt.QtCore import (
    QSettings,
    QThread,
    pyqtSignal,
    pyqtSlot,
)

from rana_qgis_plugin.utils.api import (
    finish_file_upload,
    get_tenant_file_descriptor,
    get_tenant_project_file,
    start_file_upload,
)
from rana_qgis_plugin.utils.local_paths import get_local_file_path
from rana_qgis_plugin.utils.time import convert_timestamp_str_to_local_time


def _extract_case_conflict_path(error: dict) -> str | None:
    """Extract the conflicting server path from a 400 case-conflict error body.

    The API returns detail[0].ctx.path when a file with the same name (different
    case) already exists. Returns None if the error body does not match this shape.
    """
    try:
        return error["detail"][0]["ctx"]["path"]
    except (KeyError, IndexError, TypeError):
        return None


class FileUploadWorker(QThread):
    """Worker thread for uploading new (non-rana) files.

    When ask_overwrite_permission is True, the worker emits `conflict` and waits
    for `file_overwrite` to be set by the caller instead of failing immediately
    when a name conflict is detected (exact match or case-insensitive).
    """

    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)
    conflict = pyqtSignal(str)
    failed = pyqtSignal(str)
    warning = pyqtSignal(str)

    def __init__(
        self,
        project: dict,
        local_paths: list[Path],
        online_dir: str,
        ask_overwrite_permission: bool = False,
    ):
        super().__init__()
        self.project = project
        self.local_paths = local_paths
        if online_dir and not online_dir.endswith("/"):
            online_dir += "/"
        self.online_dir = online_dir
        self.ask_overwrite_permission = ask_overwrite_permission
        self.file_overwrite = None

    def _ask_overwrite(self, online_path: str, server_file: dict) -> bool:
        """Build conflict message from server_file, emit conflict, block until decided."""
        user = server_file.get("user") or {}
        if "given_name" in user and "family_name" in user:
            created_by = f"{user['given_name']} {user['family_name']}"
        else:
            created_by = "unknown"
        created_at = convert_timestamp_str_to_local_time(server_file["last_modified"])
        message = (
            f"File {Path(online_path).name} at {online_path} was already "
            f"created at {created_at} by {created_by}.\n"
            f"Do you want to replace it?"
        )
        self.file_overwrite = None
        self.conflict.emit(message)
        while self.file_overwrite is None:
            self.msleep(100)
        return self.file_overwrite

    def handle_file_conflict(self, online_path):
        server_file = get_tenant_project_file(self.project["id"], {"path": online_path})
        if server_file:
            if self.ask_overwrite_permission:
                if not self._ask_overwrite(online_path, server_file):
                    self.failed.emit("File upload aborted.")
                    return False
            else:
                self.failed.emit("File already exists on server.")
                return False
        return True  # Continue to upload

    def update_payload(self, payload):
        return payload.copy()

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

    def get_online_path(self, local_path: Path) -> str:
        return f"{self.online_dir}{local_path.name}"

    def _initiate_upload(self, online_path: str) -> dict | None:
        """POST to start the upload. Returns the upload response or None on failure.

        On a case-insensitive conflict (API 400 with ctx.path): if
        ask_overwrite_permission is True, emits `conflict`, waits for approval,
        then retries with the server-side path from ctx.path. Otherwise fails.
        """
        upload_response, error = start_file_upload(
            self.project["id"], {"path": online_path}
        )
        if not upload_response:
            conflict_path = _extract_case_conflict_path(error)
            if conflict_path and self.ask_overwrite_permission:
                server_file = get_tenant_project_file(
                    self.project["id"], {"path": conflict_path}
                )
                if not self._ask_overwrite(conflict_path, server_file or {}):
                    self.failed.emit("File upload aborted.")
                    return None
                upload_response, error = start_file_upload(
                    self.project["id"], {"path": conflict_path}
                )
                if not upload_response:
                    self.failed.emit("Failed to initiate file upload.")
                    return None
            elif conflict_path:
                self.failed.emit(
                    f"File not uploaded: a file named '{Path(conflict_path).name}' "
                    f"already exists on the server. File names must be unique and case differences are ignored."
                )
                return None
            else:
                self.failed.emit("Failed to initiate file upload.")
                return None
        return upload_response

    def upload_single_file(
        self, local_path: Path, progress_start, progress_step
    ) -> bool:
        online_path = self.get_online_path(local_path)
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
            upload_response = self._initiate_upload(online_path)
            if not upload_response:
                return False
            upload_url = upload_response["urls"][0]
            # Step 2: Upload the file to the upload_url
            self.progress.emit(int(0.2 * progress_step + progress_start), "")
            with open(local_path, "rb") as file:
                response = requests.put(upload_url, data=file)
                response.raise_for_status()
            # Step 3: Complete the upload
            self.progress.emit(int(0.8 * progress_step + progress_start), "")

            upload_response = self.update_payload(upload_response)

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

    def __init__(self, project: dict, file: dict, local_file: Optional[Path] = None):
        if not local_file:
            local_file = Path(get_local_file_path(project["slug"], file["id"]))
        if "/" not in file["id"]:
            online_dir = ""
        else:
            online_dir = file["id"][: file["id"].rindex("/") + 1]
        self.online_path = file["id"]
        super().__init__(project, [local_file], online_dir)

        self.file_overwrite = False
        self.last_modified = None
        self.last_modified_key = f"{project['name']}/{file['id']}/last_modified"
        self.file = file

        self.finished.connect(self._finish)

    def get_online_path(self, local_path: Path) -> str:
        return self.online_path

    def update_payload(self, payload):
        # In case of existing files, we would like to reset some meta data
        result = payload.copy()
        descriptor = get_tenant_file_descriptor(self.file["descriptor_id"])

        if "meta" in descriptor:
            if "style_id" in descriptor["meta"]:
                result["descriptor"] = {
                    "meta": {"style_id": descriptor["meta"]["style_id"]},
                    "description": descriptor["description"],
                    "data_type": descriptor["data_type"],
                }
        return result

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
            self.conflict.emit(
                "The file has been modified on the server since it was last downloaded.\n"
                "Do you want to overwrite the server copy with the local copy?"
            )
            while self.file_overwrite is None:
                self.msleep(100)
            if self.file_overwrite is False:
                self.failed.emit("File upload aborted.")
                return False
        return True  # Continue to upload

    def _finish(self):
        QSettings().setValue(self.last_modified_key, self.last_modified)
