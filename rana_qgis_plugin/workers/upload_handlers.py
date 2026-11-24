"""Handlers that wire the progress and terminal messages of schematisation uploads."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import TYPE_CHECKING

from rana_qgis_plugin.api_error_signals import ApiErrorSignals
from rana_qgis_plugin.communication import (
    finish_progress,
    update_progress,
    update_step_progress,
)
from rana_qgis_plugin.network_manager import NetworkUnavailableError
from rana_qgis_plugin.simulation.workers import SchematisationUploadTask
from rana_qgis_plugin.utils.api import RanaFetchError, get_tenant_project

if TYPE_CHECKING:
    from rana_qgis_plugin.loader import Loader


class UploadHandler(ABC):
    """Shared wiring for an upload task.

    Subclasses supply the flow-specific hooks. The handler keeps the state the
    callbacks share, so no closure needs `nonlocal`. `attach` stores the handler
    on the task, so it lives as long as the task; without that reference PyQt
    would silently stop calling the slots once the handler is garbage-collected.
    """

    def __init__(self, task: SchematisationUploadTask, progress_bar) -> None:
        self.task = task
        self.progress_bar = progress_bar
        self.handed_off = False

    def attach(self) -> None:
        self.task._upload_handler = self
        self.connect()

    def connect(self) -> None:
        self.task.progress_changed.connect(self.on_upload_progress)
        self.task.model_requested.connect(self.on_model_requested)
        self.task.upload_succeeded.connect(self.on_upload_succeeded)
        self.task.taskTerminated.connect(self.on_task_terminated)

    def on_upload_progress(self, name, current, total, per_task) -> None:
        # Queued ticks can arrive after the hand-off and the bar is gone by then.
        if self.handed_off:
            return
        self.show_progress(name, total + current * per_task / 100)

    def on_model_requested(self) -> None:
        self.handed_off = True
        self.start_model_creation()

    @abstractmethod
    def show_progress(self, name: str, value: float) -> None: ...

    @abstractmethod
    def start_model_creation(self) -> None: ...

    @abstractmethod
    def on_upload_succeeded(self, revision_number: int) -> None: ...

    @abstractmethod
    def on_task_terminated(self) -> None: ...


class InitialRevisionUploadHandler(UploadHandler):
    """Progress and messages for the initial revision of a new schematisation."""

    def __init__(
        self,
        loader: Loader,
        task: SchematisationUploadTask,
        project: dict,
        schematisation,
        progress_bar,
        error_signals: ApiErrorSignals,
        display_name: str,
        refresh_callback: Callable[[], None],
    ) -> None:
        super().__init__(task, progress_bar)
        self.loader = loader
        self.project = project
        self.schematisation = schematisation
        self.error_signals = error_signals
        self.display_name = display_name
        self.refresh_callback = refresh_callback

    def show_progress(self, name: str, value: float) -> None:
        update_step_progress(
            self.progress_bar, 1, value, detail=f"Uploading revision: {name}"
        )

    def start_model_creation(self) -> None:
        self.loader.handle_initial_model_requested(
            self.project,
            self.schematisation,
            self.task.revision.id,
            self.task.upload_specification["cb_inherit_templates"],
            self.progress_bar,
            self.error_signals,
            self.display_name,
        )

    def on_upload_succeeded(self, _revision_number: int) -> None:
        self.refresh_callback()

    def on_task_terminated(self) -> None:
        self.loader.handle_initial_revision_upload_failure(self.task, self.progress_bar)


class RevisionUploadHandler(UploadHandler):
    """Progress and messages for a revision uploaded to an existing schematisation."""

    def __init__(
        self,
        loader: Loader,
        task: SchematisationUploadTask,
        progress_bar,
        project_id: str,
        schematisation_id: int,
        schematisation_name: str,
        error_signals: ApiErrorSignals,
        project: dict | None,
        on_finished: Callable[[], None],
    ) -> None:
        super().__init__(task, progress_bar)
        self.loader = loader
        self.project_id = project_id
        self.schematisation_id = schematisation_id
        self.schematisation_name = schematisation_name
        self.error_signals = error_signals
        self.project = project
        self.on_finished = on_finished

    def connect(self) -> None:
        super().connect()
        self.task.taskCompleted.connect(self.on_finished)
        self.task.taskTerminated.connect(self.on_finished)

    def show_progress(self, name: str, value: float) -> None:
        label = (
            "Waiting for model checker"
            if name == "MAKE MODEL"
            else f"Uploading revision: {name}"
        )
        update_progress(self.progress_bar, value, detail=label)

    def start_model_creation(self) -> None:
        finish_progress(self.loader.communication.iface, self.progress_bar)
        response = self.loader.start_model_tracker_process(
            self.project_id,
            self.schematisation_id,
            self.schematisation_name,
            self.task.revision.id,
            self.task.upload_specification["cb_inherit_templates"],
        )
        if response is None:
            return
        job_id = response.get("job_id") or response.get("id")
        process_project = self.project
        if job_id and process_project is None:
            try:
                process_project = get_tenant_project(self.project_id)
            except (RanaFetchError, NetworkUnavailableError):
                pass
        self.loader.point_user_to_model_creation(
            process_project, job_id, self.error_signals, self.schematisation_name
        )

    def on_upload_succeeded(self, revision_number: int) -> None:
        if self.handed_off:
            return
        finish_progress(self.loader.communication.iface, self.progress_bar)
        self.loader.communication.bar_info(f"Revision {revision_number} uploaded.")

    def on_task_terminated(self) -> None:
        communication = self.loader.communication
        finish_progress(communication.iface, self.progress_bar)
        if self.task.isCanceled():
            communication.bar_warn("Revision upload cancelled.")
        elif self.task.committed_revision is not None:
            communication.bar_error(
                f"Revision {self.task.committed_revision} was uploaded, but no model was created: "
                f"{self.task.error_message}"
            )
        else:
            communication.bar_error(
                f"Revision upload failed: {self.task.error_message}"
            )
