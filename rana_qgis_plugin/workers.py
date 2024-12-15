import os

import requests
from PyQt5.QtCore import QSettings, QThread, pyqtSignal, pyqtSlot

from .utils import get_local_file_path
from .utils_api import finish_file_upload, get_tenant_project_file, start_file_upload

CHUNK_SIZE = 1024 * 1024  # 1 MB


class FileDownloadWorker(QThread):
    """Worker thread for downloading files."""

    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(
        self,
        url: str,
        path: str,
        project_name: str,
        file_name: str,
    ):
        super().__init__()
        self.url = url
        self.path = path
        self.project_name = project_name
        self.file_name = file_name

    @pyqtSlot()
    def run(self):
        local_dir_structure, local_file_path = get_local_file_path(self.project_name, self.path, self.file_name)
        os.makedirs(local_dir_structure, exist_ok=True)
        try:
            with requests.get(self.url, stream=True) as response:
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
                            self.progress.emit(progress)
                            previous_progress = progress
            self.finished.emit(local_file_path)
        except requests.exceptions.RequestException as e:
            self.failed.emit(f"Failed to download file: {str(e)}")
        except Exception as e:
            self.failed.emit(f"An error occurred: {str(e)}")


class FileUploadWorker(QThread):
    """Worker thread for uploading files."""

    progress = pyqtSignal(int)
    finished = pyqtSignal()
    conflict = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(
        self,
        tenant: str,
        project: dict,
        file: dict,
    ):
        super().__init__()
        self.tenant = tenant
        self.project = project
        self.file = file
        self.file_overwrite = None  # Set to True to overwrite file, False to abort upload
        self.last_modified = None
        self.last_modified_key = f"{project['name']}/{file['id']}/last_modified"

    def handle_file_conflict(self):
        file_path = self.file["id"]
        local_last_modified = QSettings().value(self.last_modified_key)
        server_file = get_tenant_project_file(self.tenant, self.project["id"], {"path": file_path})
        if not server_file:
            self.failed.emit("Failed to get file from server. Check if file has been moved or deleted.")
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

    @pyqtSlot()
    def run(self):
        if not self.file or not self.project["id"]:
            return
        project_name = self.project["name"]
        file_name = os.path.basename(self.file["id"].rstrip("/"))
        file_path = self.file["id"]
        _, local_file_path = get_local_file_path(project_name, file_path, file_name)

        # Check if file exists locally before uploading
        if not os.path.exists(local_file_path):
            self.failed.emit(f"File not found: {local_file_path}")
            return

        # Handle file conflict
        continue_upload = self.handle_file_conflict()
        if not continue_upload:
            return

        # Save file to Rana
        try:
            self.progress.emit(0)
            # Step 1: POST request to initiate the upload
            upload_response = start_file_upload(self.tenant, self.project["id"], {"path": file_path})
            if not upload_response:
                self.failed.emit("Failed to initiate file upload.")
                return
            upload_url = upload_response["urls"][0]
            # Step 2: Upload the file to the upload_url
            self.progress.emit(20)
            with open(local_file_path, "rb") as file:
                response = requests.put(upload_url, data=file)
                response.raise_for_status()
            # Step 3: Complete the upload
            self.progress.emit(80)
            response = finish_file_upload(
                self.tenant,
                self.project["id"],
                upload_response,
            )
            if not response:
                self.failed.emit("Failed to complete file upload.")
                return
            QSettings().setValue(self.last_modified_key, self.last_modified)
            self.progress.emit(100)
            self.finished.emit()
        except Exception as e:
            self.failed.emit(f"Failed to upload file to Rana: {str(e)}")
