# 3Di Models and Simulations for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2023 by Lutra Consulting for 3Di Water Management
import logging
import os

from qgis.PyQt import uic
from qgis.PyQt.QtCore import QItemSelectionModel, Qt
from qgis.PyQt.QtGui import QStandardItem, QStandardItemModel
from threedi_mi_utils import (
    WIPRevision,
    list_local_schematisations,
    replace_revision_data,
)

base_dir = os.path.dirname(os.path.dirname(__file__))
uicls, basecls = uic.loadUiType(
    os.path.join(base_dir, "load_schematisation", "schematisation_load.ui")
)


logger = logging.getLogger(__name__)


class SchematisationLoad(uicls, basecls):
    """Dialog for local schematisation loading."""

    def __init__(
        self, working_dir, communication, selected_local_schematisation, parent
    ):
        super().__init__(parent)
        self.setupUi(self)
        self.label.setWordWrap(True)
        self.label.setText(
            f"No work in progress (WIP) revision was found. Available locally stored revisions are listed below.\n\nPlease choose which one you want to upload. This will set the chosen revision as WIP and make it the latest revision."
        )
        self.working_dir = working_dir
        self.setWindowTitle("Choose revision to upload as new revision")
        self.communication = communication
        self.tv_revisions_model = QStandardItemModel()
        self.revisions_tv.setModel(self.tv_revisions_model)
        self.selected_local_schematisation = selected_local_schematisation
        self.pb_load.clicked.connect(self.load_local_schematisation)
        self.pb_cancel.clicked.connect(self.cancel_load_local_schematisation)
        self.revisions_tv.selectionModel().selectionChanged.connect(
            self.toggle_load_local_schematisation
        )
        self.populate_local_schematisation_revisions()

    def populate_local_schematisation_revisions(self):
        """Populate local schematisation revisions."""
        self.tv_revisions_model.clear()
        header = ["Revision number", "Subdirectory"]
        self.tv_revisions_model.setHorizontalHeaderLabels(header)
        local_schematisation = self.selected_local_schematisation
        wip_revision = local_schematisation.wip_revision
        if wip_revision is not None:
            number_item = QStandardItem(str(wip_revision.number))
            number_item.setData(wip_revision, role=Qt.UserRole)
            subdir_item = QStandardItem(wip_revision.sub_dir)
            self.tv_revisions_model.appendRow([number_item, subdir_item])
        for revision_number, local_revision in sorted(
            local_schematisation.revisions.items(), key=lambda x: x[0], reverse=True
        ):
            number_item = QStandardItem(str(revision_number))
            number_item.setData(local_revision, role=Qt.UserRole)
            subdir_item = QStandardItem(local_revision.sub_dir)
            self.tv_revisions_model.appendRow([number_item, subdir_item])
        if self.tv_revisions_model.rowCount() > 0:
            row_idx = self.tv_revisions_model.index(0, 0)
            self.revisions_tv.selectionModel().setCurrentIndex(
                row_idx, QItemSelectionModel.ClearAndSelect
            )
        self.toggle_load_local_schematisation()

    def toggle_load_local_schematisation(self):
        """Toggle load button if any schematisation revision is selected."""
        selection_model = self.revisions_tv.selectionModel()
        if selection_model.hasSelection():
            self.pb_load.setEnabled(True)
        else:
            self.pb_load.setDisabled(True)

    def get_selected_local_revision(self):
        """Get currently selected local revision."""
        index = self.revisions_tv.currentIndex()
        if index.isValid():
            current_row = index.row()
            name_item = self.tv_revisions_model.item(current_row, 0)
            local_revision = name_item.data(Qt.UserRole)
        else:
            local_revision = None
        return local_revision

    def load_local_schematisation(self):
        """Loading selected local schematisation."""
        local_schematisation = self.selected_local_schematisation
        local_revision = self.get_selected_local_revision()
        if not isinstance(local_revision, WIPRevision):
            title = "Pick action"
            question = f"Upload data from revision {local_revision.number}?"
            picked_action_name = self.communication.custom_ask(
                self, title, question, "Replace", "Cancel"
            )
            if picked_action_name == "Replace":
                wip_revision = local_schematisation.set_wip_revision(
                    local_revision.number
                )
                replace_revision_data(local_revision, wip_revision)
            else:
                self.reject()
                return
        self.selected_local_schematisation = local_schematisation
        self.local_revision = local_revision
        self.accept()

    def cancel_load_local_schematisation(self):
        """Cancel local schematisation loading."""
        self.reject()
