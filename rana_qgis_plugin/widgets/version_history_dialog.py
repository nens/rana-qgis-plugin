"""Shared dialogs for displaying Rana file and revision history."""

from typing import Callable, cast

from qgis.core import QgsApplication, QgsTask
from qgis.PyQt.QtGui import (
    QCloseEvent,
    QShowEvent,
    QStandardItem,
    QStandardItemModel,
)
from qgis.PyQt.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableView,
    QVBoxLayout,
)

from rana_qgis_plugin.api_error_signals import ApiErrorSignals
from rana_qgis_plugin.network_manager import NetworkUnavailableError
from rana_qgis_plugin.utils.api import (
    RanaFetchError,
    get_tenant_project_file_history_page,
)


class HistoryFetchTask(QgsTask):
    """Fetch history data without blocking the QGIS GUI thread."""

    def __init__(self, fetch_page: Callable[[], tuple[list[list[str]], str | None]]):
        cancel_flag = cast("QgsTask.Flags", getattr(QgsTask, "CanCancel", 0))
        super().__init__("Fetch history", flags=cancel_flag)
        self.fetch_page = fetch_page
        self.rows: list[list[str]] = []
        self.next_cursor: str | None = None
        self.error: Exception | None = None

    def run(self) -> bool:
        """Fetch plain row data on the task worker thread."""
        if self.isCanceled():
            return False
        try:
            self.rows, self.next_cursor = self.fetch_page()
        except Exception as error:
            self.error = error
            return False
        return not self.isCanceled()


