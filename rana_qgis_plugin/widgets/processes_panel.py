import html
from typing import TYPE_CHECKING, Any, cast

from qgis.core import QgsApplication
from qgis.PyQt.QtCore import (
    QAbstractTableModel,
    QItemSelectionModel,
    QModelIndex,
    QSize,
    Qt,
    QTimer,
)
from qgis.PyQt.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QTextEdit,
    QToolButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)
from threedi_mi_utils.ui import ColoredProgressBar

from rana_qgis_plugin.api_error_signals import ApiErrorSignals
from rana_qgis_plugin.network_manager import (
    NetworkTimeoutError,
    NetworkUnavailableError,
)
from rana_qgis_plugin.simulation.threedi_calls import ThreediCalls
from rana_qgis_plugin.utils.api import (
    RanaFetchError,
    get_job_logs,
    get_process_id_for_tag,
)
from rana_qgis_plugin.utils.generic import get_threedi_api
from rana_qgis_plugin.utils.settings import base_url, get_tenant_id
from rana_qgis_plugin.utils.time import format_activity_timestamp_str
from rana_qgis_plugin.widgets.filter_bar import (
    ComboFilterConfig,
    FilterBar,
    TextFilterConfig,
)
from rana_qgis_plugin.widgets.utils_avatars import AvatarCache
from rana_qgis_plugin.widgets.jobs_models import (
    JobData,
    JobParseError,
    job_can_be_cancelled,
)
from rana_qgis_plugin.workers.rana_jobs import JobsFetchTask

_HEADERS = ["Name", "Process name", "Who", "Started", "Status"]


class ProcessProgressBar(ColoredProgressBar):
    """Progress bar colored by Rana job state."""

    def set_status(self, status: str) -> None:
        if status == "completed":
            color = self.COLOR_FINISHED
        elif status in {"scheduled", "pending", "paused", "cancelling", "running"}:
            color = self.COLOR_RUNNING
        else:
            self.set_failed()
            return
        self.setStyleSheet(f"QProgressBar::chunk {{ background-color: {color}; }}")


def apply_job_progress(progress_bar: ProcessProgressBar, job: JobData) -> None:
    """Apply job progress and status styling to a progress bar."""
    progress_bar.setValue(job.progress)
    progress_bar.setMaximum(job.max_progress)
    progress_bar.setFormat(job.progress_str())
    progress_bar.set_status(job.status)


