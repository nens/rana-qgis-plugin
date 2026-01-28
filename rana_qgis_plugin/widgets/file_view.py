from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from qgis.gui import QgsCollapsibleGroupBox
from qgis.PyQt.QtCore import (
    QSettings,
    Qt,
    pyqtSignal,
)
from qgis.PyQt.QtGui import (
    QIcon,
    QStandardItem,
    QStandardItemModel,
)
from qgis.PyQt.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from rana_qgis_plugin.constant import SUPPORTED_DATA_TYPES
from rana_qgis_plugin.simulation.threedi_calls import ThreediCalls
from rana_qgis_plugin.utils import (
    NumericItem,
    convert_to_local_time,
    display_bytes,
    get_file_icon_name,
    get_threedi_api,
)
from rana_qgis_plugin.utils_api import (
    get_tenant_file_descriptor,
    get_tenant_project_file,
    get_threedi_schematisation,
)
from rana_qgis_plugin.utils_spatial import get_bbox_area_in_m2
from rana_qgis_plugin.widgets.utils_file_action import (
    FileAction,
    FileActionSignals,
    get_file_actions_for_data_type,
)
from rana_qgis_plugin.widgets.utils_icons import get_icon_from_theme, get_icon_label


@dataclass
class InfoRow:
    key: str
    value: Any
    key_tooltip: Optional[str] = None
    value_tooltip: Optional[str] = None

    @staticmethod
    def get_label_widget(value: str, tooltip: Optional[str], parent) -> QLabel:
        label = QLabel(value, parent=parent)
        # ensure correct size hints for the labels
        label.setMinimumHeight(label.fontMetrics().height() + 4)
        if tooltip:
            label.setToolTip(tooltip)
        return label

    def get_key_widget(self, parent) -> QLabel:
        return self.get_label_widget(self.key, self.key_tooltip, parent)

    def get_value_widget(self, parent) -> QLabel:
        return self.get_label_widget(str(self.value), self.value_tooltip, parent)


class EditLabel(QLineEdit):
    def __init__(self, text, parent=None, start_editable=False):
        super().__init__(text, parent)
        if start_editable:
            self.make_editable()
        else:
            self.make_readonly()

    def make_editable(self):
        self.setReadOnly(False)
        self.setStyleSheet("")
        self.setFrame(True)

    def make_readonly(self):
        self.setReadOnly(True)
        self.setStyleSheet("""
            QLineEdit {
                background: transparent;
                border: none;
                padding: 0px;
            }
        """)
        self.setFrame(False)


