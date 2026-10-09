"""Shared name, description, and owner page for schematisation creation."""

from qgis.PyQt.QtCore import QSettings
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


class SchematisationNamePage(QWizardPage):
    """Collect required name and the shared optional metadata."""

    def __init__(self, organisations, parent=None):
        super().__init__(parent)
        if not organisations:
            raise ValueError("At least one 3Di organisation is required.")
        self.organisations = organisations
        self.main_widget = SchematisationNameWidget(organisations, self)
        layout = QGridLayout(self)
        layout.addWidget(self.main_widget)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.registerField(
            "schematisation_name*", self.main_widget.le_schematisation_name
        )
        self.registerField(
            "schematisation_description", self.main_widget.le_description
        )
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
    def name(self) -> str:
        """Return the required schematisation name."""
        return self.field("schematisation_name")

    @property
    def description(self) -> str:
        """Return the optional description."""
        return self.field("schematisation_description")

    @property
    def owner(self):
        """Return the selected organisation's unique ID."""
        if len(self.organisations) == 1:
            return next(iter(self.organisations.values())).unique_id
        organisation = self.field("schematisation_organisation")
        return organisation.unique_id if organisation is not None else None


class SchematisationNameWidget(QWidget):
    """Widget containing schematisation name and metadata fields."""

    def __init__(self, organisations, parent=None):
        super().__init__(parent)
        self.organisations = organisations
        layout = QGridLayout(self)
        layout.addItem(
            QSpacerItem(20, 25, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed),
            0,
            0,
        )

        layout.addWidget(QLabel("New schematisation name:"), 1, 0)
        self.le_schematisation_name = QLineEdit(self)
        self.le_schematisation_name.setMaxLength(80)
        self.le_schematisation_name.setPlaceholderText("Name your schematisation")
        layout.addWidget(self.le_schematisation_name, 1, 1, 1, 2)

        layout.addWidget(QLabel("Description:"), 2, 0)
        self.le_description = QLineEdit(self)
        self.le_description.setMinimumSize(0, 25)
        self.le_description.setPlaceholderText(
            "Concise description of your schematisation (optional)"
        )
        layout.addWidget(self.le_description, 2, 1, 1, 2)

        self.organisations_label = QLabel("Rana Organisation:")
        self.cbo_organisations = QComboBox(self)
        layout.addWidget(self.organisations_label, 3, 0)
        layout.addWidget(self.cbo_organisations, 3, 1, 1, 2)

        if len(organisations) == 1:
            self.organisations_label.hide()
            self.cbo_organisations.hide()
        else:
            self.populate_organisations()
            self.cbo_organisations.currentTextChanged.connect(
                self.save_selected_organisation
            )

        layout.addItem(
            QSpacerItem(
                20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding
            ),
            4,
            0,
        )

    def populate_organisations(self) -> None:
        """Populate choices and restore the last selected organisation."""
        for organisation in self.organisations.values():
            self.cbo_organisations.addItem(organisation.name, organisation)
        settings = QSettings()
        last_organisation = settings.value("threedi/last_used_organisation", "")
        if last_organisation:
            self.cbo_organisations.setCurrentText(last_organisation)

    def save_selected_organisation(self, name: str) -> None:
        """Persist the selected organisation by its display name."""
        if name:
            QSettings().setValue("threedi/last_used_organisation", name)
