"""Shared dialogs for displaying Rana file and revision history."""

from datetime import datetime

from qgis.core import QgsApplication
from qgis.PyQt.QtCore import Qt, QUrl
from qgis.PyQt.QtGui import (
    QCloseEvent,
    QDesktopServices,
    QShowEvent,
    QStandardItem,
    QStandardItemModel,
)
from qgis.PyQt.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
)

from rana_qgis_plugin.api_error_signals import ApiErrorSignals
from rana_qgis_plugin.network_manager import NetworkUnavailableError
from rana_qgis_plugin.simulation.threedi_calls import ThreediCalls
from rana_qgis_plugin.utils.api import (
    RanaFetchError,
    get_tenant_project_file_history_page,
    get_threedi_schematisation,
)
from rana_qgis_plugin.utils.data_models import OpenSchematisationRequest
from rana_qgis_plugin.utils.generic import get_rana_processes_url, get_threedi_api
from rana_qgis_plugin.utils.time import format_timestamp, parse_timestamp_str
from rana_qgis_plugin.workers.history import HistoryFetchTask, HistoryRow


class MissingThreeDiAuthenticationError(Exception):
    """Raised when revision history needs unavailable 3Di authentication."""


class HistoryDialog(QDialog):
    """Base dialog for asynchronously fetched history tables."""

    def __init__(self, error_signals: ApiErrorSignals, parent=None):
        super().__init__(parent)
        self.error_signals = error_signals
        self._closed = False
        self.current_task: HistoryFetchTask | None = None

        self.table = QTableView(self)
        self.table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        vertical_header = self.table.verticalHeader()
        if vertical_header is not None:
            vertical_header.setVisible(False)
        self.model = QStandardItemModel(self.table)
        self.table.setModel(self.model)

        self.refresh_button = QPushButton("Refresh", self)
        self.refresh_button.clicked.connect(self.refresh)
        self.error_label = QLabel(self)
        self.error_label.setStyleSheet("color: red;")
        self.error_label.setVisible(False)
        self.loading_label = QLabel("Loading history...", self)
        self.loading_label.setVisible(False)

        layout = QVBoxLayout(self)
        layout.addWidget(self.table)
        bottom_layout = QHBoxLayout(self)
        bottom_layout.addWidget(self.loading_label)
        bottom_layout.addWidget(self.error_label)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.refresh_button)
        layout.addLayout(bottom_layout)
        self.resize(900, 550)

    @staticmethod
    def format_history_timestamp(value: object) -> str:
        """Format a history timestamp as local ``YYYY-MM-DD HH:MM`` text."""
        if value is None:
            return ""
        try:
            timestamp = (
                value
                if isinstance(value, datetime)
                else parse_timestamp_str(str(value))
            )
            return format_timestamp(timestamp, "%Y-%m-%d %H:%M")
        except (TypeError, ValueError, OverflowError):
            return str("NA")

    def window_title(self) -> str:
        """Return the dialog window title."""
        raise NotImplementedError

    def column_headers(self) -> list[str]:
        """Return the table column headers."""
        raise NotImplementedError

    def fetch_page(self, cursor: str | None) -> tuple[list[HistoryRow], str | None]:
        """Fetch one history page and return rows with its next cursor."""
        raise NotImplementedError

    def showEvent(self, a0: QShowEvent | None) -> None:
        """Fetch history the first time the dialog is shown."""
        super().showEvent(a0)
        self._closed = False
        self.setWindowTitle(self.window_title())
        self.model.setHorizontalHeaderLabels(self.column_headers())
        self.configure_table_columns()
        self.refresh()

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        """Cancel an in-flight fetch when the dialog closes."""
        self._closed = True
        if self.current_task is not None:
            self.current_task.cancel()
            self.current_task = None
        super().closeEvent(a0)

    def refresh(self) -> None:
        """Start a background fetch and replace the table when it completes."""
        if self.current_task is not None:
            return
        self.refresh_button.setEnabled(False)
        self.error_label.setVisible(False)
        self.loading_label.setVisible(True)
        self.model.removeRows(0, self.model.rowCount())
        self.load_page(None)

    def load_page(self, cursor: str | None) -> None:
        """Start one page fetch for the initial or next cursor."""
        if self.current_task is not None or self._closed:
            return
        self.refresh_button.setEnabled(False)
        self.loading_label.setVisible(True)
        task = HistoryFetchTask(lambda: self.fetch_page(cursor))
        self.current_task = task
        task.taskCompleted.connect(lambda: self.fetch_task_complete(task))
        task.taskTerminated.connect(lambda: self.fetch_task_terminated(task))
        task_manager = QgsApplication.taskManager()
        if task_manager is not None:
            task_manager.addTask(task)
        else:
            self.current_task = None
            self.loading_label.setVisible(False)
            self.refresh_button.setEnabled(True)
            self.show_error("Could not start history request")

    def fetch_task_complete(self, task: HistoryFetchTask) -> None:
        """Apply successful task results on the GUI thread."""
        if task is not self.current_task or self._closed:
            return
        self.current_task = None
        self.loading_label.setVisible(False)
        self.refresh_button.setEnabled(True)
        self.append_rows(task.rows)

    def fetch_task_terminated(self, task: HistoryFetchTask) -> None:
        """Finish a failed or canceled task without applying stale rows."""
        if task is not self.current_task:
            return
        self.current_task = None
        if self._closed:
            return
        self.loading_label.setVisible(False)
        self.refresh_button.setEnabled(True)
        if task.error is not None:
            self.show_fetch_error(task.error)

    def append_rows(self, rows: list[HistoryRow]) -> None:
        """Append one fetched page to the table on the GUI thread."""
        self.model.setHorizontalHeaderLabels(self.column_headers())
        row_numbers = []
        for row in rows:
            row_number = self.model.rowCount()
            items = [QStandardItem(value) for value in row.values]
            message_column = self.message_column()
            if message_column is not None and message_column < len(items):
                items[message_column].setToolTip(row.values[message_column])
            self.model.appendRow(items)
            if row.metadata:
                items[0].setData(row.metadata, Qt.ItemDataRole.UserRole)
            row_numbers.append((row_number, row))
        self.configure_table_columns()
        for row_number, row in row_numbers:
            self.configure_row_widgets(row_number, row)

    def configure_row_widgets(self, row_number: int, row: HistoryRow) -> None:
        """Add optional GUI-thread row widgets for a history row."""

    def message_column(self) -> int | None:
        """Return the message column index, if this dialog has one."""
        return None

    def show_fetch_error(self, error: Exception) -> None:
        """Route expected fetch errors through the existing UI contract."""
        if isinstance(error, NetworkUnavailableError):
            self.error_signals.connection_lost.emit()
            self.show_error("No connection to Rana")
        elif isinstance(error, RanaFetchError):
            self.error_signals.fetch_error_occurred.emit(str(error), False)
            self.show_error(f"Failed to load history: {error}")
        elif isinstance(error, MissingThreeDiAuthenticationError):
            self.show_error(str(error))
        else:
            self.show_error(f"Failed to load history: {error}")

    def configure_table_columns(self) -> None:
        """Size metadata columns to their contents and stretch the last one."""
        header = self.table.horizontalHeader()
        column_count = self.model.columnCount()
        if header is None or column_count < 3:
            return
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(column_count - 1, QHeaderView.ResizeMode.Stretch)

    def show_error(self, message: str) -> None:
        """Display an inline error while keeping Refresh available."""
        self.error_label.setText(message)
        self.error_label.setVisible(True)


