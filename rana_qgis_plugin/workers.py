import io
import json
import os
import zipfile
from pathlib import Path
from typing import List

import requests
from bridgestyle.mapboxgl.fromgeostyler import convertGroup
from PyQt5.QtCore import QSettings, QThread, pyqtSignal, pyqtSlot
from qgis.core import QgsProject
from threedi_mi_utils import bypass_max_path_limit

from .utils import get_local_file_path, image_to_bytes
from .utils_api import (
    finish_file_upload,
    get_tenant_file_descriptor_view,
    get_tenant_file_url,
    get_tenant_project_file,
    get_vector_style_file,
    get_vector_style_upload_urls,
    map_result_to_file_name,
    start_file_upload,
)

CHUNK_SIZE = 1024 * 1024  # 1 MB


class FileDownloadWorker(QThread):
    """Worker thread for downloading files."""

    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict, dict, str)
    failed = pyqtSignal(str)

    def __init__(
        self,
        project: dict,
        file: dict,
    ):
        super().__init__()
        self.project = project
        self.file = file

    @pyqtSlot()
    def run(self):
        project_slug = self.project["slug"]
        path = self.file["id"]
        descriptor_id = self.file["descriptor_id"]
        url = get_tenant_file_url(self.project["id"], {"path": path})
        local_dir_structure, local_file_path = get_local_file_path(project_slug, path)
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
                            self.progress.emit(progress, "")
                            previous_progress = progress
            # Fetch and extract the QML zip for vector files
            if self.file["data_type"] == "vector":
                qml_zip_content = get_vector_style_file(descriptor_id, "qml.zip")
                if qml_zip_content:
                    stream = io.BytesIO(qml_zip_content)
                    if zipfile.is_zipfile(stream):
                        with zipfile.ZipFile(stream, "r") as zip_file:
                            zip_file.extractall(local_dir_structure)
            self.finished.emit(self.project, self.file, local_file_path)
        except requests.exceptions.RequestException as e:
            self.failed.emit(f"Failed to download file: {str(e)}")
        except Exception as e:
            self.failed.emit(f"An error occurred: {str(e)}")


class FileUploadWorker(QThread):
    """Worker thread for uploading new (non-rana) files."""

    progress = pyqtSignal(int, str)
    finished = pyqtSignal()
    conflict = pyqtSignal()
    failed = pyqtSignal(str)
    warning = pyqtSignal(str)

    def __init__(self, project: dict, local_path: Path, online_path: str):
        super().__init__()
        self.project = project
        self.local_path = local_path
        self.online_path = online_path

    def handle_file_conflict(self):
        server_file = get_tenant_project_file(
            self.project["id"], {"path": self.online_path}
        )
        if server_file:
            self.failed.emit("File already exist on server.")
            return False
        return True  # Continue to upload

    @pyqtSlot()
    def run(self):
        if not self.local_path or not self.project["id"]:
            return
        local_file_path = str(self.local_path)

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
            self.progress.emit(0, "")
            # Step 1: POST request to initiate the upload
            upload_response = start_file_upload(
                self.project["id"], {"path": self.online_path}
            )
            if not upload_response:
                self.failed.emit("Failed to initiate file upload.")
                return
            upload_url = upload_response["urls"][0]
            # Step 2: Upload the file to the upload_url
            self.progress.emit(20, "")
            with open(local_file_path, "rb") as file:
                response = requests.put(upload_url, data=file)
                response.raise_for_status()
            # Step 3: Complete the upload
            self.progress.emit(80, "")
            response = finish_file_upload(
                self.project["id"],
                upload_response,
            )
            if not response:
                self.failed.emit("Failed to complete file upload.")
                return
            self.progress.emit(100, "")
            self.finished.emit()
        except Exception as e:
            self.failed.emit(f"Failed to upload file to Rana: {str(e)}")


class ExistingFileUploadWorker(FileUploadWorker):
    """Worker thread for uploading files."""

    def __init__(self, project: dict, file: dict):
        super().__init__(
            project, get_local_file_path(project["slug"], file["id"])[1], file["id"]
        )

        self.file_overwrite = False
        self.last_modified = None
        self.last_modified_key = f"{project['name']}/{file['id']}/last_modified"
        self.finished.connect(self._finish)

    def handle_file_conflict(self):
        local_last_modified = QSettings().value(self.last_modified_key)
        server_file = get_tenant_project_file(
            self.project["id"], {"path": self.online_path}
        )
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


