# 3Di Models and Simulations for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2023 by Lutra Consulting for 3Di Water Management
import logging
import os
from functools import partial
from math import ceil
from operator import attrgetter

from qgis.PyQt import uic
from qgis.PyQt.QtCore import QItemSelectionModel, Qt
from qgis.PyQt.QtGui import QStandardItem, QStandardItemModel
from threedi_api_client.openapi import ApiException

from .threedi_calls import ThreediCalls
from .utils import extract_error_message
from .utils_ui import read_3di_settings, save_3di_settings, set_icon

base_dir = os.path.dirname(os.path.dirname(__file__))
uicls, basecls = uic.loadUiType(
    os.path.join(base_dir, "simulation", "simulation_wizard", "model_selection.ui")
)


logger = logging.getLogger(__name__)

TABLE_LIMIT = 10
NAME_COLUMN_IDX = 1


class ModelSelectionDialog(uicls, basecls):
    """Dialog for model selection."""

    def __init__(
        self,
        communication,
        model_pk,
        threedi_api,
        organisations,
        schematisation_id,
        parent,
    ):
        super().__init__(parent)
        self.setupUi(self)
        self.schematisation_id = schematisation_id
        self.communication = communication
        self.threedi_api = threedi_api
        self.organisations = organisations
        self.simulation_templates = None
        self.model_pk = model_pk
        self.current_model = None
        self.model_is_loaded = False
        self.templates_model = QStandardItemModel()
        self.templates_tv.setModel(self.templates_model)
        self.templates_tv.selectionModel().selectionChanged.connect(
            self.toggle_load_model
        )
        self.pb_cancel_load.clicked.connect(self.reject)
        self.pb_load.clicked.connect(self.accept)
        self.populate_organisations()
        self.organisations_box.currentTextChanged.connect(
            partial(save_3di_settings, "threedi/last_used_organisation")
        )
        set_icon(self.refresh_btn, "refresh.svg")
        self.refresh_btn.clicked.connect(self.refresh_templates_list)
        self.refresh_templates_list()

    def refresh_templates_list(self):
        """Refresh simulation templates list if any model is selected."""
        tc = ThreediCalls(self.threedi_api)
        self.current_model = tc.fetch_3di_model(self.model_pk)
        self.templates_model.clear()
        self.templates_page_sbox.setMaximum(1)
        self.templates_page_sbox.setSuffix(" / 1")
        self.fetch_simulation_templates()
        if self.templates_model.rowCount() > 0:
            row_idx = self.templates_model.index(0, 0)
            self.templates_tv.selectionModel().setCurrentIndex(
                row_idx, QItemSelectionModel.ClearAndSelect
            )
        self.toggle_load_model()
        self.switch_to_model_organisation()

    def toggle_load_model(self):
        """Toggle load button if any model is selected."""
        selection_model = self.templates_tv.selectionModel()
        if selection_model.hasSelection():
            self.pb_load.setEnabled(True)
        else:
            self.pb_load.setDisabled(True)

    def move_templates_backward(self):
        """Moving to the templates previous results page."""
        self.templates_page_sbox.setValue(self.page_sbox.value() - 1)

    def move_templates_forward(self):
        """Moving to the templates next results page."""
        self.templates_page_sbox.setValue(self.page_sbox.value() + 1)

    def populate_organisations(self):
        """Populating organisations list inside combo box."""
        for org in self.organisations.values():
            self.organisations_box.addItem(org.name, org)
        last_organisation = read_3di_settings("threedi/last_used_organisation")
        if last_organisation:
            self.organisations_box.setCurrentText(last_organisation)
        if len(self.organisations) == 1:
            self.label_6.hide()
            self.organisations_box.hide()
        else:
            self.label_6.show()
            self.organisations_box.show()

    def switch_to_model_organisation(self):
        """Switch to model organisation."""
        schematisation_id = self.schematisation_id
        try:
            tc = ThreediCalls(self.threedi_api)
            model_schematisation = tc.fetch_schematisation(schematisation_id)
            model_schematisation_owner = model_schematisation.owner
            organisation = self.organisations.get(model_schematisation_owner)
            if organisation is not None:
                self.organisations_box.setCurrentText(organisation.name)
        except ApiException as e:
            self.close()
            error_msg = extract_error_message(e)
            self.communication.show_error(error_msg)
        except Exception as e:
            self.close()
            error_msg = f"Error: {e}"
            self.communication.show_error(error_msg)

    def fetch_simulation_templates(self):
        """Fetching simulation templates list."""
        try:
            tc = ThreediCalls(self.threedi_api)
            offset = (self.templates_page_sbox.value() - 1) * TABLE_LIMIT
            selected_model = self.current_model
            model_pk = selected_model.id
            templates, templates_count = tc.fetch_simulation_templates_with_count(
                model_pk, limit=TABLE_LIMIT, offset=offset
            )
            pages_nr = ceil(templates_count / TABLE_LIMIT) or 1
            self.templates_page_sbox.setMaximum(pages_nr)
            self.templates_page_sbox.setSuffix(f" / {pages_nr}")
            self.templates_model.clear()
            header = ["Template ID", "Template name", "Creation date"]
            self.templates_model.setHorizontalHeaderLabels(header)
            for template in sorted(templates, key=attrgetter("id"), reverse=True):
                id_item = QStandardItem(str(template.id))
                name_item = QStandardItem(template.name)
                name_item.setData(template, role=Qt.UserRole)
                creation_date = (
                    template.created.strftime("%d-%m-%Y") if template.created else ""
                )
                creation_date_item = QStandardItem(creation_date)
                self.templates_model.appendRow([id_item, name_item, creation_date_item])
            for i in range(len(header)):
                self.templates_tv.resizeColumnToContents(i)
            self.simulation_templates = templates
        except ApiException as e:
            error_msg = extract_error_message(e)
            self.communication.show_error(error_msg)
        except Exception as e:
            error_msg = f"Error: {e}"
            self.communication.show_error(error_msg)

    def get_selected_template(self):
        """Get currently selected simulation template."""
        index = self.templates_tv.currentIndex()
        if index.isValid():
            current_row = index.row()
            name_item = self.templates_model.item(current_row, NAME_COLUMN_IDX)
            selected_template = name_item.data(Qt.UserRole)
        else:
            selected_template = None
        return selected_template

    def get_selected_organisation(self):
        return self.organisations_box.currentData()
