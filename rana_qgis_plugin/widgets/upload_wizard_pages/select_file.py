import os
import shutil
from collections import OrderedDict
from functools import partial

from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    QWizardPage,
)
from threedi_api_client.openapi import ApiException
from rana_qgis_plugin.simulation.utils import (
    is_file_checksum_equal,
    zip_into_archive,
)
from rana_qgis_plugin.simulation.utils_ui import (
    get_filepath,
    geopackage_layer,
)
from rana_qgis_plugin.simulation.utils_api import (
    SchematisationApiMapper,
    UploadFileStatus,
    UploadFileType,
)


class SelectFilesPage(QWizardPage):
    """Upload Select Files definition page."""

    def __init__(
        self,
        schematisation,
        schematisation_filepath,
        latest_revision,
        threedi_api,
        parent,
    ):
        super().__init__(parent)

        self.main_widget = SelectFilesWidget(
            schematisation, schematisation_filepath, latest_revision, threedi_api, self
        )
        layout = QGridLayout()
        layout.addWidget(self.main_widget, 0, 0)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.adjustSize()

        # Register these fields so we can retrieve them in the wizard
        self.registerField(
            "commit_message*",
            self.main_widget.te_upload_description,
            "plainText",
            self.main_widget.te_upload_description.textChanged,
        )
        self.registerField("make_3di_model", self.main_widget.cb_make_3di_model)
        self.registerField("inherit_templates", self.main_widget.cb_inherit_templates)

    def get_selected_files(self):
        return self.main_widget.detected_files


