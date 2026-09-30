from dataclasses import dataclass, field
from typing import Callable, cast

from qgis._core import QgsTask


@dataclass(frozen=True)
class HistoryRow:
    """Plain row data passed from a history task to the GUI thread."""

    values: list[str]
    metadata: dict = field(default_factory=dict)


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
