"""Central loader: owns background workers and the avatar cache."""

from collections.abc import Callable
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

from qgis.core import QgsApplication
from qgis.PyQt.QtCore import QObject, QSettings, QThreadPool, pyqtSignal, pyqtSlot
from qgis.PyQt.QtGui import QPixmap
from qgis.PyQt.QtWidgets import QFileDialog

from rana_qgis_plugin.utils.qgis import convert_vectorfile_to_geopackage
from rana_qgis_plugin.utils.upload import UploadTask, prepare_new_file_upload
from rana_qgis_plugin.widgets.utils_avatars import AvatarCache
from rana_qgis_plugin.workers.avatars import AvatarWorker


class UploadChoice(Enum):
    """Choices presented while resolving an upload conflict."""

    SKIP = "Skip this file"
    OVERWRITE = "Overwrite this file"
    OVERWRITE_ALL = "Overwrite all conflicts"
    ABORT = "Abort"


if TYPE_CHECKING:
    from rana_qgis_plugin.communication import UICommunication


class Loader(QObject):
    """Signal-based orchestrator for background work.

    Widgets connect to Loader signals rather than managing threads themselves.
    Currently handles avatar fetching; designed to grow with future background tasks.
    """

    avatar_updated = pyqtSignal(str, QPixmap)

    def __init__(self, communication: "UICommunication", parent=None):
        super().__init__(parent)
        self.avatar_cache = AvatarCache()
        self.avatar_cache.avatar_changed.connect(self.on_avatar_changed)
        self.communication = communication
        self.avatar_pool = QThreadPool()
        self.avatar_pool.setMaxThreadCount(1)
        self.avatar_worker: AvatarWorker | None = None

    def shutdown(self) -> None:
        """Cancel pending work and drain the pool. Call on plugin unload."""
        if self.avatar_worker is not None:
            self.avatar_worker.cancel()
        self.avatar_pool.waitForDone(3000)

    def fetch_avatars(self, users: list[dict]) -> None:
        """Start a background fetch of real avatars for the given users."""
        if not users:
            return
        if self.avatar_worker is not None:
            self.avatar_worker.cancel()
        self.avatar_worker = AvatarWorker(self.communication, users)
        self.avatar_worker.signals.avatar_ready.connect(self.avatar_cache.update_avatar)
        self.avatar_pool.start(self.avatar_worker)

    @pyqtSlot(str)
    def on_avatar_changed(self, user_id: str) -> None:
        avatar = self.avatar_cache.get_avatar_from_cache(user_id)
        if avatar:
            self.avatar_updated.emit(user_id, avatar)

    def upload_files(
        self,
        project: dict,
        folder_path: str,
        parent=None,
        refresh_callback: Callable[[], None] | None = None,
    ) -> None:
        """Select, prepare, and submit uploads for a project folder."""
        last_dir = QSettings().value("Rana/last_upload_folder", "")
        local_paths, _ = QFileDialog.getOpenFileNames(
            parent,
            "Open file(s)",
            last_dir,
            "All supported files (*.tif *.tiff *.gpkg *.sqlite *.geojson *.shp);;"
            "Rasters (*.tif *.tiff);;"
            "Vector files (*.gpkg *.sqlite *.geojson *.shp)",
        )
        if not local_paths:
            return
        QSettings().setValue(
            "Rana/last_upload_folder", str(Path(local_paths[0]).parent)
        )

        jobs = []
        convert_all = False
        overwrite_all = False
        for local_path in local_paths:
            path = Path(local_path)
            if path.suffix.lower() == ".shp":
                if not convert_all:
                    choice = self.communication.custom_ask(
                        parent,
                        "Shapefile not supported",
                        "Rana does not natively support shapefiles, would you like to convert it before uploading or cancel?",
                        "Cancel",
                        "Convert this file only",
                        "Convert all shapefiles",
                    )
                    if choice == "Cancel":
                        return
                    convert_all = choice == "Convert all shapefiles"
                path = Path(convert_vectorfile_to_geopackage(str(path)))

            result = prepare_new_file_upload(
                project["id"],
                path,
                folder_path,
                overwrite_exact=False,
                overwrite_case=overwrite_all,
            )
            if result.job:
                jobs.append(result.job)
                continue
            if result.conflict_path and not result.exact_conflict:
                choice = UploadChoice(
                    self.communication.custom_ask(
                        parent,
                        "File conflict",
                        result.error,
                        UploadChoice.SKIP.value,
                        UploadChoice.OVERWRITE.value,
                        UploadChoice.OVERWRITE_ALL.value,
                        UploadChoice.ABORT.value,
                    )
                )
                if choice == UploadChoice.ABORT:
                    return
                if choice == UploadChoice.SKIP:
                    continue
                if choice == UploadChoice.OVERWRITE_ALL:
                    overwrite_all = True
                if choice in (UploadChoice.OVERWRITE, UploadChoice.OVERWRITE_ALL):
                    result = prepare_new_file_upload(
                        project["id"],
                        path,
                        folder_path,
                        overwrite_exact=False,
                        overwrite_case=True,
                    )
                    if result.job:
                        jobs.append(result.job)
            elif result.error:
                self.communication.show_warn(result.error)

        if not jobs:
            return
        task_manager = QgsApplication.taskManager()
        if task_manager is None:
            self.communication.bar_error("Could not start file upload.")
            return
        task = UploadTask(jobs)
        task.file_failed.connect(self.handle_upload_file_failed)
        task.file_started.connect(self.handle_upload_file_started)
        task.taskCompleted.connect(
            lambda: self.handle_upload_completed(
                True, refresh_callback=refresh_callback
            )
        )
        task.taskTerminated.connect(lambda: self.handle_upload_completed(False, task))
        task_manager.addTask(task)

    @pyqtSlot(str)
    def handle_upload_file_started(self, filename: str) -> None:
        """Show a marquee progress bar for the file currently uploading."""
        self.communication.progress_bar(
            f"Uploading {filename}", minimum=0, maximum=0, clear_msg_bar=True
        )

    @pyqtSlot(str, str)
    def handle_upload_file_failed(self, local_path: str, error: str) -> None:
        """Log an individual upload failure reported by the task."""
        self.communication.log_err(f"Failed to upload {local_path}: {error}")

    def handle_upload_completed(
        self,
        success: bool,
        task: UploadTask | None = None,
        refresh_callback: Callable[[], None] | None = None,
    ) -> None:
        """Report upload completion and call refresh_callback on success."""
        self.communication.clear_message_bar()
        if success:
            self.communication.bar_info("File upload completed.")
            if refresh_callback is not None:
                refresh_callback()
            return
        if task is not None and task.isCanceled():
            self.communication.bar_warn("File upload cancelled.")
        else:
            self.communication.bar_error("File upload failed.")
