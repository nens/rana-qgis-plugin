from collections import defaultdict
from operator import attrgetter

from qgis.PyQt.QtCore import QSettings, QSize
from qgis.PyQt.QtWidgets import QSizePolicy, QWizard
from threedi_api_client.openapi import SchematisationRevision
from .upload_wizard_pages import (
    CheckModelPage, SelectFilesPage, StartPage
)


class SchematisationUploadWizard(QWizard):
    def __init__(
        self,
        current_local_schematisation,
        schematisation,
        schematisation_filepath,
        threedi_api,
        organisation,
        communication,
        parent,
    ):
        super().__init__(parent)
        self.setWizardStyle(QWizard.ClassicStyle)

        self.current_local_schematisation = current_local_schematisation
        self.schematisation = schematisation
        self.schematisation_filepath = schematisation_filepath
        self.communication = communication

        self.available_revisions = threedi_api.fetch_schematisation_revisions(
            threedi_api, self.schematisation.id
        )
        if self.available_revisions:
            self.latest_revision = max(self.available_revisions, key=attrgetter("id"))
        else:
            self.latest_revision = SchematisationRevision(number=0)

        self.addPage(
            StartPage(
                current_local_schematisation,
                schematisation,
                schematisation_filepath,
                self.available_revisions,
                self.latest_revision,
                organisation,
                self,
            )
        )
        self.addPage(
            CheckModelPage(
                current_local_schematisation,
                schematisation_filepath,
                self.communication,
                self,
            )
        )
        self.select_files_page = SelectFilesPage(
            schematisation,
            schematisation_filepath,
            self.latest_revision,
            threedi_api,
            self,
        )

        self.addPage(self.select_files_page)

        self.setButtonText(QWizard.FinishButton, "Start upload")
        finish_btn = self.button(QWizard.FinishButton)
        finish_btn.clicked.connect(self.start_upload)
        cancel_btn = self.button(QWizard.CancelButton)
        cancel_btn.clicked.connect(self.cancel_wizard)
        self.new_upload = defaultdict(lambda: None)
        self.new_upload_statuses = None
        self.setWindowTitle("New upload")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.resize(QSettings().value("threedi/upload_wizard_size", QSize(800, 600)))

    def start_upload(self):
        """Build dictionary with new upload parameters."""
        self.new_upload.clear()
        self.new_upload["schematisation"] = self.schematisation
        self.new_upload["latest_revision"] = self.latest_revision
        # Complex values, such as these dicts,
        self.new_upload["selected_files"] = self.select_files_page.get_selected_files()

        # These values are registered in the WizardPage
        self.new_upload["commit_message"] = self.field("commit_message")
        self.new_upload["create_revision"] = True
        self.new_upload["make_3di_model"] = self.field("make_3di_model")
        # TODO: rename this later (also in UploadWorker)
        self.new_upload["cb_inherit_templates"] = self.field("inherit_templates")

    def cancel_wizard(self):
        """Handling canceling wizard action."""
        QSettings().setValue("threedi/upload_wizard_size", self.size())
        self.reject()