class JobsTableModel(QAbstractTableModel):
    """Table model that reconciles refreshed jobs by stable job ID."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._jobs: list[JobData] = []
        self._highlighted_job_ids: set[str | int] = set()

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._jobs)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(_HEADERS)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role=Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
        ):
            return _HEADERS[section]
        return None

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        job = self._jobs[index.row()]
        if (
            role == Qt.ItemDataRole.BackgroundRole
            and job.id in self._highlighted_job_ids
        ):
            return QApplication.palette().highlight()
        if role == Qt.ItemDataRole.UserRole:
            return job
        if role == Qt.ItemDataRole.DisplayRole:
            if index.column() in {0, 2, 4}:
                return ""
            return (
                job.name,
                job.process_name or "",
                job.user_name,
                format_activity_timestamp_str(job.created),
                job.progress_str(),
            )[index.column()]
        if role == Qt.ItemDataRole.ToolTipRole and index.column() == 1:
            return job.process_name or ""
        if role == Qt.ItemDataRole.TextAlignmentRole and index.column() == 3:
            return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        return None

    def job_at(self, row: int) -> JobData:
        return self._jobs[row]

    def job_for_id(self, job_id: str | int) -> JobData | None:
        return next((job for job in self._jobs if job.id == job_id), None)

    def job_id_at(self, row: int) -> str | int:
        return self._jobs[row].id

    def set_job_status(self, job_id: str | int, status: str) -> None:
        """Update a job's status and notify views of the changed row."""
        for row, job in enumerate(self._jobs):
            if job.id == job_id:
                job.status = status
                self.dataChanged.emit(
                    self.index(row, 0),
                    self.index(row, self.columnCount() - 1),
                    [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.UserRole],
                )
                return

    def set_highlighted_job_ids(self, job_ids: set[str | int]) -> None:
        """Set rows to show a temporary highlight background."""
        changed_ids = self._highlighted_job_ids | job_ids
        self._highlighted_job_ids = set(job_ids)
        self._emit_background_changed(changed_ids)

    def highlighted_job_ids(self) -> set[str | int]:
        """Return the currently highlighted job IDs."""
        return set(self._highlighted_job_ids)

    def clear_highlighted_job_ids(self) -> None:
        """Clear temporary row highlights."""
        changed_ids = self._highlighted_job_ids
        self._highlighted_job_ids.clear()
        self._emit_background_changed(changed_ids)

    def _emit_background_changed(self, job_ids: set[str | int]) -> None:
        for row, job in enumerate(self._jobs):
            if job.id in job_ids:
                self.dataChanged.emit(
                    self.index(row, 0),
                    self.index(row, self.columnCount() - 1),
                    [Qt.ItemDataRole.BackgroundRole],
                )

    def update_jobs(self, jobs: list[JobData]) -> None:
        """Reconcile jobs incrementally, preserving the API response order."""
        incoming_by_id = {job.id: job for job in jobs}

        for row in range(len(self._jobs) - 1, -1, -1):
            if self._jobs[row].id not in incoming_by_id:
                self.beginRemoveRows(QModelIndex(), row, row)
                self._jobs.pop(row)
                self.endRemoveRows()

        for target_row, job in enumerate(jobs):
            existing_row = next(
                (row for row, current in enumerate(self._jobs) if current.id == job.id),
                None,
            )
            if existing_row is None:
                self.beginInsertRows(QModelIndex(), target_row, target_row)
                self._jobs.insert(target_row, job)
                self.endInsertRows()
                continue

            old_job = self._jobs[existing_row]
            if existing_row != target_row:
                destination = (
                    target_row if target_row < existing_row else target_row + 1
                )
                if self.beginMoveRows(
                    QModelIndex(),
                    existing_row,
                    existing_row,
                    QModelIndex(),
                    destination,
                ):
                    moved_job = self._jobs.pop(existing_row)
                    self._jobs.insert(target_row, moved_job)
                    self.endMoveRows()

            if old_job != job:
                self._jobs[target_row] = job
                self.dataChanged.emit(
                    self.index(target_row, 0),
                    self.index(target_row, self.columnCount() - 1),
                    [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.UserRole],
                )


