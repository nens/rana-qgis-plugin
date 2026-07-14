from functools import partial

from qgis.PyQt.QtWidgets import (
    QComboBox,
    QGridLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QSpacerItem,
    QWidget,
    QWizardPage,
)

from rana_qgis_plugin.simulation.utils_ui import (
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
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.registerField(
            "schematisation_name*", self.main_widget.le_schematisation_name
        )
        self.registerField(
            "schematisation_description", self.main_widget.le_description
        )
        self.registerField("schematisation_tags", self.main_widget.le_tags)
        self.registerField(
            "schematisation_organisation",
            self.main_widget.cbo_organisations,
            "currentData",
        )

    def nextId(self):
        return 1

    def isComplete(self):
        return bool(self.field("schematisation_name"))

    @property
    def name(self):
        """Schematisation name as entered by the user."""
        return self.field("schematisation_name")

    @property
    def description(self):
        """Schematisation description as entered by the user."""
        return self.field("schematisation_description")

    @property
    def tags(self):
        """Schematisation tags as a list of stripped strings."""
        raw = self.field("schematisation_tags")
        if not raw:
            return []
        return [tag.strip() for tag in raw.split(",")]

    @property
    def owner(self):
        """Unique ID of the selected organisation."""
        if len(self.organisations) > 1:
            return self.field("schematisation_organisation").unique_id
        return list(self.organisations.values())[0].unique_id


class SchematisationNameWidget(QWidget):
    """Widget for the Schematisation Name and tags page."""

    def __init__(self, organisations, parent):
        super().__init__(parent)

        # Set geometry and properties
        self.setWindowTitle("Name")

        # Grid layout
        gridLayout = QGridLayout(self)
        gridLayout.addItem(
            QSpacerItem(20, 25, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed),
            0,
            0,
        )

        # Schematisation name label
        gridLayout.addWidget(QLabel("New schematisation name:"), 2, 0)

        # Schematisation name input
        self.le_schematisation_name = QLineEdit()
        self.le_schematisation_name.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.le_schematisation_name.setMaxLength(80)
        self.le_schematisation_name.setPlaceholderText("Name your schematisation")
        gridLayout.addWidget(self.le_schematisation_name, 2, 2)

        gridLayout.addWidget(QLabel("Description:"), 3, 0)

        # Description input
        self.le_description = QLineEdit()
        self.le_description.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.le_description.setMinimumSize(0, 25)
        self.le_description.setPlaceholderText(
            "Concise description of your schematisation (optional)"
        )
        gridLayout.addWidget(self.le_description, 3, 2)

        gridLayout.addWidget(QLabel("Tags:"), 4, 0)

        self.le_tags = QLineEdit()
        self.le_tags.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.le_tags.setMinimumSize(0, 25)
        self.le_tags.setPlaceholderText("Comma-separated tags (optional)")
        gridLayout.addWidget(self.le_tags, 4, 2)

        organisations_label = QLabel("Rana Organisation:")
        self.cbo_organisations = QComboBox()
        gridLayout.addWidget(organisations_label, 5, 0)
        gridLayout.addWidget(self.cbo_organisations, 5, 1, 1, 2)
        # hide dropdown if exactly 1 3Di organisation is available
        # 0 available organisations should be blocked in the Rana tenant creation menu but add an assert just in case
        assert len(organisations) > 0
        if len(organisations) > 1:
            self.organisations = organisations
            self.populate_organisations()
            self.cbo_organisations.currentTextChanged.connect(
                partial(save_3di_settings, "threedi/last_used_organisation")
            )
        else:
            organisations_label.hide()
            self.cbo_organisations.hide()

        gridLayout.addItem(
            QSpacerItem(
                20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding
            ),
            6,
            0,
        )

    def populate_organisations(self):
        """Populating organisations."""
        for org in self.organisations.values():
            self.cbo_organisations.addItem(org.name, org)
        last_organisation = read_3di_settings("threedi/last_used_organisation")
        if last_organisation:
            self.cbo_organisations.setCurrentText(last_organisation)
