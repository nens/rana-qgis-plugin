import os

import requests
from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot

from .utils import get_local_file_path

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