class SelectFilesWidget(QWidget):
    """Widget for the Select Files page."""

    def __init__(
        self,
        schematisation,
        schematisation_filepath,
        latest_revision,
        threedi_api,
        parent,
    ):
        super().__init__(parent)

        self.setWindowTitle("Select files")
        self.setGeometry(0, 0, 720, 600)
        self.setMinimumSize(720, 0)
        self.setAutoFillBackground(True)

        self.gridLayout = QGridLayout(self)

        self.svg_lout = QVBoxLayout()
        self.gridLayout.addLayout(self.svg_lout, 0, 0, 1, 2)

        file_group = QGroupBox("Select files", self)
        self.gridLayout.addWidget(file_group, 1, 0)
        file_group_layout = QGridLayout(self)
        file_group.setLayout(file_group_layout)

        self.scrollArea = QScrollArea()
        self.scrollArea.setFrameShape(QFrame.StyledPanel)
        self.scrollArea.setWidgetResizable(True)

        self.scrollAreaWidgetContents = QWidget()
        self.scrollArea.setWidget(self.scrollAreaWidgetContents)
        self.gridLayout_3 = QGridLayout(self.scrollAreaWidgetContents)

        # Add all widgets inside the scroll area
        self.widget_general = self.add_section(self.gridLayout_3, "General", 0)
        self.widget_terrain_model = self.add_section(
            self.gridLayout_3, "Terrain Model", 1
        )
        self.widget_simple_infiltration = self.add_section(
            self.gridLayout_3, "Simple infiltration", 2
        )
        self.widget_groundwater = self.add_section(self.gridLayout_3, "Groundwater", 3)
        self.widget_interflow = self.add_section(self.gridLayout_3, "Interflow", 4)
        self.widget_vegetation_drag = self.add_section(
            self.gridLayout_3, "Vegetation drag", 5
        )

        file_group_layout.addWidget(self.scrollArea)

        self.gridLayout.addWidget(QLabel("Describe the changes you upload:"), 3, 0)

        # Description text area
        self.te_upload_description = QPlainTextEdit()
        self.te_upload_description.setPlaceholderText("commit message")
        self.gridLayout.addWidget(self.te_upload_description, 4, 0)

        # Checkboxes
        self.cb_upload_schematisation_revision = QCheckBox(
            "Upload schematisation revision"
        )
        self.cb_upload_schematisation_revision.setEnabled(False)
        self.cb_upload_schematisation_revision.setChecked(True)
        self.gridLayout.addWidget(self.cb_upload_schematisation_revision, 6, 0)

        self.cb_make_3di_model = QCheckBox("Make 3Di model")
        self.cb_make_3di_model.setChecked(True)
        self.gridLayout.addWidget(self.cb_make_3di_model, 7, 0)

        self.cb_inherit_templates = QCheckBox(
            "Inherit simulation templates from previous revision"
        )
        self.cb_inherit_templates.setChecked(True)
        self.gridLayout.addWidget(self.cb_inherit_templates, 8, 0)

        self.threedi_api = threedi_api
        self.latest_revision = latest_revision
        self.schematisation = schematisation
        self.schematisation_filepath = schematisation_filepath

        self.cb_make_3di_model.stateChanged.connect(self.toggle_make_3di_model)
        self.detected_files = self.check_files_states()
        self.widgets_per_file = {}

        self.initialize_widgets()

    def add_section(self, layout, title, row):
        """Adds a collapsible section layout with a bold label (stub)."""
        widget = QWidget()
        widget_layout = QGridLayout(widget)
        label = QLabel(title)
        widget_layout.addWidget(label, 0, 0)
        layout.addWidget(widget, row, 0)
        return widget

    def toggle_make_3di_model(self):
        """Handle Make 3Di model checkbox state changes."""
        if self.cb_make_3di_model.isChecked():
            self.cb_inherit_templates.setChecked(True)
            self.cb_inherit_templates.setEnabled(True)
        else:
            self.cb_inherit_templates.setChecked(False)
            self.cb_inherit_templates.setEnabled(False)

    def check_files_states(self):
        """Check raster (and geopackage) files presence and compare local and remote data."""
        files_states = OrderedDict()
        if self.latest_revision.number > 0:
            remote_rasters = self.threedi_api.fetch_schematisation_revision_rasters(
                self.threedi_api, self.schematisation.id, self.latest_revision.id
            )
        else:
            remote_rasters = []
        remote_rasters_by_type = {
            SchematisationApiMapper.settings_raster_type(raster.type): raster
            for raster in remote_rasters
        }
        if "dem_raw_file" in remote_rasters_by_type:
            remote_rasters_by_type["dem_file"] = remote_rasters_by_type["dem_raw_file"]
            del remote_rasters_by_type["dem_raw_file"]
        geopackage_dir = os.path.dirname(self.schematisation_filepath)
        if self.latest_revision.sqlite:
            try:
                zipped_schematisation_db = zip_into_archive(
                    self.schematisation_filepath
                )
                sqlite_download = self.threedi_api.download_schematisation_revision_sqlite(
                    self.threedi_api, self.schematisation.id, self.latest_revision.id
                )
                files_matching = is_file_checksum_equal(
                    zipped_schematisation_db, sqlite_download.etag
                )
                status = (
                    UploadFileStatus.NO_CHANGES_DETECTED
                    if files_matching
                    else UploadFileStatus.CHANGES_DETECTED
                )
                os.remove(zipped_schematisation_db)
            except ApiException:
                status = UploadFileStatus.CHANGES_DETECTED
        else:
            status = UploadFileStatus.NEW
        files_states["geopackage"] = {
            "status": status,
            "filepath": self.schematisation_filepath,
            "type": UploadFileType.DB,
            "remote_raster": None,
            "make_action": True,
        }

        for (
            table_name,
            files_fields,
        ) in SchematisationApiMapper.raster_reference_tables().items():
            table_lyr = geopackage_layer(self.schematisation_filepath, table_name)
            try:
                first_feat = next(table_lyr.getFeatures())
            except StopIteration:
                continue
            for file_field in files_fields:
                try:
                    file_relative_path = first_feat[file_field]
                except KeyError:
                    continue
                remote_raster = remote_rasters_by_type.get(file_field)
                if not file_relative_path and not remote_raster:
                    continue
                filepath = (
                    os.path.join(geopackage_dir, "rasters", file_relative_path)
                    if file_relative_path
                    else None
                )
                if filepath:
                    if os.path.exists(filepath):
                        if remote_raster and remote_raster.file:
                            files_matching = is_file_checksum_equal(
                                filepath, remote_raster.file.etag
                            )
                            status = (
                                UploadFileStatus.NO_CHANGES_DETECTED
                                if files_matching
                                else UploadFileStatus.CHANGES_DETECTED
                            )
                        else:
                            status = UploadFileStatus.NEW
                    else:
                        status = UploadFileStatus.INVALID_REFERENCE
                else:
                    status = UploadFileStatus.DELETED_LOCALLY
                files_states[file_field] = {
                    "status": status,
                    "filepath": filepath,
                    "type": UploadFileType.RASTER,
                    "remote_raster": remote_raster,
                    "make_action": True,
                }
        return files_states

    def initialize_widgets(self):
        """Dynamically set up widgets based on detected files."""
        self.widgets_per_file.clear()
        files_widgets = [
            self.widget_general,
            self.widget_terrain_model,
            self.widget_simple_infiltration,
            self.widget_groundwater,
            self.widget_interflow,
            self.widget_vegetation_drag,
        ]
        files_info_collection = [
            OrderedDict((("geopackage", "GeoPackage"),)),
            SchematisationApiMapper.model_settings_rasters(),
            SchematisationApiMapper.simple_infiltration_rasters(),
            SchematisationApiMapper.groundwater_rasters(),
            SchematisationApiMapper.interflow_rasters(),
            SchematisationApiMapper.vegetation_drag_rasters(),
        ]
        for widget in files_widgets:
            widget.hide()

        current_main_layout_row = 1
        for widget, files_info in zip(files_widgets, files_info_collection):
            widget_layout = widget.layout()
            for field_name, name in files_info.items():
                try:
                    file_state = self.detected_files[field_name]
                except KeyError:
                    continue
                status = file_state["status"]
                widget.show()
                name_label = QLabel(name)
                name_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
                widget_layout.addWidget(name_label, current_main_layout_row, 0)

                status_label = QLabel(status.value)
                status_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
                widget_layout.addWidget(status_label, current_main_layout_row, 1)

                empty_label = QLabel()
                widget_layout.addWidget(empty_label, current_main_layout_row, 2)

                no_action_pb_name = "Ignore"
                if status == UploadFileStatus.DELETED_LOCALLY:
                    action_pb_name = "Delete online"
                else:
                    action_pb_name = "Upload"
                # Add valid reference widgets
                all_actions_widget = QWidget()
                actions_sublayout = QGridLayout()
                all_actions_widget.setLayout(actions_sublayout)

                valid_ref_widget = QWidget()
                valid_ref_sublayout = QGridLayout()
                valid_ref_widget.setLayout(valid_ref_sublayout)
                no_action_pb = QPushButton(no_action_pb_name)
                no_action_pb.setCheckable(True)
                no_action_pb.setAutoExclusive(True)
                no_action_pb.clicked.connect(
                    partial(self.toggle_action, field_name, False)
                )

                action_pb = QPushButton(action_pb_name)
                action_pb.setCheckable(True)
                action_pb.setAutoExclusive(True)
                action_pb.setChecked(True)
                action_pb.clicked.connect(partial(self.toggle_action, field_name, True))

                valid_ref_sublayout.addWidget(no_action_pb, 0, 0)
                valid_ref_sublayout.addWidget(action_pb, 0, 1)

                # Add invalid reference widgets
                invalid_ref_widget = QWidget()
                invalid_ref_sublayout = QGridLayout()
                invalid_ref_widget.setLayout(invalid_ref_sublayout)

                filepath_sublayout = QGridLayout()
                filepath_line_edit = QLineEdit()
                filepath_line_edit.setSizePolicy(
                    QSizePolicy.Minimum, QSizePolicy.Minimum
                )
                browse_pb = QPushButton("...")
                browse_pb.clicked.connect(partial(self.browse_for_raster, field_name))
                filepath_sublayout.addWidget(filepath_line_edit, 0, 0)
                filepath_sublayout.addWidget(browse_pb, 0, 1)
                invalid_ref_sublayout.addLayout(filepath_sublayout, 0, 0)

                update_ref_pb = QPushButton("Update reference")
                update_ref_pb.clicked.connect(
                    partial(self.update_raster_reference, field_name)
                )
                invalid_ref_sublayout.addWidget(update_ref_pb, 0, 1)

                actions_sublayout.addWidget(valid_ref_widget, 0, 0)
                actions_sublayout.addWidget(invalid_ref_widget, 0, 1)
                # Add all actions widget into the main widget layout
                widget_layout.addWidget(all_actions_widget, current_main_layout_row, 2)
                # Hide some widgets based on files states
                if status == UploadFileStatus.NO_CHANGES_DETECTED:
                    all_actions_widget.hide()
                elif status == UploadFileStatus.INVALID_REFERENCE:
                    valid_ref_widget.hide()
                else:
                    invalid_ref_widget.hide()
                self.widgets_per_file[field_name] = (
                    name_label,
                    status_label,
                    valid_ref_widget,
                    action_pb,
                    invalid_ref_widget,
                    filepath_line_edit,
                )
                current_main_layout_row += 1

    def toggle_action(self, raster_type, make_action):
        """Update detected files info after particular action change."""
        files_refs = self.detected_files[raster_type]
        files_refs["make_action"] = make_action

    def browse_for_raster(self, raster_type):
        """Browse for raster file for a given raster type."""
        name_filter = "GeoTIFF (*.tif *.TIF *.tiff *.TIFF)"
        title = "Select reference raster file"
        raster_file = get_filepath(
            None, extension_filter=name_filter, dialog_title=title
        )
        if raster_file:
            filepath_line_edit = self.widgets_per_file[raster_type][-1]
            filepath_line_edit.setText(raster_file)

    def update_raster_reference(self, raster_type):
        """
        Update raster reference and copy file to the raster subdirectory if it lays outside of it.
        """
        (
            name_label,
            status_label,
            valid_ref_widget,
            action_pb,
            invalid_ref_widget,
            filepath_line_edit,
        ) = self.widgets_per_file[raster_type]
        new_filepath = filepath_line_edit.text()
        if new_filepath:
            new_file_name = os.path.basename(new_filepath)
            main_dir = os.path.dirname(self.schematisation_filepath)
            target_filepath = os.path.join(main_dir, "rasters", new_file_name)
            filepath_exists = os.path.exists(new_filepath)
            if filepath_exists:
                if not os.path.exists(target_filepath):
                    shutil.copyfile(new_filepath, target_filepath)
        else:
            new_file_name = ""
            target_filepath = None
            filepath_exists = False
        reference_table = SchematisationApiMapper.raster_table_mapping()[raster_type]
        table_lyr = geopackage_layer(self.schematisation_filepath, reference_table)
        first_feat = next(table_lyr.getFeatures())
        field_idx = table_lyr.fields().lookupField(raster_type)
        fid = first_feat.id()
        table_lyr.startEditing()
        table_lyr.changeAttributeValue(fid, field_idx, new_file_name)
        table_lyr.commitChanges()
        (
            geopackage_name_label,
            geopackage_status_label,
            geopackage_valid_ref_widget,
            geopackage_action_pb,
            geopackage_invalid_ref_widget,
            geopackage_filepath_line_edit,
        ) = self.widgets_per_file["geopackage"]
        geopackage_files_refs = self.detected_files["geopackage"]
        if geopackage_files_refs["status"] != UploadFileStatus.NEW:
            geopackage_files_refs["status"] = UploadFileStatus.CHANGES_DETECTED
            geopackage_status_label.setText(UploadFileStatus.CHANGES_DETECTED.value)
            geopackage_valid_ref_widget.show()
        files_refs = self.detected_files[raster_type]
        remote_raster = files_refs["remote_raster"]
        files_refs["filepath"] = target_filepath
        if not new_file_name:
            if not remote_raster:
                files_refs["status"] = UploadFileStatus.NO_CHANGES_DETECTED
                status_label.setText(UploadFileStatus.NO_CHANGES_DETECTED.value)
                invalid_ref_widget.hide()
            else:
                files_refs["status"] = UploadFileStatus.DELETED_LOCALLY
                status_label.setText(UploadFileStatus.DELETED_LOCALLY.value)
                action_pb.setText("Delete online")
                invalid_ref_widget.hide()
                valid_ref_widget.show()
        else:
            if filepath_exists:
                if not remote_raster:
                    files_refs["status"] = UploadFileStatus.NEW
                    status_label.setText(UploadFileStatus.NEW.value)
                    invalid_ref_widget.hide()
                    valid_ref_widget.show()
                else:
                    if is_file_checksum_equal(new_filepath, remote_raster.file.etag):
                        files_refs["status"] = UploadFileStatus.NO_CHANGES_DETECTED
                        status_label.setText(UploadFileStatus.NO_CHANGES_DETECTED.value)
                        invalid_ref_widget.hide()
                    else:
                        files_refs["status"] = UploadFileStatus.CHANGES_DETECTED
                        status_label.setText(UploadFileStatus.CHANGES_DETECTED.value)
                        invalid_ref_widget.hide()
                        valid_ref_widget.show()
