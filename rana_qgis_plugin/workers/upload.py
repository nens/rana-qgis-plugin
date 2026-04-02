from pathlib import Path

import requests
from qgis.PyQt.QtCore import (
    QSettings,
    QThread,
    pyqtSignal,
    pyqtSlot,
)

from rana_qgis_plugin.utlis.api import (
    finish_file_upload,
    get_tenant_project_file,
    start_file_upload,
)


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

    def get_online_path(self, local_path: Path) -> str:
        return f"{self.online_dir}{local_path.name}"

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
        self.finished.connect(self._finish)

    def get_online_path(self, local_path: Path) -> str:
        return self.online_path

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
