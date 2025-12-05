from operator import attrgetter

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QStandardItem, QStandardItemModel
from qgis.PyQt.QtWidgets import QFormLayout, QGridLayout, QLabel, QTreeView, QWizardPage


class StartPage(QWizardPage):
    def __init__(
        self,
        current_local_schematisation,
        schematisation,
        schematisation_filepath,
        available_revisions,
        latest_revision,
        organisation,
        parent,
    ):
        super().__init__(parent)

        self.adjustSize()
        self.setWindowModality(Qt.NonModal)
        self.setWindowTitle("Start")

        gridLayout = QGridLayout(self)

        formLayout = QFormLayout()
        formLayout.setWidget(0, QFormLayout.LabelRole, QLabel("Schematisation:"))
        self.lbl_schematisation = QLabel(
            "{schematisation name} ({schematistion owner})"
        )
        formLayout.setWidget(0, QFormLayout.FieldRole, self.lbl_schematisation)
        formLayout.setWidget(1, QFormLayout.LabelRole, QLabel("Directory:"))
        self.lbl_model_dir = QLabel("{model directory path}")
        formLayout.setWidget(1, QFormLayout.FieldRole, self.lbl_model_dir)
        formLayout.setWidget(
            2,
            QFormLayout.LabelRole,
            QLabel("Work in progress is adapted from revision:"),
        )
        self.lbl_revision_number = QLabel("{revision number}")
        formLayout.setWidget(2, QFormLayout.FieldRole, self.lbl_revision_number)

        gridLayout.addLayout(formLayout, 1, 0)
        gridLayout.addWidget(QLabel("Schematisation revisions history"), 2, 0)

        self.revisions_tv = QTreeView()
        self.revisions_tv.setMinimumSize(0, 250)
        self.revisions_tv.setEditTriggers(QTreeView.NoEditTriggers)
        self.revisions_tv.setSelectionMode(QTreeView.NoSelection)
        gridLayout.addWidget(self.revisions_tv, 3, 0)

        self.tv_revisions_model = QStandardItemModel()

        self.revisions_tv.setModel(self.tv_revisions_model)

        self.current_local_schematisation = current_local_schematisation
        self.schematisation = schematisation
        self.schematisation_filepath = schematisation_filepath
        self.available_revisions = available_revisions
        self.latest_revision = latest_revision
        wip_revision = self.current_local_schematisation.wip_revision

        self.lbl_schematisation.setText(
            f"{self.schematisation.name} ({organisation.name})"
        )
        self.lbl_model_dir.setText(wip_revision.schematisation_dir)
        self.lbl_revision_number.setText(str(wip_revision.number))
        self.populate_available_revisions()

    def populate_available_revisions(self):
        self.tv_revisions_model.clear()
        header = ["Revision number", "Committed by", "Commit date", "Commit message"]
        self.tv_revisions_model.setHorizontalHeaderLabels(header)
        for revision in sorted(
            self.available_revisions, key=attrgetter("number"), reverse=True
        ):
            number_item = QStandardItem(str(revision.number))
            commit_user_item = QStandardItem(revision.commit_user or "")
            commit_date = (
                revision.commit_date.strftime("%d-%m-%Y")
                if revision.commit_date
                else ""
            )
            commit_date_item = QStandardItem(commit_date)
            commit_message_item = QStandardItem(revision.commit_message or "")
            self.tv_revisions_model.appendRow(
                [number_item, commit_user_item, commit_date_item, commit_message_item]
            )
        for i in range(len(header)):
            self.revisions_tv.resizeColumnToContents(i)
