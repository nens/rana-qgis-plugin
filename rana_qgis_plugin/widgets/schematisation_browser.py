"""Search HCC schematisations and select a revision to import."""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
)
from threedi_api_client.openapi import ApiException

from rana_qgis_plugin.simulation.threedi_calls import ThreediCalls
from rana_qgis_plugin.simulation.utils import extract_error_message
from rana_qgis_plugin.utils.api import RanaFetchError, get_schematisations
from rana_qgis_plugin.utils.time import (
    format_timestamp,
    parse_timestamp_str,
)
from rana_qgis_plugin.widgets.utils_search import DebouncedSearchBox


class SortableTableWidgetItem(QTableWidgetItem):
    """Table item with an explicit, optionally case-folded sort value."""

    SORT_ROLE = Qt.ItemDataRole.UserRole + 1

    def __init__(self, text: str, sort_value=None):
        super().__init__(text)
        self.setData(
            self.SORT_ROLE, text.casefold() if sort_value is None else sort_value
        )

    def __lt__(self, other) -> bool:
        return self.data(self.SORT_ROLE) < other.data(self.SORT_ROLE)


class SchematisationBrowser(QDialog):
    """Let the user search HCC schematisations and choose one revision."""

    def __init__(self, threedi_api, parent=None):
        super().__init__(parent)
        self.tc = ThreediCalls(threedi_api)
        self.selected_schematisation = None
        self.selected_revision = None
        self.setWindowTitle("Import schematisation to project")
        self.setMinimumWidth(900)
        self.setMaximumSize(1200, 850)
        self.search_input = DebouncedSearchBox(
            parent=self,
            delay_ms=500,
            min_chars=0,
            placeholder="Search for a schematisation",
        )
        self.search_input.searchChanged.connect(
            lambda _text: self.populate_schematisation_table()
        )

        self.schematisation_table = QTableWidget(0, 3, self)
        self.schematisation_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.schematisation_table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )
        self.schematisation_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.schematisation_table.setSortingEnabled(True)
        self.schematisation_table.verticalHeader().setVisible(False)
        self.schematisation_table.horizontalHeader().setStretchLastSection(False)
        self.schematisation_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        self.schematisation_table.setHorizontalHeaderLabels(
            ["Name", "Updated", "Created by"]
        )
        self.schematisation_table.itemSelectionChanged.connect(
            self.on_schematisation_selected
        )

        self.revisions_table = QTableWidget(0, 3, self)
        self.revisions_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.revisions_table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )
        self.revisions_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.revisions_table.setSortingEnabled(False)
        self.revisions_table.verticalHeader().setVisible(False)
        self.revisions_table.horizontalHeader().setStretchLastSection(False)
        revisions_header = self.revisions_table.horizontalHeader()
        revisions_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        revisions_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        revisions_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        revisions_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        revisions_header.setStretchLastSection(True)
        self.revisions_table.setHorizontalHeaderLabels(
            ["Revision", "Committed", "Message"]
        )
        self.revisions_table.itemSelectionChanged.connect(self.update_ok_button)

        self.status_label = QLabel(self)
        self.status_label.setStyleSheet("color: red;")
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self.ok_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        self.ok_button.setEnabled(False)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        layout = QGridLayout(self)
        layout.addWidget(self.search_input, 0, 0, 1, 3)
        layout.addWidget(QLabel("Schematisations", self), 1, 0, 1, 3)
        layout.addWidget(self.schematisation_table, 2, 0, 1, 3)
        layout.addWidget(QLabel("Revisions", self), 3, 0, 1, 3)
        layout.addWidget(self.revisions_table, 4, 0, 1, 3)
        layout.addWidget(self.status_label, 5, 0, 1, 2)
        layout.addWidget(self.button_box, 5, 2)

        self.populate_schematisation_table()

    def populate_schematisation_table(self) -> None:
        """Fetch and display schematisations matching the current search."""
        self.schematisation_table.setRowCount(0)
        self.revisions_table.setRowCount(0)
        self.selected_schematisation = None
        self.selected_revision = None
        self.update_ok_button()
        self.status_label.clear()
        self.schematisation_table.setSortingEnabled(False)
        try:
            schematisations = get_schematisations(self.search_input.text())
        except Exception as error:
            self.schematisation_table.setSortingEnabled(True)
            self.show_fetch_error(error)
            return

        for row, schematisation in enumerate(schematisations):
            name_item = SortableTableWidgetItem(str(schematisation["name"]))
            name_item.setData(Qt.ItemDataRole.UserRole, schematisation)
            created_by = " ".join(
                part
                for part in (
                    schematisation.get("created_by_first_name"),
                    schematisation.get("created_by_last_name"),
                )
                if part
            )
            values = (
                name_item,
                SortableTableWidgetItem(
                    self.format_schematisation_timestamp(
                        schematisation.get("last_updated", "")
                    )
                ),
                SortableTableWidgetItem(created_by),
            )
            self.schematisation_table.insertRow(row)
            for column, value in enumerate(values):
                self.schematisation_table.setItem(row, column, value)
        self.schematisation_table.resizeColumnsToContents()
        self.schematisation_table.setSortingEnabled(True)
        self.schematisation_table.sortItems(0, Qt.SortOrder.AscendingOrder)
        self.resize_to_contents()
        if schematisations:
            self.schematisation_table.selectRow(0)
        else:
            self.status_label.setText("No schematisations found.")

    def on_schematisation_selected(self) -> None:
        """Load revisions for the selected schematisation."""
        self.revisions_table.setRowCount(0)
        self.selected_revision = None
        row = self.schematisation_table.currentRow()
        item = self.schematisation_table.item(row, 0) if row >= 0 else None
        self.selected_schematisation = (
            item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        )
        if self.selected_schematisation is None:
            self.update_ok_button()
            return

        self.status_label.clear()
        self.revisions_table.setSortingEnabled(False)
        try:
            revisions = self.tc.fetch_schematisation_revisions(
                self.selected_schematisation["id"]
            )
        except Exception as error:
            self.show_fetch_error(error)
            return

        self.populate_revisions_table(revisions)

    def populate_revisions_table(self, revisions) -> None:
        """Populate the revision table newest first and select its latest row."""
        revisions = sorted(
            revisions, key=lambda revision: int(revision.number or 0), reverse=True
        )
        for row, revision in enumerate(revisions):
            number_item = QTableWidgetItem(str(revision.number))
            number_item.setData(Qt.ItemDataRole.UserRole, revision)
            values = (
                number_item,
                QTableWidgetItem(
                    self.format_schematisation_timestamp(
                        getattr(revision, "commit_date", "")
                    )
                ),
                QTableWidgetItem(str(getattr(revision, "commit_message", "") or "")),
            )
            self.revisions_table.insertRow(row)
            for column, value in enumerate(values):
                self.revisions_table.setItem(row, column, value)
        self.revisions_table.resizeColumnsToContents()
        self.resize_to_contents()
        if revisions:
            self.revisions_table.selectRow(0)
        else:
            self.status_label.setText("No committed revisions are available.")
        self.update_ok_button()

    def resize_to_contents(self) -> None:
        """Fit the dialog to table contents up to its maximum dimensions."""
        schematisation_header = self.schematisation_table.horizontalHeader()
        schematisation_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        schematisation_header.setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        schematisation_header.setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self.schematisation_table.resizeColumnsToContents()
        self.revisions_table.resizeColumnsToContents()
        table_content_width = max(
            self.schematisation_table.verticalHeader().width()
            + 2 * self.schematisation_table.frameWidth()
            + sum(self.schematisation_table.columnWidth(column) for column in range(3)),
            self.revisions_table.verticalHeader().width()
            + 2 * self.revisions_table.frameWidth()
            + sum(self.revisions_table.columnWidth(column) for column in range(3)),
        )
        layout = self.layout()
        if layout is not None:
            margins = layout.contentsMargins()
            table_content_width += margins.left() + margins.right()
        width = min(
            max(table_content_width, self.sizeHint().width(), self.minimumWidth()),
            self.maximumWidth(),
        )
        self.resize(
            width,
            min(max(self.sizeHint().height(), self.height()), self.maximumHeight()),
        )
        layout = self.layout()
        if layout is not None:
            layout.activate()
        schematisation_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.resize_schematisation_name_column()

    def resizeEvent(self, event) -> None:
        """Keep the name column wide enough to fill space left by metadata."""
        super().resizeEvent(event)
        self.resize_schematisation_name_column()

    def resize_schematisation_name_column(self) -> None:
        """Give the schematisation name column all width left by metadata."""
        table_width = (
            self.schematisation_table.width()
            - 2 * self.schematisation_table.frameWidth()
            - self.schematisation_table.verticalHeader().width()
        )
        metadata_width = self.schematisation_table.columnWidth(
            1
        ) + self.schematisation_table.columnWidth(2)
        if table_width > metadata_width:
            self.schematisation_table.setColumnWidth(0, table_width - metadata_width)

    def update_ok_button(self) -> None:
        """Enable confirmation only when both selections are valid."""
        row = self.revisions_table.currentRow()
        item = self.revisions_table.item(row, 0) if row >= 0 else None
        self.selected_revision = (
            item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        )
        self.ok_button.setEnabled(
            self.selected_schematisation is not None
            and self.selected_revision is not None
        )

    def show_fetch_error(self, error: Exception) -> None:
        """Display a useful HCC fetch error and disable confirmation."""
        if isinstance(error, ApiException):
            message = extract_error_message(error)
        elif isinstance(error, RanaFetchError):
            message = error.msg
        else:
            message = str(error)
        self.status_label.setText(
            f"Failed to retrieve schematisations or revisions: {message}"
        )
        self.selected_revision = None
        self.update_ok_button()

    def accept(self) -> None:
        """Accept only when a schematisation and revision are selected."""
        self.update_ok_button()
        if self.ok_button.isEnabled():
            super().accept()

    @staticmethod
    def format_schematisation_timestamp(value) -> str:
        """Format a schematisation or revision timestamp as local yyyy-mm-dd hh:mm."""
        if not value:
            return ""
        try:
            return format_timestamp(parse_timestamp_str(str(value)), "%Y-%m-%d %H:%M")
        except (TypeError, ValueError, OverflowError):
            return str(value)