class HistoryDialog(QDialog):
    """Base dialog for asynchronously fetched history tables."""

    def __init__(self, error_signals: ApiErrorSignals, parent=None):
        super().__init__(parent)
        self.error_signals = error_signals
        self._has_loaded = False
        self._closed = False
        self._task: HistoryFetchTask | None = None
        self._next_cursor: str | None = None

        self.table = QTableView(self)
        self.table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        vertical_header = self.table.verticalHeader()
        if vertical_header is not None:
            vertical_header.setVisible(False)
        self.model = QStandardItemModel(self.table)
        self.table.setModel(self.model)
        scrollbar = self.table.verticalScrollBar()
        if scrollbar is not None:
            scrollbar.valueChanged.connect(self._load_next_page_if_needed)
            scrollbar.rangeChanged.connect(self._load_next_page_if_needed)

        self.refresh_button = QPushButton("Refresh", self)
        self.refresh_button.clicked.connect(self.refresh)
        self.error_label = QLabel(self)
        self.error_label.setStyleSheet("color: red;")
        self.error_label.setVisible(False)
        self.empty_label = QLabel("No history yet", self)
        self.empty_label.setVisible(False)
        self.loading_label = QLabel("Loading history...", self)
        self.loading_label.setVisible(False)

        layout = QVBoxLayout(self)
        layout.addWidget(self.table)
        bottom_layout = QHBoxLayout(self)
        bottom_layout.addWidget(self.loading_label)
        bottom_layout.addWidget(self.empty_label)
        bottom_layout.addWidget(self.error_label)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.refresh_button)
        layout.addLayout(bottom_layout)
        self.resize(900, 550)
        self._row_count = 0

    def window_title(self) -> str:
        """Return the dialog window title."""
        raise NotImplementedError

    def column_headers(self) -> list[str]:
        """Return the table column headers."""
        raise NotImplementedError

    def fetch_page(self, cursor: str | None) -> tuple[list[list[str]], str | None]:
        """Fetch one history page and return rows with its next cursor."""
        raise NotImplementedError

    def showEvent(self, a0: QShowEvent | None) -> None:
        """Fetch history the first time the dialog is shown."""
        super().showEvent(a0)
        self._closed = False
        self.setWindowTitle(self.window_title())
        self.model.setHorizontalHeaderLabels(self.column_headers())
        self.configure_table_columns()
        if not self._has_loaded:
            self.refresh()

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        """Cancel an in-flight fetch when the dialog closes."""
        self._closed = True
        self._has_loaded = False
        if self._task is not None:
            self._task.cancel()
            self._task = None
        super().closeEvent(a0)

    def refresh(self) -> None:
        """Start a background fetch and replace the table when it completes."""
        if self._task is not None:
            return
        self.refresh_button.setEnabled(False)
        self.error_label.setVisible(False)
        self.empty_label.setVisible(False)
        self.loading_label.setVisible(True)
        self._has_loaded = True
        self.model.removeRows(0, self.model.rowCount())
        self._row_count = 0
        self._next_cursor = None
        self._start_page(None)

    def _start_page(self, cursor: str | None) -> None:
        """Start one page fetch for the initial or next cursor."""
        if self._task is not None or self._closed:
            return
        self.refresh_button.setEnabled(False)
        self.loading_label.setVisible(True)
        task = HistoryFetchTask(lambda: self.fetch_page(cursor))
        self._task = task
        task.taskCompleted.connect(lambda: self._task_completed(task))
        task.taskTerminated.connect(lambda: self._task_terminated(task))
        task_manager = QgsApplication.taskManager()
        if task_manager is not None:
            task_manager.addTask(task)
        else:
            self._task = None
            self.loading_label.setVisible(False)
            self.refresh_button.setEnabled(True)
            self.show_error("Could not start history request")

    def _task_completed(self, task: HistoryFetchTask) -> None:
        """Apply successful task results on the GUI thread."""
        if task is not self._task or self._closed:
            return
        self._task = None
        self.loading_label.setVisible(False)
        self.refresh_button.setEnabled(True)
        self._next_cursor = task.next_cursor
        self._append_rows(task.rows)
        self.empty_label.setVisible(self._row_count == 0)

    def _task_terminated(self, task: HistoryFetchTask) -> None:
        """Finish a failed or canceled task without applying stale rows."""
        if task is not self._task:
            return
        self._task = None
        if self._closed:
            return
        self.loading_label.setVisible(False)
        self.refresh_button.setEnabled(True)
        if task.error is not None:
            self._show_fetch_error(task.error)

    def _append_rows(self, rows: list[list[str]]) -> None:
        """Append one fetched page to the table on the GUI thread."""
        self.model.setHorizontalHeaderLabels(self.column_headers())
        self.configure_table_columns()
        for row in rows:
            self.model.appendRow([QStandardItem(value) for value in row])
        self._row_count += len(rows)

    def _load_next_page_if_needed(self, *_args: int) -> None:
        """Fetch the next page when the user reaches the table bottom."""
        scrollbar = self.table.verticalScrollBar()
        if (
            scrollbar is None
            or scrollbar.value() < scrollbar.maximum()
            or self._next_cursor is None
            or self._task is not None
            or self._closed
        ):
            return
        cursor = self._next_cursor
        self._next_cursor = None
        self._start_page(cursor)

    def _show_fetch_error(self, error: Exception) -> None:
        """Route expected fetch errors through the existing UI contract."""
        if isinstance(error, NetworkUnavailableError):
            self.error_signals.connection_lost.emit()
            self.show_error("No connection to Rana")
        elif isinstance(error, RanaFetchError):
            self.error_signals.fetch_error_occurred.emit(str(error), False)
            self.show_error(f"Failed to load history: {error}")
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
        super().__init__(error_signals, parent)

    def window_title(self) -> str:
        """Return the generic history dialog title."""
        return "History"

    def column_headers(self) -> list[str]:
        """Return the generic history columns."""
        return ["Timestamp", "User", "Message"]

    def fetch_page(self, cursor: str | None) -> tuple[list[list[str]], str | None]:
        """Fetch and map one generic Rana history page."""
        # TODO: there are strange issues with pagination causing incorrect none cursors to be returned
        # This should be fixed
        params: dict[str, str | int] = {"limit": 100}
        if self.path:
            params["path"] = self.path
        if cursor:
            params["cursor"] = cursor
        page = get_tenant_project_file_history_page(self.project_id, params)
        rows = [
            [
                str(item.get("created_at", "")),
                self._display_user(item.get("committed_by")),
                str(item.get("message", "")),
            ]
            for item in page.get("items", [])
        ]
        return rows, page.get("next")

    @staticmethod
    def _display_user(user: dict | None) -> str:
        """Return the preferred display value for a committed-by user."""
        user = user or {}
        name = " ".join(
            part for part in (user.get("given_name"), user.get("family_name")) if part
        )
        return name or user.get("email") or "Unknown"
