from functools import partial

from qgis.PyQt.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QRadioButton,
    QSizePolicy,
    QSpacerItem,
    QToolButton,
    QWidget,
    QWizardPage,
)

from rana_qgis_plugin.simulation.utils_ui import (
    get_filepath,
    read_3di_settings,
    save_3di_settings,
)


class SchematisationNamePage(QWizardPage):
    """New schematisation name and tags definition page."""

    def __init__(self, organisations, parent):
        super().__init__(parent)
        self.organisations = organisations
        self.main_widget = SchematisationNameWidget(organisations, self)
        layout = QGridLayout()
        layout.addWidget(self.main_widget)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.registerField(
            "schematisation_name*", self.main_widget.le_schematisation_name
        )
        self.registerField("from_geopackage", self.main_widget.rb_existing_geopackage)
        self.registerField("geopackage_path", self.main_widget.le_geopackage_path)
        self.main_widget.rb_existing_geopackage.toggled.connect(self.update_pages_order)
        self.main_widget.le_schematisation_name.textChanged.connect(
            self.update_pages_order
        )
        self.main_widget.le_geopackage_path.textChanged.connect(self.update_pages_order)

        self.registerField(
            "schematisation_description", self.main_widget.le_description
        )
        self.registerField("schematisation_tags", self.main_widget.le_tags)
        self.registerField(
            "schematisation_organisation",
            self.main_widget.cbo_organisations,
            "currentData",
        )
        self.registerField("rana_path", self.main_widget.le_rana_path)

    def update_pages_order(self):
        """Check if user wants to use an existing GeoPackage and finalize the wizard, if needed."""
        if self.main_widget.rb_existing_geopackage.isChecked():
            self.main_widget.le_geopackage_path.setEnabled(True)
            self.main_widget.btn_browse_geopackage.setEnabled(True)
            if self.field("geopackage_path"):
                self.setFinalPage(True)
        else:
            self.main_widget.le_geopackage_path.setEnabled(False)
            self.main_widget.btn_browse_geopackage.setEnabled(False)
            self.setFinalPage(False)
        self.completeChanged.emit()

    def nextId(self):
        if self.main_widget.rb_existing_geopackage.isChecked() and self.field(
            "geopackage_path"
        ):
            return -1
        else:
            return 1

    def isComplete(self):
        if self.field("schematisation_name") and (
            self.main_widget.rb_new_geopackage.isChecked()
            or (
                self.main_widget.rb_existing_geopackage.isChecked()
                and self.field("geopackage_path")
            )
        ):
            return True

        else:
            return False


class SchematisationNameWidget(QWidget):
    """Widget for the Schematisation Name and tags page."""

    def __init__(self, organisations, parent):
        super().__init__(parent)

        # Set geometry and properties
        self.setWindowTitle("Name")

        # Grid layout
        gridLayout = QGridLayout(self)
        gridLayout.addItem(
            QSpacerItem(20, 25, QSizePolicy.Minimum, QSizePolicy.Fixed), 0, 0
        )

        # Schematisation name label
        gridLayout.addWidget(QLabel("New schematisation name:"), 2, 0)

        # Schematisation name input
        self.le_schematisation_name = QLineEdit()
        self.le_schematisation_name.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Preferred
        )
        self.le_schematisation_name.setMaxLength(80)
        self.le_schematisation_name.setPlaceholderText("Name your schematisation")
        gridLayout.addWidget(self.le_schematisation_name, 2, 2)

        gridLayout.addWidget(QLabel("Description:"), 3, 0)

        # Description input
        self.le_description = QLineEdit()
        self.le_description.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.le_description.setMinimumSize(0, 25)
        self.le_description.setPlaceholderText(
            "Concise description of your schematisation (optional)"
        )
        gridLayout.addWidget(self.le_description, 3, 2)

        gridLayout.addWidget(QLabel("Tags:"), 4, 0)

        self.le_tags = QLineEdit()
        self.le_tags.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.le_tags.setMinimumSize(0, 25)
        self.le_tags.setPlaceholderText("Comma-separated tags (optional)")
        gridLayout.addWidget(self.le_tags, 4, 2)

        gridLayout.addWidget(QLabel("Organisation:"), 5, 0)

        self.cbo_organisations = QComboBox()
        gridLayout.addWidget(self.cbo_organisations, 5, 1, 1, 2)

        gridLayout.addItem(
            QSpacerItem(20, 25, QSizePolicy.Minimum, QSizePolicy.Fixed), 6, 0
        )

        gridLayout.addWidget(QLabel("GeoPackage:"), 7, 0)

        gridLayout_2 = QGridLayout()
        self.rb_new_geopackage = QRadioButton("Create new GeoPackage")
        self.rb_new_geopackage.setChecked(True)
        gridLayout_2.addWidget(self.rb_new_geopackage, 0, 0)

        horizontalLayout_2 = QHBoxLayout()
        horizontalLayout_2.setContentsMargins(0, 0, 0, 0)

        self.rb_existing_geopackage = QRadioButton("Choose file:")
        horizontalLayout_2.addWidget(self.rb_existing_geopackage)

        self.le_geopackage_path = QLineEdit()
        self.le_geopackage_path.setEnabled(False)
        horizontalLayout_2.addWidget(self.le_geopackage_path)

        self.btn_browse_geopackage = QToolButton()
        self.btn_browse_geopackage.setEnabled(False)
        self.btn_browse_geopackage.setText("...")
        horizontalLayout_2.addWidget(self.btn_browse_geopackage)

        gridLayout_2.addLayout(horizontalLayout_2, 2, 0)

        gridLayout.addLayout(gridLayout_2, 7, 2)

        # Rana path label
        gridLayout.addWidget(QLabel("Rana schematisation directory:"), 8, 0)

        # Rana path input
        self.le_rana_path = QLineEdit()
        self.le_rana_path.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.le_rana_path.setMaxLength(80)
        self.le_rana_path.setPlaceholderText(
            "Directory in your Rana project to place the new schematisation in (optional)"
        )
        gridLayout.addWidget(self.le_rana_path, 8, 2)

        gridLayout.addItem(
            QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding), 9, 0
        )

        self.organisations = organisations
        self.populate_organisations()
        self.btn_browse_geopackage.clicked.connect(self.browse_existing_geopackage)
        self.cbo_organisations.currentTextChanged.connect(
            partial(save_3di_settings, "threedi/last_used_organisation")
        )

    def populate_organisations(self):
        """Populating organisations."""
        for org in self.organisations.values():
            self.cbo_organisations.addItem(org.name, org)
        last_organisation = read_3di_settings("threedi/last_used_organisation")
        if last_organisation:
            self.cbo_organisations.setCurrentText(last_organisation)

    def browse_existing_geopackage(self):
        gpkg_filter = "GeoPackage/SQLite (*.gpkg *.GPKG *.sqlite *SQLITE)"
        geopackage_path = get_filepath(
            self,
            dialog_title="Select Schematisation file",
            extension_filter=gpkg_filter,
        )
        if geopackage_path is not None:
            self.le_geopackage_path.setText(geopackage_path)