class RanaHistoryDialog(HistoryDialog):
    """Display generic Rana history for a project path or the project."""

    def __init__(
        self,
        project_id: str,
        path: str,
        error_signals: ApiErrorSignals,
        parent=None,
    ):
        self.project_id = project_id
        self.path = path
        self.next_cursor: str | None = None
        super().__init__(error_signals, parent)
        scrollbar = self.table.verticalScrollBar()
        if scrollbar is not None:
            scrollbar.valueChanged.connect(self.load_next_page)
            scrollbar.rangeChanged.connect(self.load_next_page)

    def refresh(self) -> None:
        """Restart generic history from the first cursor page."""
        self.next_cursor = None
        super().refresh()

    def fetch_task_complete(self, task: HistoryFetchTask) -> None:
        """Store the next cursor before applying the fetched rows."""
        self.next_cursor = task.next_cursor
        super().fetch_task_complete(task)

    def load_next_page(self, *_args: int) -> None:
        """Fetch the next page when the user reaches the table bottom."""
        scrollbar = self.table.verticalScrollBar()
        if (
            scrollbar is None
            or scrollbar.value() < scrollbar.maximum()
            or self.next_cursor is None
            or self.current_task is not None
            or self._closed
        ):
            return
        cursor = self.next_cursor
        self.next_cursor = None
        self.load_page(cursor)

    def window_title(self) -> str:
        """Return the generic history dialog title."""
        return "History"

    def column_headers(self) -> list[str]:
        """Return the generic history columns."""
        return ["Timestamp", "User", "Message"]

    def message_column(self) -> int | None:
        """Return the generic history message column."""
        return 2

    @staticmethod
    def format_user(user: dict | None) -> str:
        """Format a Rana API committed-by user object."""
        if not user:
            return "Unknown"
        name = " ".join(
            part for part in (user.get("given_name"), user.get("family_name")) if part
        )
        return (
            name
            or user.get("username")
            or user.get("user_name")
            or user.get("email")
            or "Unknown"
        )

    def fetch_page(self, cursor: str | None) -> tuple[list[HistoryRow], str | None]:
        """Fetch and map one generic Rana history page."""
        params: dict[str, str | int] = {"limit": 20}
        if self.path:
            params["path"] = self.path
        if cursor:
            params["cursor"] = cursor
        page = get_tenant_project_file_history_page(self.project_id, params)
        # The API sometimes returns a None cursor even when there are more items,
        # so we increase the limit until we get a next cursor or fewer items than the limit.
        while (len(page["items"]) == params["limit"]) and not page.get("next"):
            params["limit"] = min(int(params["limit"]) + 10, 100)
            if int(params["limit"]) == len(page["items"]):
                break
            page = get_tenant_project_file_history_page(self.project_id, params)
        rows = [
            HistoryRow(
                [
                    HistoryDialog.format_history_timestamp(item.get("created_at")),
                    RanaHistoryDialog.format_user(item.get("committed_by")),
                    str(item.get("message", "")),
                ]
            )
            for item in page.get("items", [])
        ]
        return rows, page.get("next")