class ProcessesPanel(QWidget):
    """Project-scoped Processes UI and polling lifecycle."""

    def __init__(
        self,
        project: dict,
        error_signals: ApiErrorSignals,
        avatar_cache: AvatarCache | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.project = project
        self.error_signals = error_signals
        self.avatar_cache = avatar_cache or AvatarCache()
        try:
            self.simulation_tracker_process_id = get_process_id_for_tag(
                "simulation_tracker"
            )
        except (RanaFetchError, NetworkUnavailableError) as error:
            self.simulation_tracker_process_id = None
            self._report_fetch_error(error)
        self.model = JobsTableModel(self)
        self.filter_bar = FilterBar(
            [
                TextFilterConfig(key="name", placeholder="Search by name"),
                ComboFilterConfig(key="who", placeholder="All contributors"),
                ComboFilterConfig(
                    key="status",
                    placeholder="All statuses",
                    dynamic=False,
                    items=[
                        ("Scheduled", "scheduled"),
                        ("Pending", "pending"),
                        ("Running", "running"),
                        ("Completed", "completed"),
                        ("Failed", "failed"),
                        ("Cancelled", "cancelled"),
                        ("Crashed", "crashed"),
                        ("Paused", "paused"),
                        ("Cancelling", "cancelling"),
                    ],
                ),
            ],
            parent=self,
        )
        self.table = QTreeView(self)
        self.table.setRootIsDecorated(False)
        self.table.setModel(self.model)
        self.table.setEditTriggers(QTreeView.EditTrigger.NoEditTriggers)
        self.table.setUniformRowHeights(True)
        self.table.setWordWrap(False)
        self.table.setTextElideMode(Qt.TextElideMode.ElideRight)
        header = self.table.header()
        if header is not None:
            header.setStretchLastSection(False)
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(2, 36)
        self.table.setColumnWidth(4, 200)
        self.logs = QTextEdit(self)
        self.logs.setReadOnly(True)
        self.logs.setPlaceholderText("Select a job to view its logs.")

        layout = QVBoxLayout(self)
        layout.addWidget(self.filter_bar)
        layout.addWidget(self.table)
        layout.addWidget(self.logs)

        self._current_task: JobsFetchTask | None = None
        self._filters: dict = {}
        self._fetch_requested = False
        self._highlight_job_ids: set[str | int] = set()
        self._logs_job_id: str | int | None = None
        self._highlight_timer = QTimer(self)
        self._highlight_timer.setSingleShot(True)
        self._highlight_timer.setInterval(30_000)
        self._highlight_timer.timeout.connect(self.model.clear_highlighted_job_ids)
        self._stopped = False
        self._visible = False
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(10_000)
        self._poll_timer.timeout.connect(self._poll_jobs)
        self.filter_bar.filters_changed.connect(self._on_filters_changed)
        selection_model = self.table.selectionModel()
        if selection_model is not None:
            selection_model.selectionChanged.connect(self._on_selection_changed)
        self.model.dataChanged.connect(self._update_row_widgets)
        self.model.rowsInserted.connect(self._update_all_row_widgets)
        self.model.rowsMoved.connect(self._update_all_row_widgets)
        self.model.rowsRemoved.connect(self._update_all_row_widgets)

    @property
    def polling(self) -> bool:
        """Whether the panel's scheduled polling timer is active."""
        return self._poll_timer.isActive()

    @property
    def current_task(self) -> JobsFetchTask | None:
        """The active job fetch, if one is in progress."""
        return self._current_task

    def start_polling(self) -> None:
        """Start periodic polling and request an initial fetch."""
        if self._stopped or self._poll_timer.isActive():
            return
        self._poll_timer.start()
        self._request_fetch()

    def stop_polling(self) -> None:
        """Stop future polls and ignore any in-flight result."""
        self._stopped = True
        self._poll_timer.stop()
        self._fetch_requested = False

    def _on_filters_changed(self, filters: dict) -> None:
        self._filters = self._api_filters(filters)
        self._request_fetch()

    @staticmethod
    def _api_filters(filters: dict) -> dict:
        params = {}
        search = filters.get("name")
        created_by = filters.get("who")
        status = filters.get("status")
        if search:
            params["search"] = search
        if created_by:
            params["created_by"] = created_by
        if status:
            params["status"] = status
        return params

    def _poll_jobs(self) -> None:
        if not self._stopped and self._visible:
            self._request_fetch(fetch_after_active=False)

    def _request_fetch(self, fetch_after_active: bool = True) -> None:
        if self._stopped or not self._visible:
            return
        if self._current_task is not None:
            if fetch_after_active:
                self._fetch_requested = True
            return

        task = JobsFetchTask(self.project["id"], self._filters)
        self._current_task = task
        task.taskCompleted.connect(lambda task=task: self._fetch_completed(task))
        task.taskTerminated.connect(lambda task=task: self._fetch_terminated(task))
        task_manager = QgsApplication.taskManager()
        if task_manager is None:
            self._current_task = None
            return
        task_manager.addTask(task)

    def _fetch_completed(self, task: JobsFetchTask) -> None:
        if task is not self._current_task:
            return
        self._current_task = None
        if not self._stopped and self._visible and task.error is None:
            if task.params != self._filters:
                self._fetch_requested = True
            elif task.result is not None:
                jobs: list[JobData] = []
                for item in task.result.get("items", []):
                    try:
                        jobs.append(JobData.from_job_dict(item))
                    except JobParseError as error:
                        self.error_signals.fetch_error_occurred.emit(
                            f"Could not read job {item.get('id')} from Rana: {error}",
                            False,
                        )
                self.model.update_jobs(jobs)
                self._update_all_row_widgets()
                self._repopulate_who_combo()
                self._refresh_selected_job_logs()
                if self._highlight_job_ids:
                    requested_ids = self._highlight_job_ids
                    if self._select_and_highlight_jobs(requested_ids):
                        self._highlight_job_ids.clear()
        elif self._stopped or not self._visible:
            self._fetch_requested = False

        self._continue_requested_fetch()

    def highlight_jobs(self, job_ids: list[str]) -> None:
        """Refresh now and temporarily select/highlight matching jobs."""
        self._highlight_job_ids = set(job_ids)
        if self._current_task is not None:
            return
        if not self._visible or self._stopped:
            return
        self._request_fetch()

    def _select_and_highlight_jobs(self, job_ids: set[str | int]) -> bool:
        requested_ids = {str(job_id) for job_id in job_ids}
        rows = [
            row
            for row in range(self.model.rowCount())
            if str(self.model.job_id_at(row)) in requested_ids
        ]
        if not rows:
            return False

        selection_model = self.table.selectionModel()
        if selection_model is None:
            return False
        selection_model.clearSelection()
        for row in rows:
            index = self.model.index(row, 0)
            selection_model.select(
                index,
                cast(
                    QItemSelectionModel.SelectionFlags,
                    QItemSelectionModel.SelectionFlag.Select
                    | QItemSelectionModel.SelectionFlag.Rows,
                ),
            )
        self.table.scrollTo(self.model.index(rows[0], 0))
        self.model.set_highlighted_job_ids({self.model.job_id_at(row) for row in rows})
        self._highlight_timer.start()
        return True

    def _fetch_terminated(self, task: JobsFetchTask) -> None:
        if task is not self._current_task:
            return
        self._current_task = None
        if not self._stopped and self._visible and task.error is not None:
            if task.params == self._filters:
                self._report_fetch_error(task.error)
            else:
                self._fetch_requested = True
        elif self._stopped or not self._visible:
            self._fetch_requested = False
        self._continue_requested_fetch()

    def _continue_requested_fetch(self) -> None:
        if self._fetch_requested and not self._stopped and self._visible:
            self._fetch_requested = False
            self._request_fetch()

    def _report_fetch_error(self, error: Exception) -> None:
        if isinstance(error, NetworkTimeoutError):
            self.error_signals.request_timed_out.emit()
        elif isinstance(error, NetworkUnavailableError):
            self.error_signals.connection_lost.emit()
        elif isinstance(error, RanaFetchError):
            self.error_signals.fetch_error_occurred.emit(str(error), False)

    def _on_selection_changed(self, *_args) -> None:
        self._logs_job_id = None
        self._refresh_selected_job_logs()

    def _refresh_selected_job_logs(self) -> None:
        selection_model = self.table.selectionModel()
        if selection_model is None or not selection_model.hasSelection():
            self._logs_job_id = None
            self.logs.clear()
            self.logs.setPlaceholderText("Select a job to view its logs.")
            return

        selected_rows = selection_model.selectedRows()
        if not selected_rows:
            self._logs_job_id = None
            self.logs.clear()
            self.logs.setPlaceholderText("Select a job to view its logs.")
            return

        job = self.model.job_at(selected_rows[0].row())
        if self._logs_job_id != job.id:
            self.logs.clear()
            self.logs.setPlaceholderText(f"Loading logs for {job.name}…")
            self._logs_job_id = job.id
        try:
            response = get_job_logs(str(job.id))
        except (NetworkTimeoutError, NetworkUnavailableError, RanaFetchError) as error:
            self.logs.setPlaceholderText("Could not load job logs.")
            self._report_fetch_error(error)
            return

        current_selection = self.table.selectionModel()
        if (
            current_selection is None
            or not current_selection.hasSelection()
            or current_selection.selectedRows()[0].row() >= self.model.rowCount()
            or self.model.job_at(current_selection.selectedRows()[0].row()).id != job.id
        ):
            return

        entries = response.get("items", [])
        if not entries:
            self.logs.setPlaceholderText("No logs available for this job.")
            return

        self.logs.setPlaceholderText("")
        rendered_entries = []
        for entry in entries:
            level = entry.get("log_level")
            lines = [
                " | ".join(
                    str(value)
                    for value in (
                        entry.get("timestamp"),
                        level,
                        entry.get("message"),
                    )
                    if value is not None
                )
            ]
            exception = entry.get("exception")
            if isinstance(exception, dict):
                title = exception.get("title")
                description = exception.get("description")
                if title:
                    lines.append(f"Exception: {title}")
                if description:
                    lines.append(str(description))
                if exception.get("traceback"):
                    lines.append(str(exception["traceback"]))
            elif exception:
                lines.append(f"Exception: {exception}")
            rendered_entries.append("\n".join(lines))
        text = "\n\n".join(rendered_entries)
        if self.logs.toPlainText() != text:
            self.logs.setPlainText(text)

    def _repopulate_who_combo(self) -> None:
        contributors = {}
        for row in range(self.model.rowCount()):
            user = self.model.job_at(row).user
            if not isinstance(user, dict):
                continue
            user_id = user.get("id")
            if not isinstance(user_id, (str, int)) or not str(user_id).strip():
                continue
            given_name = user.get("given_name")
            family_name = user.get("family_name")
            given_name = given_name.strip() if isinstance(given_name, str) else ""
            family_name = family_name.strip() if isinstance(family_name, str) else ""
            display_name = (
                " ".join(name for name in (given_name, family_name) if name)
                or "Unknown contributor"
            )
            avatar_user = {
                **user,
                "id": user_id,
                "given_name": given_name or "?",
                "family_name": family_name or "?",
            }
            contributors[user_id] = (display_name, avatar_user)
        ordered_users = sorted(
            contributors.values(), key=lambda item: item[0].casefold()
        )
        self.filter_bar.set_combo_items(
            "who",
            [
                (
                    display_name,
                    user["id"],
                    self.avatar_cache.get_avatar_for_user(user),
                )
                for display_name, user in ordered_users
            ],
        )

    def _update_all_row_widgets(self, *_args) -> None:
        for row in range(self.model.rowCount()):
            self._update_row_widgets(self.model.index(row, 0), self.model.index(row, 4))

    def _update_row_widgets(
        self, top_left: QModelIndex, bottom_right: QModelIndex
    ) -> None:
        for row in range(top_left.row(), bottom_right.row() + 1):
            job = self.model.job_at(row)
            name_index = self.model.index(row, 0)
            name_label = self.table.indexWidget(name_index)
            if name_label is None:
                name_label = QLabel(self.table)
                name_label.setOpenExternalLinks(True)
                name_label.setWordWrap(False)
                self.table.setIndexWidget(name_index, name_label)
            name_label.setToolTip(job.name)
            if job.process_id:
                name_label.setStyleSheet("")
                job_url = html.escape(self._job_url(job), quote=True)
                job_name = html.escape(job.name, quote=True)
                name_label.setText(f'<a href="{job_url}">{job_name}</a>')
            else:
                name_label.setStyleSheet(
                    f"color: {self.table.palette().text().color().name()}"
                )
                name_label.setText(job.name)

            who_index = self.model.index(row, 2)
            who_label = self.table.indexWidget(who_index)
            if who_label is None:
                who_label = QLabel(self.table)
                who_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setIndexWidget(who_index, who_label)
            who_label.setPixmap(self.avatar_cache.get_avatar_for_user(job.user))
            who_label.setToolTip(job.user_name)

            status_index = self.model.index(row, 4)
            status_widget = self.table.indexWidget(status_index)
            if status_widget is None:
                status_widget = QWidget(self.table)
                status_layout = QHBoxLayout(status_widget)
                status_layout.setContentsMargins(0, 0, 0, 0)
                status_layout.setSpacing(4)
                progress_bar = ProcessProgressBar(self.table)
                progress_bar.setFixedWidth(160)
                progress_bar.setTextVisible(True)
                status_layout.addWidget(progress_bar)
                cancel_button = QToolButton(status_widget)
                cancel_button.setToolTip("Cancel simulation")
                cancel_button.setIcon(QgsApplication.getThemeIcon("mTaskCancel.svg"))
                cancel_button.setIconSize(QSize(16, 16))
                cancel_button.setAutoRaise(True)
                cancel_slot = QWidget(status_widget)
                cancel_slot.setFixedWidth(24)
                cancel_layout = QHBoxLayout(cancel_slot)
                cancel_layout.setContentsMargins(0, 0, 0, 0)
                cancel_layout.addWidget(cancel_button)
                cancel_button.clicked.connect(self._cancel_simulation_from_button)
                status_layout.addWidget(cancel_slot)
                status_layout.addStretch(1)
                self.table.setIndexWidget(status_index, status_widget)
            status_layout = status_widget.layout()
            assert status_layout is not None
            progress_item = status_layout.itemAt(0)
            cancel_item = status_layout.itemAt(1)
            assert progress_item is not None and cancel_item is not None
            progress_bar = cast(ProcessProgressBar, progress_item.widget())
            cancel_slot = cast(QWidget, cancel_item.widget())
            cancel_layout = cancel_slot.layout()
            assert cancel_layout is not None
            cancel_item = cancel_layout.itemAt(0)
            assert cancel_item is not None
            cancel_button = cast(QToolButton, cancel_item.widget())
            cancel_button.setProperty("job_id", job.id)
            cancel_button.setVisible(
                job_can_be_cancelled(job, self.simulation_tracker_process_id)
                and "simulation_id" in job.inputs
            )
            apply_job_progress(progress_bar, job)

    def _cancel_simulation_from_button(self, _checked=False) -> None:
        button = self.sender()
        if button is not None:
            self._cancel_simulation(button.property("job_id"))

    def _cancel_simulation(self, job_id: str | int) -> None:
        """Confirm and request shutdown of an eligible simulation job."""
        job = self.model.job_for_id(job_id)
        if job is None or not job_can_be_cancelled(
            job, self.simulation_tracker_process_id
        ):
            return
        if "simulation_id" not in job.inputs:
            return
        if (
            QMessageBox.question(
                self,
                "Cancel Simulation",
                "Are you sure you want to cancel this simulation?",
                cast(
                    QMessageBox.StandardButtons,
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                ),
                QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return

        button = self._cancel_button_for_job(job_id)
        if button is not None:
            button.setEnabled(False)
        try:
            ThreediCalls(get_threedi_api()).create_simulation_action(
                job.inputs["simulation_id"], name="shutdown"
            )
        except Exception as error:
            self.error_signals.fetch_error_occurred.emit(str(error), True)
            if button is not None:
                button.setEnabled(True)
            return

        self.model.set_job_status(job_id, "cancelling")

    def _cancel_button_for_job(self, job_id: str | int) -> QToolButton | None:
        """Return a job row's cancel button, if its status widget is present."""
        for row in range(self.model.rowCount()):
            if self.model.job_id_at(row) == job_id:
                index = self.model.index(row, 4)
                status_widget = self.table.indexWidget(index)
                if status_widget is not None:
                    button = status_widget.findChild(QToolButton)
                    return button
        return None

    def _job_url(self, job: JobData) -> str:
        return (
            f"{base_url()}/{get_tenant_id()}/projects/{self.project['slug']}"
            f"?tab=2&job={job.id}"
        )

    def showEvent(self, a0) -> None:
        super().showEvent(a0)
        self._visible = True
        if not self._stopped:
            self.start_polling()

    def hideEvent(self, a0) -> None:
        self._visible = False
        self._poll_timer.stop()
        self._fetch_requested = False
        super().hideEvent(a0)