class VectorStyleWorker(QThread):
    """Worker thread for generating vector styling files"""

    finished = pyqtSignal(str)
    failed = pyqtSignal(str)
    warning = pyqtSignal(str)

    def __init__(
        self,
        project: dict,
        file: dict,
    ):
        super().__init__()
        self.project = project
        self.file = file

    def upload_to_s3(self, url: str, data: dict, content_type: str):
        """Method to upload to S3"""
        try:
            headers = {"Content-Type": content_type}
            response = requests.put(url, data=data, headers=headers)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            self.failed.emit(f"Failed to upload file to S3: {str(e)}")

    def create_qml_zip(self, local_dir: str, zip_path: str):
        """Craete a QML zip file for all the qml files in the local directory"""
        try:
            with zipfile.ZipFile(zip_path, "w") as zip_file:
                for root, _, files in os.walk(local_dir):
                    for file in files:
                        if file.endswith(".qml"):
                            file_path = os.path.join(root, file)
                            zip_file.write(
                                file_path, os.path.relpath(file_path, local_dir)
                            )
        except Exception as e:
            self.failed.emit(f"Failed to create QML zip: {str(e)}")

    @pyqtSlot()
    def run(self):
        if not self.file:
            self.failed.emit("File not found.")
            return
        path = self.file["id"]
        file_name = os.path.basename(path.rstrip("/"))
        descriptor_id = self.file["descriptor_id"]
        all_layers = QgsProject.instance().mapLayers().values()
        layers = [layer for layer in all_layers if file_name in layer.source()]

        if not layers:
            self.failed.emit(
                f"No layers found for {file_name}. Open the file in QGIS and try again."
            )
            return

        qgis_layers = {layer.name(): layer for layer in layers}
        group = {"layers": list(qgis_layers.keys())}
        base_url = "http://baseUrl"

        # Save QML style files for each layer to local directory
        local_dir, _ = get_local_file_path(self.project["slug"], path)
        os.makedirs(local_dir, exist_ok=True)
        for layer in layers:
            qml_path = os.path.join(local_dir, f"{layer.name()}.qml")
            layer.saveNamedStyle(str(qml_path))

        # Convert QGIS layers to styling files for the Rana Web Client
        try:
            _, warnings, mb_style, sprite_sheet = convertGroup(
                group, qgis_layers, base_url, workspace="workspace", name="default"
            )
            if warnings:
                self.warning.emit(", ".join(warnings))

            # Get upload URLs to S3
            upload_urls = get_vector_style_upload_urls(descriptor_id)

            if not upload_urls:
                self.failed.emit("Failed to get vector style upload URLs from the API.")
                return

            # Upload style.json
            self.upload_to_s3(
                upload_urls["style.json"], json.dumps(mb_style), "application/json"
            )

            # Upload sprite images if available
            if sprite_sheet and sprite_sheet.get("img") and sprite_sheet.get("img2x"):
                self.upload_to_s3(
                    upload_urls["sprite.png"],
                    image_to_bytes(sprite_sheet["img"]),
                    "image/png",
                )
                self.upload_to_s3(
                    upload_urls["sprite@2x.png"],
                    image_to_bytes(sprite_sheet["img2x"]),
                    "image/png",
                )
                self.upload_to_s3(
                    upload_urls["sprite.json"], sprite_sheet["json"], "application/json"
                )
                self.upload_to_s3(
                    upload_urls["sprite@2x.json"],
                    sprite_sheet["json2x"],
                    "application/json",
                )

            # Zip and upload QML zip
            zip_path = os.path.join(local_dir, "qml.zip")
            self.create_qml_zip(local_dir, zip_path)
            with open(zip_path, "rb") as file:
                self.upload_to_s3(upload_urls["qml.zip"], file, "application/zip")
            os.remove(zip_path)

            # Finish
            self.finished.emit(f"Styling files uploaded successfully for {file_name}.")
        except Exception as e:
            self.failed.emit(f"Failed to generate and upload styling files: {str(e)}")


class LizardResultDownloadWorker(QThread):
    """Worker thread for downloading files from ."""

    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict, dict, str)
    failed = pyqtSignal(str)

    def __init__(
        self, project: dict, file: dict, result_ids: List[int], target_folder: str
    ):
        super().__init__()
        self.project = project
        self.file = file
        self.result_ids = result_ids
        self.target_folder = target_folder

    @pyqtSlot()
    def run(self):
        descriptor_id = self.file["descriptor_id"]
        for result_id in self.result_ids:
            # Retrieve URLS from file descriptors (again), presigned url might be expired
            results = get_tenant_file_descriptor_view(
                descriptor_id, "lizard-scenario-results"
            )
            result = [r for r in results if r["id"] == result_id][0]
            file_name = map_result_to_file_name(result)
            target_file = bypass_max_path_limit(
                os.path.join(self.target_folder, file_name)
            )

            try:
                with requests.get(result["attachment_url"], stream=True) as response:
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
            except Exception as e:
                self.failed.emit(f"An error occurred: {str(e)}")

        self.finished.emit(self.project, self.file, self.target_folder)
