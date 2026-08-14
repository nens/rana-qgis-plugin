"""Central loader: owns background workers and the avatar cache."""

from collections.abc import Callable
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

from qgis.core import QgsApplication, QgsProject
from qgis.PyQt.QtCore import QObject, QSettings, QThreadPool, pyqtSignal, pyqtSlot
from qgis.PyQt.QtGui import QPixmap
from qgis.PyQt.QtWidgets import QFileDialog

from rana_qgis_plugin.network_manager import NetworkUnavailableError
from rana_qgis_plugin.utils.api import (
    RanaPostError,
    delete_tenant_project_file,
    get_tenant_project_file,
    get_tenant_project_files,
    move_directory,
    move_file,
)
from rana_qgis_plugin.utils.upload import (
    ShapefileUploadJob,
    UploadJob,
    UploadTask,
    prepare_new_file_upload,
)
from rana_qgis_plugin.widgets.utils_avatars import AvatarCache
from rana_qgis_plugin.workers.avatars import AvatarWorker


class UploadChoice(Enum):
    """Choices presented while resolving an upload conflict."""

    SKIP = "Skip"
    OVERWRITE = "Overwrite"
    OVERWRITE_ALL = "Overwrite all conflicts"
    ABORT = "Cancel"


if TYPE_CHECKING:
    from rana_qgis_plugin.communication import UICommunication


class Loader(QObject):
    """Signal-based orchestrator for background work.

    Widgets connect to Loader signals rather than managing threads themselves.
    Currently handles avatar fetching; designed to grow with future background tasks.
    """

    avatar_updated = pyqtSignal(str, QPixmap)
    item_renamed = pyqtSignal(str, str, bool)  # old_path, new_path, is_folder
    item_deleted = pyqtSignal(str, bool)  # path, is_folder

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

    def rename_item(
        self, project_id: str, old_path: str, new_name: str, is_folder: bool
    ) -> str | None:
        """Rename a file or folder on Rana. Emits item_renamed on success.

        Returns None on success, or an error message string on failure.
        """
        if not new_name or not new_name.strip():
            return "Name cannot be empty."

        # Rana directory paths have a trailing /; strip it for path manipulation
        source = old_path.rstrip("/")
        try:
            new_path = PurePosixPath(source).with_name(new_name).as_posix()
        except ValueError:
            return f"'{new_name}' is not a valid name."

        try:
            if is_folder:
                if _has_sibling_folder(project_id, source, new_name):
                    return f"Folder '{new_name}' already exists."
                move_directory(
                    project_id,
                    params={
                        "source_path": source + "/",
                        "destination_path": new_path + "/",
                    },
                )
            else:
                if _has_sibling_file(project_id, old_path, new_name):
                    return f"File '{new_name}' already exists."
                move_file(
                    project_id,
                    params={"source_path": old_path, "destination_path": new_path},
                )
        except NetworkUnavailableError:
            return "No connection to Rana."
        except RanaPostError as e:
            return e.msg

        self.item_renamed.emit(old_path, new_path, is_folder)
        return None

    def delete_file(self, project_id: str, path: str) -> str | None:
        """Delete a file on Rana. Emits item_deleted on success.

        Returns None on success, or an error message string on failure.
        """
        try:
            delete_tenant_project_file(project_id, params={"path": path})
        except NetworkUnavailableError:
            return "No connection to Rana."
        except RanaPostError as e:
            return e.msg

        self.item_deleted.emit(path, False)
        return None

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

        jobs: list[UploadJob] = []
        convert_all = False
        overwrite_all = False
        project_instance = QgsProject.instance()
        transform_context = (
            project_instance.transformContext()
            if project_instance is not None
            else None
        )
        for local_path in local_paths:
            path = Path(local_path)
            source_shp_path = None
            if path.suffix.lower() == ".shp":
                if not convert_all:
                    conversion_choices = [
                        "Cancel",
                        "Convert",
                    ]
                    if len(local_paths) > 1:
                        conversion_choices.append("Convert all shapefiles")
                    choice = self.communication.custom_ask(
                        parent,
                        "Shapefile not supported",
                        "Rana does not natively support shapefiles, would you like to convert it before uploading or cancel?",
                        *conversion_choices,
                    )
                    if choice == "Cancel":
                        return
                    convert_all = choice == "Convert all shapefiles"
                source_shp_path = path
                path = path.with_suffix(".gpkg")

            result = prepare_new_file_upload(
                project["id"],
                path,
                folder_path,
                overwrite_exact=False,
                overwrite_case=overwrite_all,
            )
            if (
                result.conflict_path and not result.exact_conflict
            ) and not overwrite_all:
                overwrite_choices = [
                    UploadChoice.SKIP.value,
                    UploadChoice.OVERWRITE.value,
                ]
                if len(local_paths) > 1:
                    overwrite_choices.append(UploadChoice.OVERWRITE_ALL.value)
                overwrite_choices.append(UploadChoice.ABORT.value)
                choice = UploadChoice(
                    self.communication.custom_ask(
                        parent,
                        "File conflict",
                        result.error,
                        *overwrite_choices,
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
            if result.error:
                self.communication.show_warn(result.error)
            if result.job:
                if source_shp_path is not None:
                    jobs.append(
                        ShapefileUploadJob.from_upload_job(
                            result.job, source_shp_path, transform_context
                        )
                    )
                else:
                    jobs.append(result.job)

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


# TODO: I hate these methods here, but they are good for testability


def _has_sibling_folder(project_id: str, source: str, new_name: str) -> bool:
    """Check whether a folder with new_name already exists among siblings."""
    parent_path = PurePosixPath(source).parent
    params = (
        {"path": parent_path.as_posix()} if parent_path != PurePosixPath(".") else None
    )
    siblings = get_tenant_project_files(project_id, params=params)
    return any(
        sibling["type"] == "directory"
        and sibling["id"].rstrip("/").rsplit("/", 1)[-1] == new_name
        for sibling in siblings
    )


def _has_sibling_file(project_id: str, old_path: str, new_name: str) -> bool:
    """Check whether a file with new_name already exists among siblings."""
    target_path = PurePosixPath(old_path).with_name(new_name).as_posix()
    return get_tenant_project_file(project_id, {"path": target_path}) is not None
