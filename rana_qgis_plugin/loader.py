"""Central loader: owns background workers and the avatar cache."""

from collections.abc import Callable
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

from qgis.core import QgsApplication, QgsProject
from qgis.PyQt.QtCore import QObject, QSettings, QThreadPool, pyqtSignal, pyqtSlot
from qgis.PyQt.QtGui import QPixmap
from qgis.PyQt.QtWidgets import QFileDialog, QMessageBox

from rana_qgis_plugin.layer_management.dirty_tracking import (
    DATA_DIRTY_PROPERTY,
    STYLE_DIRTY_PROPERTY,
    clear_dirty,
)
from rana_qgis_plugin.layer_management.layer_manager import (
    RanaLayerRef,
    clear_rana_refs,
    get_rana_refs,
    get_vector_layer_names,
    open_rana_raster,
    open_rana_vector_layer,
    open_rana_vector_layers,
)
from rana_qgis_plugin.layer_management.sync_lock import LayerLockRegistry
from rana_qgis_plugin.network_manager import NetworkUnavailableError
from rana_qgis_plugin.utils.api import (
    FileDescriptorStatus,
    RanaFetchError,
    RanaPostError,
    create_tenant_project_directory,
    delete_tenant_project_directory,
    delete_tenant_project_file,
    get_tenant_file_descriptor,
    get_tenant_project_file,
    get_tenant_project_files,
    move_directory,
    move_file,
)
from rana_qgis_plugin.utils.data_models import (
    OpenFileRequest,
    OpenFolderRequest,
    OpenLayerRequest,
    StyleUploadItem,
    UploadableLayerItem,
)
from rana_qgis_plugin.widgets.utils_avatars import AvatarCache
from rana_qgis_plugin.workers.avatars import AvatarWorker
from rana_qgis_plugin.workers.download import (
    BaseDownloader,
    DownloadTask,
    FileDownloadContext,
    RanaFileDownloader,
)
from rana_qgis_plugin.workers.styling import StyleUploadTask
from rana_qgis_plugin.workers.upload import (
    ExistingUploadStatus,
    FileUploadTask,
    ShapefileUploadJob,
    UploadJob,
    UploadPreparationResult,
    prepare_existing_file_upload,
    prepare_new_file_upload,
)


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
    item_renamed = pyqtSignal(
        str, str, str, bool
    )  # old_path, new_path, project_id, is_folder
    item_deleted = pyqtSignal(str, str, bool)  # path, project_id, is_folder

    def __init__(self, communication: "UICommunication", parent=None):
        super().__init__(parent)
        self.avatar_cache = AvatarCache()
        self.avatar_cache.avatar_changed.connect(self.on_avatar_changed)
        self.communication = communication
        self.layer_lock_registry = LayerLockRegistry()
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
        """Rename a file or folder on Rana.

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
                parent = PurePosixPath(source).parent
                parent_path = (
                    parent.as_posix() + "/" if parent != PurePosixPath(".") else ""
                )
                if Loader.folder_exists_in(project_id, parent_path, new_name):
                    return f"Folder '{new_name}' already exists."
                move_directory(
                    project_id,
                    params={
                        "source_path": source + "/",
                        "destination_path": new_path + "/",
                    },
                )
            else:
                if get_tenant_project_file(project_id, {"path": new_path}) is not None:
                    return f"File '{new_name}' already exists."
                move_file(
                    project_id,
                    params={"source_path": old_path, "destination_path": new_path},
                )
        except NetworkUnavailableError:
            return "No connection to Rana."
        except (RanaFetchError, RanaPostError) as e:
            return e.msg

        self.item_renamed.emit(old_path, new_path, project_id, is_folder)
        return None

    def delete_file(self, project_id: str, path: str) -> str | None:
        """Delete a file on Rana.

        Returns None on success, or an error message string on failure.
        """
        try:
            delete_tenant_project_file(project_id, params={"path": path})
        except NetworkUnavailableError:
            return "No connection to Rana."
        except RanaPostError as e:
            return e.msg

        self.item_deleted.emit(path, project_id, False)
        return None

    def delete_folder(self, project_id: str, path: str) -> str | None:
        """Delete a folder on Rana.

        Returns None on success, or an error message string on failure.
        """
        try:
            success = delete_tenant_project_directory(project_id, params={"path": path})
        except NetworkUnavailableError:
            return "No connection to Rana."
        if not success:
            return "Failed to delete folder."

        self.item_deleted.emit(path, project_id, True)
        return None

    def create_folder(self, project_id: str, parent_path: str, name: str) -> str | None:
        """Create a folder on Rana. Emits folder_created on success.

        Returns None on success, or an error message string on failure.
        """
        full_path = f"{parent_path}{name}/" if parent_path else f"{name}/"
        try:
            if Loader.folder_exists_in(project_id, parent_path, name):
                return f"Folder '{name}' already exists."
            success = create_tenant_project_directory(project_id, full_path)
        except NetworkUnavailableError:
            return "No connection to Rana."
        except RanaFetchError as e:
            return e.msg
        if not success:
            return "Failed to create folder."

        return None

    @staticmethod
    def folder_exists_in(project_id: str, parent_path: str, name: str) -> bool:
        """Check whether a folder with *name* already exists inside *parent_path*."""
        params = {"path": parent_path} if parent_path else None
        children = get_tenant_project_files(project_id, params=params)
        return any(
            child["type"] == "directory"
            and child["id"].rstrip("/").rsplit("/", 1)[-1] == name
            for child in children
        )

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
        task = FileUploadTask(jobs)
        task.file_failed.connect(self.handle_upload_file_failed)
        task.file_started.connect(
            lambda file_name: self.set_progress_bar_busy(f"Downloading {file_name}")
        )
        task.taskCompleted.connect(
            lambda: self.handle_upload_completed(
                True, refresh_callback=refresh_callback
            )
        )
        task.taskTerminated.connect(lambda: self.handle_upload_completed(False, task))
        task_manager.addTask(task)

    @pyqtSlot(str, str)
    def handle_upload_file_failed(self, local_path: str, error: str) -> None:
        """Log an individual upload failure reported by the task."""
        self.communication.log_err(f"Failed to upload {local_path}: {error}")

    def handle_upload_completed(
        self,
        success: bool,
        task: FileUploadTask | None = None,
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

    def upload_existing_files(self, items: list[UploadableLayerItem]) -> None:
        """Prepare and upload linked Rana files as one background task."""
        # Verify targets exist before preparing uploads. The lazy guard
        # clears refs and warns the user if a file was deleted remotely.
        verified_items: list[UploadableLayerItem] = []
        for item in items:
            layers = self.layers_for_keys(
                [
                    (
                        item.rana_ref.project_id,
                        item.rana_ref.descriptor_id or item.rana_ref.file_id,
                    )
                ]
            )
            if self.verify_data_target(item, layers):
                verified_items.append(item)
        if not verified_items:
            return

        jobs: list[UploadJob] = []
        conflicts: list[tuple[UploadableLayerItem, UploadPreparationResult]] = []
        errors: list[str] = []
        for item in verified_items:
            ref = item.rana_ref
            result = prepare_existing_file_upload(
                {"id": ref.project_id, "name": item.project_name},
                {"id": ref.file_id, "descriptor_id": ref.descriptor_id},
                local_file=item.local_file_path,
            )
            if result.status == ExistingUploadStatus.REMOTE_NEWER:
                conflicts.append((item, result))
                continue
            if result.error:
                errors.append(f"{item.layer_name}: {result.error}")
            if result.job is not None:
                jobs.append(result.job)
        for error in errors:
            self.communication.log_err(error)
        if errors:
            if len(items) == 1:
                message = errors[0]
            else:
                message = f"{len(errors)} files could not be uploaded due to errors, check the logs for details."
            self.communication.show_warn(message)
        overwrite_all = False
        for item, result in conflicts:
            conflict = result.conflict
            if not overwrite_all:
                if conflict is None:
                    continue
                choices = [UploadChoice.SKIP.value, UploadChoice.OVERWRITE.value]
                if len(conflicts) > 1:
                    choices.append(UploadChoice.OVERWRITE_ALL.value)
                choices.append(UploadChoice.ABORT.value)
                choice = UploadChoice(
                    self.communication.custom_ask(
                        None, "File conflict", conflict, *choices
                    )
                )
                if choice == UploadChoice.ABORT:
                    return
                if choice == UploadChoice.SKIP:
                    continue
                overwrite_all = choice == UploadChoice.OVERWRITE_ALL
            ref = item.rana_ref
            result = prepare_existing_file_upload(
                {"id": ref.project_id, "name": item.project_name},
                {"id": ref.file_id, "descriptor_id": ref.descriptor_id},
                local_file=item.local_file_path,
                overwrite=True,
            )
            if result.job is not None:
                jobs.append(result.job)
        if not jobs:
            return
        task_manager = QgsApplication.taskManager()
        if task_manager is None:
            self.communication.bar_error("Could not start file sync.")
            return
        keys = list(
            {
                (
                    item.rana_ref.project_id,
                    item.rana_ref.descriptor_id or item.rana_ref.file_id,
                )
                for item in verified_items
            }
        )
        if not self.acquire_sync_keys(keys):
            self.communication.bar_warn("A sync is already in progress.")
            return

        task = FileUploadTask(jobs)
        task.rana_sync_keys = keys
        task.file_failed.connect(self.handle_upload_file_failed)
        task.file_started.connect(
            lambda name: self.set_progress_bar_busy(f"Uploading {name}")
        )
        task.file_started.connect(
            lambda name: self.communication.log_msg(f"uploading {name}")
        )
        task.taskCompleted.connect(
            lambda: self.handle_sync_completed(
                task,
                DATA_DIRTY_PROPERTY,
                "Data saved to Rana.",
                task.failed_files,
            )
        )
        task.taskCompleted.connect(lambda: self.update_descriptor_ids(task))
        task.taskTerminated.connect(lambda: self.release_sync_keys(task.rana_sync_keys))
        task.taskTerminated.connect(lambda: self.handle_data_sync_terminated(task))
        task_manager.addTask(task)

    def upload_styles(self, items: list[StyleUploadItem]) -> None:
        """Submit a background task for the supplied style uploads."""
        if not items:
            return
        task_manager = QgsApplication.taskManager()
        if task_manager is None:
            self.communication.bar_error("Could not start style upload.")
            return
        keys = list(
            {
                (item.project_id, item.descriptor_id)
                for item in items
                if item.project_id is not None and item.descriptor_id is not None
            }
        )
        if not self.acquire_sync_keys(keys):
            self.communication.bar_warn("A sync is already in progress.")
            return

        for item in items:
            if item.project_id is None or item.descriptor_id is None:
                continue
            layers = self.layers_for_keys([(item.project_id, item.descriptor_id)])
            if not self.verify_style_target(item, layers):
                self.release_sync_keys(keys)
                return
        task = StyleUploadTask(items)
        task.rana_sync_keys = keys
        task.item_started.connect(
            lambda name: self.set_progress_bar_busy(f"Uploading style {name}")
        )
        task.item_failed.connect(
            lambda name, error: self.communication.log_err(
                f"Style upload failed for {name}: {error}"
            )
        )
        task.taskCompleted.connect(
            lambda: self.handle_sync_completed(
                task, STYLE_DIRTY_PROPERTY, "Styles saved to Rana.", task.failed_items
            )
        )
        task.taskTerminated.connect(lambda: self.release_sync_keys(task.rana_sync_keys))
        task.taskTerminated.connect(lambda: self.handle_style_sync_terminated(task))
        task_manager.addTask(task)

    def acquire_sync_keys(self, keys: list[tuple[str, str]]) -> bool:
        acquired: list[tuple[str, str]] = []
        for key in keys:
            if not self.layer_lock_registry.acquire(key):
                self.release_sync_keys(acquired)
                return False
            acquired.append(key)
        return True

    def verify_data_target(self, item: UploadableLayerItem, layers: list) -> bool:
        """Verify that a data-upload target still exists in Rana."""
        try:
            get_tenant_project_file(
                item.rana_ref.project_id,
                {"path": item.rana_ref.file_id},
                raise_on_error=True,
            )
        except NetworkUnavailableError:
            self.communication.bar_warn(
                "Could not verify file exists in Rana — try again."
            )
            return False
        except RanaFetchError as error:
            if error.status_code in (404, 410):
                self.clear_layer_refs(layers)
                self.communication.bar_warn(
                    f"The file '{PurePosixPath(item.rana_ref.file_id).name}' no longer "
                    "exists in Rana — syncing has been disabled for this layer/group."
                )
            else:
                self.communication.bar_warn(
                    "Could not verify file exists in Rana — try again."
                )
            return False
        return True

    def verify_style_target(self, item: StyleUploadItem, layers: list) -> bool:
        """Verify that a style-upload target still exists in Rana."""
        if item.descriptor_id is None:
            return False
        try:
            descriptor = get_tenant_file_descriptor(item.descriptor_id)
            if descriptor is not None:
                status = FileDescriptorStatus.from_fd_response(descriptor)
                if status is not None and not status.is_ready:
                    self.communication.bar_warn(
                        "The file is still being processed by Rana — try again in a moment."
                    )
                    return False
        except NetworkUnavailableError:
            self.communication.bar_warn(
                "Could not verify file exists in Rana — try again."
            )
            return False
        except RanaFetchError as error:
            if error.status_code in (404, 410):
                self.clear_layer_refs(layers)
                self.communication.bar_warn(
                    f"The file '{PurePosixPath(item.file_ref_str.removeprefix('file ')).name}' "
                    "no longer exists in Rana — syncing has been disabled for this layer/group."
                )
            else:
                self.communication.bar_warn(
                    "Could not verify file exists in Rana — try again."
                )
            return False
        return True

    def release_sync_keys(self, keys) -> None:
        for key in keys:
            self.layer_lock_registry.release(key)

    @staticmethod
    def clear_layer_refs(layers: list) -> None:
        for layer in layers:
            clear_rana_refs(layer)

    @staticmethod
    def layers_for_keys(keys: list[tuple[str, str]]) -> list:
        layers: list = []
        project = QgsProject.instance()
        if project is None:
            return layers
        for layer in project.mapLayers().values():
            ref = get_rana_refs(layer)
            if (
                ref is not None
                and (ref.project_id, ref.descriptor_id or ref.file_id) in keys
            ):
                layers.append(layer)
        return layers

    def handle_sync_completed(
        self, task, dirty_property: str, message: str, failures: list
    ) -> None:
        if not failures and not task.isCanceled():
            for layer in self.layers_for_keys(task.rana_sync_keys):
                clear_dirty(layer, dirty_property)
        self.release_sync_keys(task.rana_sync_keys)
        self.communication.clear_message_bar()
        self.communication.bar_info(message)

    def update_descriptor_ids(self, task: FileUploadTask) -> None:
        """Update descriptor_id on linked layers after a successful data upload.

        The Rana backend assigns a new descriptor_id when a file is re-uploaded.
        Without this update, subsequent style uploads would target the stale
        descriptor and be rejected by the server.
        """
        if not task.updated_descriptors:
            return
        for layer in self.layers_for_keys(task.rana_sync_keys):
            ref = get_rana_refs(layer)
            if ref is None:
                continue
            new_descriptor_id = task.updated_descriptors.get(ref.file_id)
            if new_descriptor_id and new_descriptor_id != ref.descriptor_id:
                layer.setCustomProperty("rana/descriptor_id", new_descriptor_id)

    def handle_data_sync_terminated(self, task) -> None:
        self.handle_upload_completed(False, task)

    def handle_style_sync_terminated(self, task) -> None:
        self.handle_style_upload_terminated(task)

    def handle_style_upload_terminated(self, task) -> None:
        """Report whether a style task was cancelled or failed."""
        self.communication.clear_message_bar()
        if task.isCanceled():
            self.communication.bar_warn("Style upload cancelled.")
        else:
            self.communication.bar_error("Style upload failed.")

    def open_items(
        self,
        requests: list[OpenFileRequest | OpenLayerRequest | OpenFolderRequest],
    ) -> None:
        """Resolve, confirm, download and open Rana files/layers.

        Folder requests are resolved via the API into file requests (single
        level). Downloads are de-duplicated by (project_id, file_id) — multiple
        layer requests for the same file result in one download. Shows a
        confirmation dialog when the download count exceeds 10 or hits the
        limit. Creates one DownloadTask for the entire batch.
        """
        MAX_DOWNLOADS = 50
        # Step 1: Expand folder requests into file requests
        file_requests: list[OpenFileRequest | OpenLayerRequest] = []
        for request in requests:
            if isinstance(request, OpenFolderRequest):
                self.resolve_folder(request.project, request.folder_path, file_requests)
            elif isinstance(request, (OpenFileRequest, OpenLayerRequest)):
                data_type = request.file_item.get("data_type", "")
                if data_type in ("vector", "raster"):
                    file_requests.append(request)

        if not file_requests:
            return

        # Step 2: Build downloaders — one per unique file, multiple callbacks
        downloaders: list[BaseDownloader] = []
        open_callbacks: dict[str, list[Callable[[str], None]]] = {}
        seen_files: set[tuple[str, str]] = set()

        for request in file_requests:
            project = request.project
            file_item = request.file_item
            file_key = (project["id"], file_item["id"])

            context = FileDownloadContext(
                project_slug=project.get("slug", ""),
                file_id=file_item["id"],
                file_descriptor_id=file_item.get("descriptor_id") or "",
                file_data_type=file_item.get("data_type", ""),
            )
            local_path = str(context.local_file_path)

            if file_key not in seen_files:
                if len(seen_files) >= MAX_DOWNLOADS:
                    break
                seen_files.add(file_key)
                downloader = RanaFileDownloader(project, file_item, context)
                try:
                    downloader.resolve_url()
                except (NetworkUnavailableError, RanaFetchError) as e:
                    self.communication.bar_error(
                        f"Could not resolve download URL for "
                        f"{PurePosixPath(file_item['id']).name}: {e}"
                    )
                    continue
                downloaders.append(downloader)
                open_callbacks[local_path] = []

            if isinstance(request, OpenLayerRequest):

                def _make_layer_cb(
                    p: dict, fi: dict, ln: str, lid: str | None
                ) -> Callable[[str], None]:
                    return lambda lp: self.open_layer(lp, p, fi, ln, lid)

                open_callbacks[local_path].append(
                    _make_layer_cb(
                        project,
                        file_item,
                        request.layer_name,
                        request.layer_id,
                    )
                )
            else:

                def _make_file_cb(p: dict, fi: dict) -> Callable[[str], None]:
                    return lambda lp: self.open_file(lp, p, fi)

                open_callbacks[local_path].append(_make_file_cb(project, file_item))

        if not downloaders:
            return

        # Step 3: Confirm if many downloads
        n_downloads = len(downloaders)
        hit_limit = len(seen_files) >= MAX_DOWNLOADS
        if n_downloads > 10 or hit_limit:
            if hit_limit:
                message = (
                    f"This selection resolved to more than {MAX_DOWNLOADS} "
                    f"files. Open the first {n_downloads}?"
                )
            else:
                message = f"This will download {n_downloads} files. Continue?"

            answer = QMessageBox.question(
                None,
                "Open in QGIS",
                message,
                QMessageBox.StandardButton.Yes,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        # Step 4: Submit one DownloadTask
        task_manager = QgsApplication.taskManager()
        if task_manager is None:
            self.communication.bar_error("Could not start file download.")
            return

        task = DownloadTask(list(downloaders))
        task.file_started.connect(
            lambda file_id: self.set_progress_bar_busy(
                f"Downloading {PurePosixPath(file_id).name}"
            )
        )
        task.file_failed.connect(self.handle_download_file_failed)
        task.file_downloaded.connect(
            lambda local_path: self._on_file_downloaded(local_path, open_callbacks)
        )
        task.file_downloaded.connect(
            lambda local_path: self.communication.log_msg(f"downloaded {local_path}")
        )
        task.taskCompleted.connect(self.communication.clear_message_bar)
        task.taskTerminated.connect(lambda: self.handle_download_terminated(task))
        task_manager.addTask(task)

    def resolve_folder(
        self,
        project: dict,
        folder_path: str,
        resolved: list[OpenFileRequest | OpenLayerRequest],
    ) -> None:
        """Resolve a folder into OpenFileRequests via the API (single level)."""
        params = {"path": folder_path} if folder_path else None
        try:
            files = get_tenant_project_files(project["id"], params=params)
        except (NetworkUnavailableError, RanaFetchError) as e:
            self.communication.bar_error(f"Could not list folder contents: {e}")
            return

        for item in files:
            if item.get("type") == "directory":
                continue
            data_type = item.get("data_type", "")
            if data_type in ("vector", "raster"):
                resolved.append(OpenFileRequest(project=project, file_item=item))

    def open_file(self, local_file_path: str, project: dict, file_item: dict) -> None:
        ref = RanaLayerRef(
            project_id=project["id"],
            file_id=file_item["id"],
            descriptor_id=file_item.get("descriptor_id"),
        )
        parents = [project["name"], "files"] + file_item["id"].split("/")

        if file_item.get("data_type") == "vector":
            layer_names = get_vector_layer_names(local_file_path)
            open_rana_vector_layers(local_file_path, layer_names, parents, ref)
        else:
            open_rana_raster(local_file_path, parents, ref)

        self._store_server_timestamp(project["name"], file_item)

    def open_layer(
        self,
        local_file_path: str,
        project: dict,
        file_item: dict,
        layer_name: str,
        layer_id: str | None = None,
    ) -> None:
        ref = RanaLayerRef(
            project_id=project["id"],
            file_id=file_item["id"],
            descriptor_id=file_item.get("descriptor_id"),
            layer_id=layer_id,
        )
        parents = [project["name"], "files"] + file_item["id"].split("/")
        open_rana_vector_layer(local_file_path, layer_name, parents, ref)
        self._store_server_timestamp(project["name"], file_item)

    @staticmethod
    def _store_server_timestamp(project_name: str, file_item: dict) -> None:
        """Record the server's last_modified so conflict detection works on upload."""
        last_modified = file_item.get("last_modified")
        if last_modified is not None:
            key = f"{project_name}/{file_item['id']}/last_modified"
            QSettings().setValue(key, last_modified)

    def _on_file_downloaded(
        self,
        local_file_path: str,
        open_callbacks: dict[str, list[Callable[[str], None]]],
    ) -> None:
        """Called per file when download completes. Invokes all matching callbacks."""
        callbacks = open_callbacks.get(local_file_path, [])
        for callback in callbacks:
            callback(local_file_path)

    @pyqtSlot(str)
    def set_progress_bar_busy(self, message: str) -> None:
        """Show a marquee progress bar with the given message."""
        self.communication.progress_bar(message, minimum=0, maximum=0)

    @pyqtSlot(str, str)
    def handle_download_file_failed(self, file_id: str, error: str) -> None:
        filename = PurePosixPath(file_id).name
        self.communication.bar_error(f"Failed to download {filename}: {error}")

    def handle_download_terminated(self, task: DownloadTask) -> None:
        if task.isCanceled():
            self.communication.bar_warn("File download cancelled.")
        elif task.failed_files:
            for file_id, error in task.failed_files:
                self.communication.log_err(f"Download terminated - {file_id}: {error}")
            self.communication.bar_error("File download failed.")
        else:
            self.communication.bar_error("File download failed (unknown reason).")