class SchematisationRevisionHistoryDialog(HistoryDialog):
    """Display the committed revisions for a schematisation file."""

    def __init__(
        self,
        descriptor_id: str,
        project: dict,
        file_item: dict,
        loader,
        error_signals: ApiErrorSignals,
        parent=None,
    ):
        self.descriptor_id = descriptor_id
        self.project = project
        self.file_item = file_item
        self.loader = loader
        super().__init__(error_signals, parent)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_revision_context_menu)

    def window_title(self) -> str:
        """Return the schematisation revision history title."""
        return "Schematisation revision history"

    def column_headers(self) -> list[str]:
        """Return the initial revision metadata columns."""
        return ["#", "Timestamp", "User", "Message", "Simulation", "Rana Model"]

    def message_column(self) -> int | None:
        """Return the revision message column."""
        return 3

    @staticmethod
    def format_user(revision: object) -> str:
        """Format the author fields exposed by an HCC revision object."""
        first_name = getattr(revision, "commit_first_name", None)
        last_name = getattr(revision, "commit_last_name", None)
        name = " ".join(part for part in (first_name, last_name) if part).strip()
        return name or getattr(revision, "commit_user", None) or "Unknown"

    def fetch_page(self, cursor: str | None) -> tuple[list[HistoryRow], str | None]:
        """Fetch all committed revisions in the worker task."""
        if cursor is not None:
            return [], None
        schematisation_data = get_threedi_schematisation(self.descriptor_id)
        threedi_api = get_threedi_api()
        if threedi_api is None:
            raise MissingThreeDiAuthenticationError(
                "Not authenticated with 3Di API — cannot load schematisation revisions."
            )
        schematisation_id = schematisation_data["schematisation"]["id"]
        revisions = ThreediCalls(threedi_api).fetch_schematisation_revisions(
            schematisation_id
        )
        model_count = sum(bool(revision.has_threedimodel) for revision in revisions)
        model_limit = schematisation_data["schematisation"]["threedimodel_limit"]
        rows = []
        for revision in revisions:
            has_model = bool(revision.has_threedimodel)
            model_enabled = has_model or model_count < model_limit
            rows.append(
                HistoryRow(
                    [
                        str(revision.number),
                        HistoryDialog.format_history_timestamp(revision.commit_date),
                        SchematisationRevisionHistoryDialog.format_user(revision),
                        str(revision.commit_message or ""),
                        "New",
                        "Delete" if has_model else "Create",
                    ],
                    {
                        "simulation_enabled": has_model,
                        "simulation_tooltip": (
                            "A Rana model must be created before a simulation can be started."
                            if not has_model
                            else ""
                        ),
                        "model_enabled": model_enabled,
                        "model_tooltip": (
                            "The maximum number of Rana models has been reached. "
                            "Please delete one of the existing models before creating a new one."
                            if not has_model and not model_enabled
                            else ""
                        ),
                        "has_model": has_model,
                        "model_limit": model_limit,
                        "revision_id": revision.id,
                        "revision": revision,
                        "management_url": schematisation_data.get("management_url"),
                        "schematisation_id": schematisation_id,
                        "schematisation_name": schematisation_data["schematisation"][
                            "name"
                        ],
                    },
                )
            )
        return rows, None

    def show_revision_context_menu(self, position) -> None:
        """Show actions for the revision row under the pointer."""
        index = self.table.indexAt(position)
        if not index.isValid():
            return
        item = self.model.item(index.row(), 0)
        if item is None:
            return
        metadata = item.data(Qt.ItemDataRole.UserRole)
        if not metadata or "revision_id" not in metadata:
            return
        revision_id = int(metadata["revision_id"])
        menu = QMenu(self.table)
        open_action = menu.addAction("Open")
        if open_action is not None:
            open_action.triggered.connect(
                lambda: self.loader.open_items(
                    [
                        OpenSchematisationRequest(
                            self.project, self.file_item, revision_id
                        )
                    ]
                )
            )
        web_action = menu.addAction("Open in web viewer")
        if web_action is not None:
            web_action.triggered.connect(
                lambda: self.open_revision_in_web_viewer(revision_id, metadata)
            )
        viewport = self.table.viewport()
        if viewport is not None:
            menu.exec(viewport.mapToGlobal(position))

    def open_revision_in_web_viewer(self, revision_id: int, metadata: dict) -> None:
        """Open the schematisation management URL for one revision."""
        management_url = metadata.get("management_url")
        if not management_url:
            return
        old_revision_id = management_url.split("?")[0].split("/")[-1]
        QDesktopServices.openUrl(
            QUrl(management_url.replace(old_revision_id, str(revision_id)))
        )

    def configure_table_columns(self) -> None:
        """Fit metadata and action columns while stretching the message."""
        header = self.table.horizontalHeader()
        if header is None:
            return
        for column in (0, 1, 2, 4, 5):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

    def configure_row_widgets(self, row_number: int, row: HistoryRow) -> None:
        """Render the Simulation and Rana Model action buttons."""
        self.render_action_widgets(row_number, row)

    def render_action_widgets(self, row_number: int, row: HistoryRow) -> None:
        """Render the action buttons for one revision row."""
        for column, enabled, tooltip in (
            (
                4,
                row.metadata["simulation_enabled"],
                row.metadata["simulation_tooltip"],
            ),
            (5, row.metadata["model_enabled"], row.metadata["model_tooltip"]),
        ):
            self.render_action_widget(row_number, row, column, enabled, tooltip)

    def render_action_widget(
        self,
        row_number: int,
        row: HistoryRow,
        column: int,
        enabled: bool,
        tooltip: str,
    ) -> None:
        """Replace one action button in a revision row."""
        old_button = self.action_button(row_number, column)
        if old_button is not None:
            self.table.setIndexWidget(self.model.index(row_number, column), None)
            old_button.deleteLater()
        button = QPushButton(row.values[column], self.table)
        button.setEnabled(enabled)
        button.setToolTip(tooltip)
        if column == 4:
            button.clicked.connect(self.show_simulation_placeholder)
        elif column == 5 and row.values[column] == "Create" and enabled:
            button.clicked.connect(
                lambda _checked=False, row=row, button=button: self.create_model(
                    row, button
                )
            )
        elif column == 5 and row.values[column] == "Delete" and enabled:
            button.clicked.connect(
                lambda _checked=False, row=row: self.delete_model(row)
            )
        self.table.setIndexWidget(self.model.index(row_number, column), button)

    def action_button(self, row_number: int, column: int) -> QPushButton | None:
        """Return an action button currently rendered for a table cell."""
        widget = self.table.indexWidget(self.model.index(row_number, column))
        return widget if isinstance(widget, QPushButton) else None

    def row_number_for_revision(self, revision_id: int) -> int | None:
        """Find the table row for a revision ID."""
        for row_number in range(self.model.rowCount()):
            item = self.model.item(row_number, 0)
            if item is None:
                continue
            metadata = item.data(Qt.ItemDataRole.UserRole) or {}
            if metadata.get("revision_id") == revision_id:
                return row_number
        return None

    def row_history(self, row_number: int, metadata: dict) -> HistoryRow:
        """Build current row data for an action-button update."""
        values = []
        for column in range(self.model.columnCount()):
            item = self.model.item(row_number, column)
            values.append(item.text() if item is not None else "")
        return HistoryRow(values, metadata)

    def update_action_columns_after_delete_success(
        self, deleted_revision_id: int
    ) -> None:
        """Update affected action buttons after a successful model deletion."""
        # Update delete row metadata
        deleted_row_number = self.row_number_for_revision(deleted_revision_id)
        if deleted_row_number is None:
            return
        deleted_item = self.model.item(deleted_row_number, 0)
        if deleted_item is None:
            return
        deleted_metadata = deleted_item.data(Qt.ItemDataRole.UserRole)
        if not deleted_metadata:
            return
        model_limit = deleted_metadata["model_limit"]
        deleted_metadata["has_model"] = False
        deleted_metadata["simulation_enabled"] = False
        deleted_metadata["simulation_tooltip"] = (
            "A Rana model must be created before a simulation can be started."
        )
        model_count = sum(
            bool((item.data(Qt.ItemDataRole.UserRole) or {})["has_model"])
            for row_number in range(self.model.rowCount())
            if (item := self.model.item(row_number, 0)) is not None
        )
        deleted_metadata["model_enabled"] = model_count < model_limit
        deleted_metadata["model_tooltip"] = ""
        deleted_item.setData(deleted_metadata, Qt.ItemDataRole.UserRole)
        # Update deleted model actions
        model_item = self.model.item(deleted_row_number, 5)
        if model_item is not None:
            model_item.setText("Create")
        deleted_row = self.row_history(deleted_row_number, deleted_metadata)
        self.render_action_widget(
            deleted_row_number,
            deleted_row,
            4,
            deleted_metadata["simulation_enabled"],
            deleted_metadata["simulation_tooltip"],
        )
        self.render_action_widget(
            deleted_row_number,
            deleted_row,
            5,
            deleted_metadata["model_enabled"],
            deleted_metadata["model_tooltip"],
        )
        # Enable model creation for other rows if the limit allows
        if model_count < model_limit:
            for row_number in range(self.model.rowCount()):
                item = self.model.item(row_number, 0)
                if item is None:
                    continue
                metadata = item.data(Qt.ItemDataRole.UserRole)
                if not metadata or metadata["has_model"]:
                    continue
                if metadata["model_enabled"]:
                    continue
                metadata["model_enabled"] = True
                metadata["model_tooltip"] = ""
                item.setData(metadata, Qt.ItemDataRole.UserRole)
                button = self.action_button(row_number, 5)
                if button is not None:
                    button.setEnabled(True)
                    button.setToolTip("")

    def show_simulation_placeholder(self) -> None:
        """Explain that simulation creation is deferred."""
        QMessageBox.information(
            self,
            "Simulation",
            "Simulation creation is not implemented yet.",
        )

    def create_model(self, row: HistoryRow, button: QPushButton) -> None:
        """Start model creation and show the online process link."""
        response = self.loader.start_model_tracker_process(
            self.project["id"],
            row.metadata["schematisation_id"],
            row.metadata["schematisation_name"],
            row.metadata["revision_id"],
        )
        if response is None:
            return
        button.setEnabled(False)
        button.setToolTip("Model creation requested — click Refresh to check status")
        job_id = response.get("job_id") or response.get("id")
        self.show_process_url_popup(job_id)

    def show_process_url_popup(self, job_id: str) -> None:
        url = get_rana_processes_url(self.project.get("slug", ""), job_id)
        QMessageBox.information(
            self,
            "Rana model creation",
            f'<a href="{url}">Track model creation in Rana</a>',
        )

    def delete_model(self, row: HistoryRow) -> None:
        """Confirm and synchronously delete one revision's Rana model."""
        revision_number = row.values[0]
        if (
            QMessageBox.question(
                self,
                "Delete Rana model",
                f"Delete Rana model for revision #{revision_number}? This cannot be undone.",
                QMessageBox.StandardButton.Yes,
                QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        row_number = self.row_number_for_revision(row.metadata["revision_id"])
        button = self.action_button(row_number, 5) if row_number is not None else None
        if button is not None:
            button.setEnabled(False)
        deleted = False
        try:
            error = self.loader.delete_schematisation_revision_3di_model(
                row.metadata["schematisation_id"], row.metadata["revision_id"]
            )
            if error:
                self.loader.communication.show_error(error, parent=self)
                return
            deleted = True
            self.update_action_columns_after_delete_success(row.metadata["revision_id"])
        finally:
            if button is not None and not deleted:
                button.setEnabled(True)
