from functools import partial
from typing import List

from qgis.core import QgsCoordinateReferenceSystem
from qgis.gui import QgsProjectionSelectionWidget
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QDoubleValidator, QIcon
from qgis.PyQt.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from rana_qgis_plugin.constant import PLUGIN_NAME
from rana_qgis_plugin.utils import format_activity_time
from rana_qgis_plugin.utils_api import (
    get_filename_from_attachment_url,
    get_schematisations,
)


class SchematisationBrowser(QDialog):
    def __init__(self, parent, communication):
        super().__init__(parent)
        self.setWindowTitle("Import schematisation to project")
        self.setMinimumWidth(600)
        self.communication = communication
        layout = QGridLayout(self)
        self.setLayout(layout)
        self.selected_schematisation = None

        self.search_le = QLineEdit(self)
        self.search_le.addAction(
            QIcon(":images/themes/default/mIconZoom.svg"), QLineEdit.LeadingPosition
        )
        self.search_le.setPlaceholderText("Search for a schematisation")
        self.search_le.textChanged.connect(self.populate_table)
        layout.addWidget(self.search_le, 0, 0)
        spacer = QSpacerItem(60, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        layout.addItem(spacer, 0, 1, 1, 2)

        self.table = QTableWidget(self)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        self.table.setColumnCount(3)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setHorizontalHeaderLabels(["Name", "Updated", "Created by"])
        layout.addWidget(self.table, 1, 0, 1, 3)

        cancel_button = QPushButton("Cancel", self)
        layout.addWidget(cancel_button, 2, 0, 1, 1)
        cancel_button.clicked.connect(self.reject)
        cancel_button.setMaximumWidth(100)

        spacer = QSpacerItem(60, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        layout.addItem(spacer, 2, 1)

        self.ok_button = QPushButton("Ok", self)
        self.ok_button.setEnabled(False)
        self.ok_button.setMaximumWidth(100)
        self.ok_button.clicked.connect(self.ok_pressed)
        layout.addWidget(self.ok_button, 2, 2, 1, 1)

        self.table.itemSelectionChanged.connect(
            partial(self.ok_button.setEnabled, True)
        )

        self.populate_table()

    def ok_pressed(self):
        self.selected_schematisation = self.table.item(self.table.currentRow(), 0).data(
            Qt.ItemDataRole.UserRole
        )
        self.communication.log_warn("self.selected_schematisation")
        self.communication.log_warn(str(self.selected_schematisation))
        self.accept()

    def populate_table(self):
        search_value = self.search_le.text()

        schematisations = get_schematisations(self.communication)
        for i, schematisation in enumerate(schematisations):
            self.table.insertRow(self.table.rowCount())
            name_item = QTableWidgetItem(schematisation["name"])
            updated_item = QTableWidgetItem(
                format_activity_time(schematisation["last_updated"])
            )
            creation_by_item = QTableWidgetItem(
                schematisation["created_by_first_name"]
                + " "
                + schematisation["created_by_last_name"]
            )
            name_item.setData(Qt.ItemDataRole.UserRole, schematisation)
            self.table.setItem(i, 0, name_item)
            self.table.setItem(i, 1, updated_item)
            self.table.setItem(i, 2, creation_by_item)

            for i in range(3):
                self.table.resizeColumnToContents(i)
