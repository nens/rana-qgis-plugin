from dataclasses import dataclass, field
from typing import Callable, cast

from qgis._core import QgsTask


@dataclass(frozen=True)
class HistoryRow:
    """Plain row data passed from a history task to the GUI thread."""

    values: list[str]
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ModelDeleteResult:
    """Outcome of a model deletion, passed from the task to the GUI thread."""

    error: str | None = None
    is_generating: bool = False


class ModelDeleteTask(QgsTask):
    """Delete a Rana model off the GUI thread.

    Deliberately not cancelable: an interrupted delete could leave the revision
    half-deleted, so QGIS waits for it to finish on shutdown.
    """

    def __init__(self, delete: Callable[[], ModelDeleteResult]):
        # QgsTask defaults to CanCancel, so pass empty flags explicitly.
        super().__init__("Delete Rana model", flags=QgsTask.Flags())
        self.delete = delete
        self.result = ModelDeleteResult()

    def run(self) -> bool:
        """Run the delete; failures are reported through ``result``."""
        try:
            self.result = self.delete()
        except Exception as error:
            self.result = ModelDeleteResult(error=str(error))
        return True


class HistoryFetchTask(QgsTask):
    """Fetch history data without blocking the QGIS GUI thread."""

    def __init__(self, fetch_page: Callable[[], tuple[list[HistoryRow], str | None]]):
        cancel_flag = cast("QgsTask.Flags", getattr(QgsTask, "CanCancel", 0))
        super().__init__("Fetch history", flags=cancel_flag)
        self.fetch_page = fetch_page
        self.rows: list[HistoryRow] = []
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
