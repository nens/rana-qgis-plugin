"""Shared dialogs for displaying Rana file and revision history."""

from abc import ABC, abstractmethod

from qgis.PyQt.QtGui import QShowEvent, QStandardItem, QStandardItemModel
from qgis.PyQt.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableView,
    QVBoxLayout,
)

from rana_qgis_plugin.api_error_signals import ApiErrorSignals
from rana_qgis_plugin.network_manager import NetworkUnavailableError
from rana_qgis_plugin.utils.api import RanaFetchError


class HistoryDialog(QDialog, ABC):
    """Base dialog for synchronously fetched history tables."""

    def __init__(self, error_signals: ApiErrorSignals, parent=None):
        super().__init__(parent)
        self.error_signals = error_signals
        self._has_loaded = False

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
        self.empty_label = QLabel("No history yet", self)
        self.empty_label.setVisible(False)

        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(self.refresh_button)
        layout = QVBoxLayout(self)
        layout.addWidget(self.table)
        layout.addWidget(self.empty_label)
        layout.addWidget(self.error_label)
        layout.addLayout(buttons)

    @abstractmethod
    def window_title(self) -> str:
        """Return the dialog window title."""
        raise NotImplementedError

    @abstractmethod
    def column_headers(self) -> list[str]:
        """Return the table column headers."""
        raise NotImplementedError

    @abstractmethod
    def fetch_rows(self) -> list[list[QStandardItem]]:
        """Fetch history and return rows ready for the table model."""
        raise NotImplementedError

    def showEvent(self, a0: QShowEvent | None) -> None:
        """Fetch history the first time the dialog is shown."""
        super().showEvent(a0)
        self.setWindowTitle(self.window_title())
        self.model.setHorizontalHeaderLabels(self.column_headers())
        if not self._has_loaded:
            self.refresh()

    def refresh(self) -> None:
        """Fetch history and replace the current table contents."""
        self.refresh_button.setEnabled(False)
        self.error_label.setVisible(False)
        self.empty_label.setVisible(False)
        try:
            rows = self.fetch_rows()
        except NetworkUnavailableError:
            self.error_signals.connection_lost.emit()
            self.show_error("No connection to Rana")
            return
        except RanaFetchError as error:
            self.error_signals.fetch_error_occurred.emit(str(error), False)
            self.show_error(f"Failed to load history: {error}")
            return
        finally:
            self.refresh_button.setEnabled(True)
            self._has_loaded = True

        self.model.removeRows(0, self.model.rowCount())
        self.model.setHorizontalHeaderLabels(self.column_headers())
        for row in rows:
            self.model.appendRow(row)
        self.empty_label.setVisible(not rows)

    def show_error(self, message: str) -> None:
        """Display an inline error while keeping Refresh available."""
        self.error_label.setText(message)
        self.error_label.setVisible(True)