class FileView(QWidget):
    file_showed = pyqtSignal()
    show_revisions_clicked = pyqtSignal(dict, dict)

    def __init__(
        self, communication, file_signals: FileActionSignals, avatar_cache, parent=None
    ):
        super().__init__(parent)
        self.communication = communication
        self.selected_file = None
        self.avatar_cache = avatar_cache
        self.project = None
        self.file_signals = file_signals
        self.setup_ui()
        self.no_refresh = False

    def update_project(self, project: dict):
        self.project = project

    def setup_ui(self):
        self.general_box = QgsCollapsibleGroupBox("General")
        self.general_box.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum
        )
        self.general_box.setAlignment(Qt.AlignTop)
        self.general_box.setContentsMargins(0, 0, 0, 0)
        # Set filename_edit, this will be replaced on updating the contents of self.general_box
        self.filename_edit = EditLabel("")
        self.more_box = QgsCollapsibleGroupBox("More information")
        self.files_box = QgsCollapsibleGroupBox("Related files")
        self.files_table = QTableView()
        self.files_table.setSortingEnabled(False)
        self.files_table.verticalHeader().hide()
        self.files_table.setEditTriggers(QTableView.NoEditTriggers)
        self.files_model = QStandardItemModel()
        self.files_table.setModel(self.files_model)
        self.files_model.setColumnCount(3)
        self.files_model.setHorizontalHeaderLabels(["Name", "Type", "Size"])
        self.files_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        files_layout = QVBoxLayout()
        files_layout.addWidget(self.files_table)
        self.files_box.setLayout(files_layout)

        # put all collabpsibles in a container, this seems to help with correct spacing
        collapsible_container = QWidget()
        collapsible_layout = QVBoxLayout(collapsible_container)
        collapsible_layout.setContentsMargins(0, 0, 0, 0)
        collapsible_layout.setSpacing(0)
        collapsible_layout.addWidget(self.general_box)
        collapsible_layout.addWidget(self.more_box)
        collapsible_layout.addWidget(self.files_box)
        collapsible_layout.addStretch()

        button_layout = QHBoxLayout()
        self.btn_start_simulation = QPushButton("Start Simulation")
        self.btn_create_model = QPushButton("Create Rana Model")
        self.btn_stack = QStackedWidget()
        self.btn_stack.setFixedHeight(self.btn_start_simulation.sizeHint().height())
        self.btn_stack.addWidget(self.btn_start_simulation)
        self.btn_stack.addWidget(self.btn_create_model)
        btn_show_revisions = QPushButton(FileAction.VIEW_REVISIONS.value)
        btn_show_revisions.clicked.connect(
            lambda _: self.file_signals.view_all_revisions_requested.emit(
                self.project, self.selected_file
            )
        )
        self.btn_stack.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        btn_show_revisions.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        button_layout.addWidget(self.btn_stack)
        button_layout.addWidget(btn_show_revisions)
        self.file_action_btn_dict = self.get_file_action_buttons()
        file_action_btn_layout = QHBoxLayout()
        for btn in self.file_action_btn_dict.values():
            file_action_btn_layout.addWidget(btn)

        # Put everything in the widget layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(collapsible_container)
        layout.addLayout(file_action_btn_layout)
        layout.addLayout(button_layout)
        self.setLayout(layout)

    def toggle_interactions(self, enabled: bool):
        buttons = self.findChildren(QPushButton)
        for button in buttons:
            button.setEnabled(enabled)

    def get_file_action_buttons(self) -> dict[FileAction, QPushButton]:
        btn_dict = {}
        for action in sorted(FileAction):
            if action == FileAction.VIEW_REVISIONS:
                continue
            btn = QPushButton(action.value)
            action_signal = self.file_signals.get_signal(action)
            if action == FileAction.RENAME:
                btn.clicked.connect(lambda _: self.edit_file_name(self.selected_file))
            else:
                btn.clicked.connect(
                    lambda _, signal=action_signal: signal.emit(self.selected_file)
                )
            # hide buttons by default to prevent big width in size hint
            # update_file_action_buttons ensures buttons are correctly shown on display
            btn.hide()
            btn_dict[action] = btn
        return btn_dict

    def edit_file_name(self, selected_item: dict):
        current_name = self.filename_edit.text()
        self.no_refresh = True

        def finish_editing():
            self.filename_edit.editingFinished.disconnect(finish_editing)
            self.filename_edit.make_readonly()
            if current_name != self.filename_edit.text():
                self.file_signals.get_signal(FileAction.RENAME).emit(
                    selected_item, self.filename_edit.text()
                )
                self.selected_file["id"] = self.filename_edit.text()
            self.toggle_interactions(True)
            self.no_refresh = False

        self.toggle_interactions(False)
        self.filename_edit.make_editable()

        # Set up single-shot connection
        self.filename_edit.editingFinished.connect(finish_editing)

        # Set focus to the edit field
        self.filename_edit.setFocus()
        self.filename_edit.selectAll()

    def update_file_action_buttons(self, selected_file: dict):
        active_actions = get_file_actions_for_data_type(selected_file)
        for action in FileAction:
            btn = self.file_action_btn_dict.get(action)
            if not btn:
                continue
            if action in active_actions:
                btn.show()
            else:
                btn.hide()

    def update_selected_file(self, selected_file: dict):
        self.selected_file = selected_file

    @staticmethod
    def _get_dem_raster_file(revision):
        if "rasters" in revision:
            return next(
                (
                    raster
                    for raster in revision["rasters"]
                    if raster["type"] == "dem_file"
                ),
                None,
            )

    @staticmethod
    def _get_crs_str(data_type, meta, revision) -> str:
        if data_type == "scenario" and meta:
            return meta.get("grid", {}).get("crs")
        elif data_type == "threedi_schematisation" and revision:
            dem = FileView._get_dem_raster_file(revision)
            if dem:
                return f"EPSG:{dem['epsg_code']}"
        elif meta.get("extent"):
            return meta["extent"].get("crs")
        return ""

    @staticmethod
    def _get_area_str(data_type, meta, revision):
        """Return bounding box as [x1, y1, x2, y2]"""
        area = None
        if data_type == "scenario" and meta:
            # use grid['x'] and grid['y'] which is always in meters
            grid = meta.get("grid")
            if grid:
                area = (
                    grid["x"]["cell_size"]
                    * grid["x"]["size"]
                    * grid["y"]["size"]
                    * grid["y"]["cell_size"]
                )
        else:
            if data_type == "threedi_schematisation" and revision:
                # compute area based on DEM for 2D models and skip for models without dem
                dem = FileView._get_dem_raster_file(revision)
                if dem:
                    coord = dem["extent"]["coordinates"]
                    # re-organize bbox coordinates to match return format
                    # extent in threedi-api has a fixed crs
                    area = get_bbox_area_in_m2([*coord[0], *coord[1]], "EPSG:4326")
            elif meta.get("extent"):
                area = get_bbox_area_in_m2(
                    meta["extent"].get("bbox"),
                    FileView._get_crs_str(data_type, meta, revision),
                )
        if area:
            return f"{area / 1e6:.2f} km²"
        return ""

    def update_general_box(self, selected_file: dict):
        rows = []
        # line 1: icon - filename - size
        file_icon = get_icon_from_theme(get_file_icon_name(selected_file["data_type"]))
        file_icon_label = get_icon_label(file_icon)
        filename = Path(selected_file["id"]).name
        size_str = (
            display_bytes(selected_file["size"])
            if selected_file["data_type"] != "threedi_schematisation"
            else "N/A"
        )
        self.filename_edit.setText(filename)
        self.filename_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.filename_edit.adjustSize()

        rows.append([file_icon_label, self.filename_edit, QLabel(size_str)])
        # line 2: user icon - user name - commit msg - time
        # Note that the avatar is not automatically refreshed!
        user_icon_label = get_icon_label(
            self.avatar_cache.get_avatar_for_user(selected_file["user"])
        )
        username = (
            selected_file["user"]["given_name"]
            + " "
            + selected_file["user"]["family_name"]
        )
        if selected_file["data_type"] == "threedi_schematisation":
            schematisation = get_threedi_schematisation(
                self.communication, selected_file["descriptor_id"]
            )
            msg = schematisation["latest_revision"]["commit_message"]
            last_modified = convert_to_local_time(
                schematisation["latest_revision"]["commit_date"]
            )
        else:
            descriptor = get_tenant_file_descriptor(selected_file["descriptor_id"])
            msg = descriptor.get("description")
            last_modified = convert_to_local_time(selected_file["last_modified"])
        msg_label = QLabel(msg)
        msg_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Ignored)

        msg_label.setWordWrap(True)
        rows.append(
            [
                user_icon_label,
                QLabel(f"<b>{username}</b>"),
                msg_label,
                QLabel(last_modified),
            ]
        )
        # Refresh contents of general box
        container = QWidget(self.general_box)
        layout = QVBoxLayout(container)
        for row in rows:
            row_layout = QHBoxLayout()
            for item in row[:-1]:
                item.setParent(container)
                row_layout.addWidget(item)
            row_layout.addStretch()
            row[-1].setParent(container)
            row_layout.addWidget(row[-1])
            layout.addLayout(row_layout)
        # assign existing layout to temporary widget
        # this will be deleted once the scope of this method is over
        if self.general_box.layout():
            QWidget().setLayout(self.general_box.layout())
        self.general_box.setLayout(layout)

    def update_more_box(self, selected_file):
        descriptor = get_tenant_file_descriptor(selected_file["descriptor_id"])
        meta = descriptor.get("meta") if descriptor else None
        data_type = selected_file.get("data_type")
        revision = None
        if data_type == "threedi_schematisation":
            schematisation_base = get_threedi_schematisation(
                self.communication, selected_file["descriptor_id"]
            )
            if schematisation_base:
                revision = schematisation_base["latest_revision"]
        crs_str = self._get_crs_str(data_type, meta, revision)
        details = [
            # InfoRow("Area", self._get_area_str(data_type, meta, revision)),
            InfoRow("Projection", crs_str),
            InfoRow("Type", SUPPORTED_DATA_TYPES.get(data_type, data_type)),
        ]
        if data_type != "threedi_schematisation":
            details.append(InfoRow("Storage", display_bytes(selected_file["size"])))
        if data_type == "scenario" and meta:
            simulation = meta["simulation"]
            schematisation = meta["schematisation"]
            interval = simulation["interval"]
            if interval:
                start = convert_to_local_time(interval[0])
                end = convert_to_local_time(interval[1])
            else:
                start = "N/A"
                end = "N/A"
            details += [
                InfoRow("Simulation name", simulation["name"]),
                InfoRow("Simulation ID", simulation["id"]),
                InfoRow("Schematisation name", schematisation["name"]),
                InfoRow("Schematisation ID", schematisation["id"]),
                InfoRow("Schematisation version", schematisation["version"]),
                InfoRow("Revision ID", schematisation["revision_id"]),
                InfoRow("Model ID", schematisation["model_id"]),
                InfoRow("Model software", simulation["software"]["id"]),
                InfoRow("Software version", simulation["software"]["version"]),
                InfoRow("Start", start),
                InfoRow("End", end),
            ]
        if data_type == "threedi_schematisation" and revision:
            schematisation = schematisation_base["schematisation"]
            valid_revision = revision.get("has_threedimodel")
            if valid_revision:
                tc = ThreediCalls(get_threedi_api())
                threedi_models = tc.fetch_schematisation_revision_3di_models(
                    schematisation["id"], revision["id"]
                )
                valid_model = next(
                    (
                        model
                        for model in threedi_models
                        if model.is_valid and not model.disabled
                    ),
                    None,
                )
            details += [
                InfoRow("Schematisation name", schematisation["name"]),
                InfoRow("Schematisation ID", schematisation["id"]),
                InfoRow(
                    "Schematisation description",
                    schematisation["meta"].get("description"),
                ),
                InfoRow(
                    "Schematisation created by",
                    schematisation["created_by_first_name"]
                    + " "
                    + schematisation["created_by_last_name"],
                ),
                InfoRow(
                    "Schematisation created on",
                    convert_to_local_time(schematisation["created"]),
                ),
                InfoRow(
                    "Schematisation tags",
                    "; ".join(schematisation["tags"]) if schematisation["tags"] else "",
                ),
                InfoRow("Latest revision ID", revision["id"] if revision else ""),
                InfoRow(
                    "Latest revision number", revision["number"] if revision else None
                ),
                InfoRow(
                    "Latest revision valid", "Yes" if revision.get("is_valid") else "No"
                ),
                InfoRow(
                    "Latest revision is simulation ready",
                    "Yes" if valid_model else "No",
                ),
                InfoRow("Node count", valid_model.nodes_count if valid_model else ""),
                InfoRow("Line count", valid_model.lines_count if valid_model else ""),
            ]

        # Refresh contents of general box
        container = QWidget(self.more_box)
        layout = QGridLayout(container)
        for row_idx, info_row in enumerate(details):
            layout.addWidget(info_row.get_key_widget(parent=container), row_idx, 0)
            layout.addWidget(info_row.get_value_widget(parent=container), row_idx, 1)

        layout.setColumnStretch(1, 1)
        # assign existing layout to temporary widget
        # this will be deleted once the scope of this method is over
        if self.more_box.layout():
            QWidget().setLayout(self.more_box.layout())
        self.more_box.setLayout(layout)

    def update_files_box(self, selected_file):
        # only show files for schematisation with revision
        if selected_file["data_type"] != "threedi_schematisation":
            self.files_box.hide()
            return
        schematisation = get_threedi_schematisation(
            self.communication, selected_file["descriptor_id"]
        )
        if not schematisation:
            self.files_box.hide()
            return
        rows = []
        revision = schematisation["latest_revision"]
        sqlite_file = revision.get("sqlite", {}).get("file")
        if sqlite_file:
            rows.append(
                [
                    sqlite_file.get("filename"),
                    sqlite_file.get("type"),
                    sqlite_file.get("size"),
                ]
            )
        rasters = revision.get("rasters", [])
        for raster in rasters:
            raster_file = raster.get("file")
            if raster_file:
                rows.append(
                    [
                        raster_file.get("filename"),
                        raster.get("type"),
                        raster_file.get("size"),
                    ]
                )
        self.files_model.clear()
        self.files_model.setHorizontalHeaderLabels(["Name", "Type", "Size"])
        for file_name, data_type, file_size in rows:
            file_type_icon = get_icon_from_theme(get_file_icon_name(data_type))
            name_item = QStandardItem(file_name)
            name_item.setIcon(QIcon(file_type_icon))
            data_type_item = QStandardItem(
                SUPPORTED_DATA_TYPES.get(data_type, data_type)
            )
            size_item = NumericItem(display_bytes(file_size))
            size_item.setData(file_size, role=Qt.ItemDataRole.UserRole)
            self.files_model.appendRow([name_item, data_type_item, size_item])
        self.files_box.show()

    def show_selected_file_details(self, selected_file):
        self.selected_file = selected_file
        self.update_general_box(selected_file)
        self.update_more_box(selected_file)
        self.update_files_box(selected_file)
        if selected_file.get("data_type") == "threedi_schematisation":
            schematisation = get_threedi_schematisation(
                self.communication, selected_file["descriptor_id"]
            )
            if schematisation:
                revision = schematisation["latest_revision"]
                self.btn_stack.show()
                if revision and revision.get("has_threedimodel"):
                    self.btn_stack.setCurrentIndex(0)
                else:
                    self.btn_stack.setCurrentIndex(1)
            else:
                self.btn_stack.hide()
        else:
            self.btn_stack.hide()
        self.update_file_action_buttons(selected_file)

    def refresh(self):
        # Skip refresh because user is interacting with state of the file
        if self.no_refresh:
            return
        # Get fresh object to retrieve correct last_modified
        updated_file = get_tenant_project_file(
            self.project["id"], {"path": self.selected_file["id"]}
        )
        # Only update if new file is still there
        if updated_file:
            self.selected_file = updated_file
            last_modified_key = (
                f"{self.project['name']}/{self.selected_file['id']}/last_modified"
            )
            QSettings().setValue(last_modified_key, self.selected_file["last_modified"])
            self.show_selected_file_details(self.selected_file)
