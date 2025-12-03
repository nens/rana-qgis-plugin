import sys
from typing import List
from pathlib import Path

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QApplication,
    QFileDialog,
    QWidget,
    QGridLayout,
    QListWidget,
    QPushButton,
    QRadioButton,
    QLabel,
    QDialog,
    QDialogButtonBox,
    QComboBox,
    QGroupBox,
    QTableWidget,
    QTableWidgetItem,
    QButtonGroup,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
)

from rana_qgis_plugin.constant import PLUGIN_NAME

class NewSchematisationDialog(QDialog):
    def __init__(self, parent, path):
        super().__init__(parent)
        self.setWindowTitle(PLUGIN_NAME)
        self.setMinimumWidth(600)
        layout = QVBoxLayout(self)
        self.setLayout(layout)

        self.selected_file = None

        inputs_group = QWidget(self)
        inputs_group.setLayout(QFormLayout())

        self.schematisation_name_box = QLineEdit(self)
        self.description_name_box = QLineEdit(self)
        self.tags_box = QLineEdit(self)
        self.organisation_select_box = QComboBox(self)

        self.schematisation_name_box.setPlaceholderText("Name your schematisation")
        self.description_name_box.setPlaceholderText("Concise description of your schematisation (optional)")
        self.tags_box.setPlaceholderText("Comma-separated tags (optional)")
        self.organisation_select_box.addItems(['Foo', 'Bar'])

        inputs_group.layout().addRow("New schematisation name:", self.schematisation_name_box)
        inputs_group.layout().addRow("Description:", self.description_name_box)
        inputs_group.layout().addRow("Tags:", self.tags_box)
        inputs_group.layout().addRow("Organisation:", self.organisation_select_box)

        # file selection
        self.file_choice_widget = QWidget(self)
        self.file_choice_widget.setLayout(QGridLayout())

        self.new_geopackage_button = QRadioButton("Create new GeoPackage")
        self.choose_file_button = QRadioButton("Choose file:")

        self.file_name_box = QLineEdit(self)
        file_browse = QPushButton('...')
        file_browse.setMaximumWidth(25)
        file_browse.clicked.connect(self.open_file_dialog)

        def enable_disable_file_browse():
            self.file_name_box.setEnabled(self.choose_file_button.isChecked())
            file_browse.setEnabled(self.choose_file_button.isChecked())

        self.choose_file_button.toggled.connect(enable_disable_file_browse)
        self.new_geopackage_button.setChecked(True)
        enable_disable_file_browse()

        self.file_choice_widget.layout().addWidget(
            self.new_geopackage_button, 0, 0, 1, 3, Qt.AlignLeft)
        self.file_choice_widget.layout().addWidget(self.choose_file_button, 1, 0)
        self.file_choice_widget.layout().addWidget(self.file_name_box, 1, 1)
        self.file_choice_widget.layout().addWidget(file_browse, 1, 2)

        inputs_group.layout().addRow("GeoPackage:", self.file_choice_widget)

        layout.addWidget(inputs_group)

        buttonBox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)
        layout.addWidget(buttonBox)


    def open_file_dialog(self):
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Select File",
            "/home/eli/Programs/threedi-sample-data"
            "Geopackage (*.gpkg)"
        )
        if filename:
            self.selected_file == filename
            self.file_name_box.setText(filename)
    
    def get_selected_filename(self):
        return self.selected_file

    def accept(self) -> None:
        return super().accept()
