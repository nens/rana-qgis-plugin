import math
import os
import time
from collections import namedtuple
from enum import Enum
from pathlib import Path
from typing import List

from qgis.gui import QgsCollapsibleGroupBox
from qgis.PyQt.QtCore import (
    QEvent,
    QModelIndex,
    QObject,
    QRectF,
    QSettings,
    QSize,
    Qt,
    QTimer,
    QUrl,
    pyqtSignal,
    pyqtSlot,
)
from qgis.PyQt.QtGui import (
    QAction,
    QDesktopServices,
    QIcon,
    QImage,
    QPainter,
    QPainterPath,
    QPixmap,
    QStandardItem,
    QStandardItemModel,
)
from qgis.PyQt.QtSvg import QSvgWidget
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLayout,
    QLineEdit,
    QMenu,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QStackedWidget,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QToolButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from rana_qgis_plugin.communication import UICommunication
from rana_qgis_plugin.constant import SUPPORTED_DATA_TYPES
from rana_qgis_plugin.icons import (
    ICONS_DIR,
    dir_icon,
    ellipsis_icon,
    file_icon,
    refresh_icon,
    separator_icon,
)
from rana_qgis_plugin.simulation.threedi_calls import (
    ThreediCalls,
)
from rana_qgis_plugin.utils import (
    NumericItem,
    convert_to_local_time,
    convert_to_timestamp,
    display_bytes,
    elide_text,
    get_file_icon_name,
    get_threedi_api,
    get_timestamp_as_numeric_item,
)
from rana_qgis_plugin.utils_api import (
    get_tenant_file_descriptor,
    get_tenant_id,
    get_tenant_project_file,
    get_tenant_project_file_history,
    get_tenant_project_files,
    get_tenant_projects,
    get_threedi_schematisation,
    get_user_info,
)
from rana_qgis_plugin.utils_settings import base_url
from rana_qgis_plugin.utils_spatial import get_bbox_area_in_m2
from rana_qgis_plugin.widgets.processes_browser import ProcessesBrowser
from rana_qgis_plugin.widgets.utils_avatars import (
    AvatarCache,
)
from rana_qgis_plugin.widgets.utils_delegates import ContributorAvatarsDelegate
from rana_qgis_plugin.widgets.utils_file_action import (
    FileAction,
    FileActionSignals,
    get_file_actions_for_data_type,
)
from rana_qgis_plugin.widgets.utils_icons import (
    get_icon_from_theme,
    get_icon_label,
)

# allow for using specific data just for sorting
SORT_ROLE = Qt.ItemDataRole.UserRole + 1


class RevisionsView(QWidget):
    new_simulation_clicked = pyqtSignal(int)
    create_3di_model_clicked = pyqtSignal(int)
    delete_3di_model_clicked = pyqtSignal(int)
    open_schematisation_revision_in_qgis_requested = pyqtSignal(dict, dict)
    busy = pyqtSignal()
    ready = pyqtSignal()

    def __init__(self, communication, parent=None):
        super().__init__(parent)
        self.communication = communication
        self.revisions = []
        self.selected_file = None
        self.project = None
        self.setup_ui()

    def setup_ui(self):
        self.revisions_table = QTableView()
        self.revisions_table.setSortingEnabled(True)
        self.revisions_table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.revisions_table.verticalHeader().hide()
        self.revisions_model = QStandardItemModel()
        self.revisions_table.setModel(self.revisions_model)
        self.revisions_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        self.revisions_table.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.revisions_table.customContextMenuRequested.connect(self.menu_requested)
        self.revisions_table.setShowGrid(False)
        self.revisions_table.horizontalHeader().setFrameStyle(0)
        layout = QVBoxLayout(self)
        layout.addWidget(self.revisions_table)
        self.setLayout(layout)

    def show_revisions_for_file(self, project: dict, selected_file: dict):
        self.project = project
        self.selected_file = selected_file
        self.show_revisions()

    def menu_requested(self, pos):
        index = self.revisions_table.indexAt(pos)
        revision_item = self.revisions_model.itemFromIndex(index)
        if not revision_item:
            return
        data = revision_item.data()
        if not data:
            return
        threedi_revision, schematisation = data
        if threedi_revision:
            menu = QMenu(self)
            action = QAction("Open in QGIS", self)
            action.triggered.connect(
                lambda _: self.open_schematisation_revision_in_qgis_requested.emit(
                    threedi_revision.to_dict(), schematisation["schematisation"]
                )
            )
            menu.addAction(action)
        menu.popup(self.revisions_table.viewport().mapToGlobal(pos))

    def refresh(self):
        self.show_revisions()

    def show_revisions(self):
        self.busy.emit()
        selected_file = self.selected_file
        # collect rows to show in widget, format: [date_str, event, (button_label, signal_func), revision, schematisation]
        rows = []
        BTNData = namedtuple("BTNData", ["label", "func", "enabled", "tooltip"])
        if selected_file.get("data_type") == "threedi_schematisation":
            # retrieve schematisation and revisions
            schematisation = get_threedi_schematisation(
                self.communication, selected_file["descriptor_id"]
            )
            threedi_api = get_threedi_api()
            tc = ThreediCalls(threedi_api)
            revisions = tc.fetch_schematisation_revisions(
                schematisation["schematisation"]["id"]
            )
            # Check number of models and enable creation if max has been reached
            create_enabled = True
            create_tooltip = None
            if (
                sum(revision.has_threedimodel for revision in revisions)
                >= schematisation["schematisation"]["threedimodel_limit"]
            ):
                create_enabled = False
                create_tooltip = "The maximum number of Rana models has been reached. Please delete one of the existing models before creating a new one."
            # Extract data from each revision
            for i, revision in enumerate(revisions):
                commit_date = revision.commit_date.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                latest = revision.id == schematisation["latest_revision"]["id"]
                tooltip = (
                    "A Rana model must be created before a simulation can be started."
                    if not revision.has_threedimodel
                    else None
                )
                sim_btn_data = BTNData(
                    "New",
                    lambda _, rev_id=revision.id: self.new_simulation_clicked.emit(
                        rev_id
                    ),
                    revision.has_threedimodel,
                    tooltip,
                )
                if revision.has_threedimodel:
                    model_btn_data = BTNData(
                        "Delete",
                        lambda _,
                        rev_id=revision.id: self.delete_3di_model_clicked.emit(rev_id),
                        True,
                        None,
                    )
                else:
                    model_btn_data = BTNData(
                        "Create",
                        lambda _,
                        rev_id=revision.id: self.create_3di_model_clicked.emit(rev_id),
                        create_enabled,
                        create_tooltip,
                    )
                rows.append(
                    [
                        commit_date,
                        revision.commit_message,
                        sim_btn_data,
                        model_btn_data,
                        revision,
                        schematisation,
                        latest,
                    ]
                )
        else:
            history = get_tenant_project_file_history(
                self.project["id"], {"path": self.selected_file["id"]}
            )
            for item in history["items"]:
                rows.append([item["created_at"], item["message"]])

        # Populate table
        self.revisions_model.clear()
        if selected_file.get("data_type") == "threedi_schematisation":
            self.revisions_model.setColumnCount(5)
            self.revisions_model.setHorizontalHeaderLabels(
                ["#", "Timestamp", "Event", "Simulation", "Rana Model"]
            )
        else:
            self.revisions_model.setColumnCount(2)
            self.revisions_model.setHorizontalHeaderLabels(["Timestamp", "Event"])
        latest = False
        threedi_revision = sim_btn_data = model_btn_data = threedi_schematisation = None
        for i, (commit_date, event, *schematisation_related) in enumerate(rows):
            row = []
            if schematisation_related:
                (
                    sim_btn_data,
                    model_btn_data,
                    threedi_revision,
                    threedi_schematisation,
                    latest,
                ) = schematisation_related
                nr_item = NumericItem(str(threedi_revision.number))
                nr_item.setData(threedi_revision.number, role=Qt.ItemDataRole.UserRole)
                row.append(nr_item)
            commit_item = get_timestamp_as_numeric_item(commit_date)
            if latest:
                commit_item.setText(commit_item.text() + " (latest)")
            # We store the revision object for loading specific revisions in menu_requested.
            if threedi_revision:
                commit_item.setData((threedi_revision, threedi_schematisation))
            row += [commit_item, QStandardItem(event)]
            self.revisions_model.appendRow(row)
            for col_idx, btn_data in enumerate([sim_btn_data, model_btn_data], 3):
                if btn_data:
                    btn = QPushButton(btn_data.label)
                    btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
                    btn.clicked.connect(btn_data.func)
                    btn.setEnabled(btn_data.enabled)
                    if btn_data.tooltip:
                        btn.setToolTip(btn_data.tooltip)
                    container = QWidget()
                    container.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
                    layout = QVBoxLayout(container)
                    layout.setContentsMargins(0, 0, 0, 0)
                    layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    layout.addWidget(btn)
                    container.adjustSize()
                    self.revisions_table.setIndexWidget(
                        self.revisions_model.index(i, col_idx), container
                    )

        if threedi_revision:
            resize_columns = [0, 1, 3, 4]
        else:
            resize_columns = [0]
        for col_idx in resize_columns:
            self.revisions_table.horizontalHeader().setSectionResizeMode(
                col_idx, QHeaderView.ResizeToContents
            )
        self.ready.emit()


def _clear_layout(layout):
    """Remove widgets/layouts stored in a layout (Qt-safe)."""
    while layout and layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w:
            w.deleteLater()
        elif item.layout():
            _clear_layout(item.layout())


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

    @staticmethod
    def _get_size_str(data_type, selected_file) -> str:
        if data_type != "threedi_schematisation":
            return display_bytes(selected_file["size"])
        return "N/A"

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
            schematisation = get_threedi_schematisation(
                self.communication, selected_file["descriptor_id"]
            )
            if schematisation:
                revision = schematisation["latest_revision"]
        crs_str = self._get_crs_str(data_type, meta, revision)
        details = [
            ("Area", self._get_area_str(data_type, meta, revision)),
            ("Projection", crs_str),
            ("Kind", data_type),
            ("Storage", self._get_size_str(data_type, selected_file)),
        ]
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
                ("Simulation name", simulation["name"]),
                ("Simulation ID", simulation["id"]),
                ("Schematisation name", schematisation["name"]),
                ("Schematisation ID", schematisation["id"]),
                ("Schematisation version", schematisation["version"]),
                ("Revision ID", schematisation["revision_id"]),
                ("Model ID", schematisation["model_id"]),
                ("Model software", simulation["software"]["id"]),
                ("Software version", simulation["software"]["version"]),
                ("Start", start),
                ("End", end),
            ]
        if data_type == "threedi_schematisation" and revision:
            details += [
                ("Schematisation ID", schematisation["schematisation"]["id"]),
                ("Latest revision ID", revision["id"] if revision else None),
                (
                    "Latest revision number",
                    revision["number"] if revision else None,
                ),
            ]

        # Refresh contents of general box
        container = QWidget(self.more_box)
        layout = QGridLayout(container)
        for row, (label, value) in enumerate(details):
            layout.addWidget(QLabel(label, parent=container), row, 0)
            layout.addWidget(QLabel(str(value), parent=container), row, 1)
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
                    [raster_file.get("filename"), "raster", raster_file.get("size")]
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


class CreateFolderDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout()
        label = QLabel("Enter folder name:")
        self.input = QLineEdit()
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        layout.addWidget(label)
        layout.addWidget(self.input)
        layout.addWidget(button_box)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        self.setWindowTitle("Create New Folder")
        self.setLayout(layout)

    def folder_name(self) -> str:
        return self.input.text().strip()


class FileBrowserModel(QStandardItemModel):
    def sort(self, column, order=Qt.SortOrder.AscendingOrder):
        self.layoutAboutToBeChanged.emit()

        directories = []
        files = []

        # First separate directories and files
        while self.rowCount() > 0:
            row_items = self.takeRow(0)
            if not row_items:
                continue
            item_type = row_items[0].data(Qt.ItemDataRole.UserRole).get("type")
            if item_type == "directory":
                sort_text = row_items[0].data(Qt.ItemDataRole.DisplayRole) or ""
                directories.append((row_items, sort_text))
            else:
                # try to use SORT_ROLE data before using UserRole data for sorting
                sort_text = (
                    row_items[column].data(SORT_ROLE)
                    or row_items[column].data(Qt.ItemDataRole.UserRole)
                    or ""
                )
                files.append((row_items, sort_text))

        # Sort directories and files separately
        # only changing on directory name should affect directory sorting
        if column == 0:
            directories.sort(
                key=lambda x: x[1],
                reverse=(order == Qt.SortOrder.DescendingOrder),
            )
        files.sort(key=lambda x: x[1], reverse=(order == Qt.SortOrder.DescendingOrder))
        # Always add directories first, then files
        for row_items, _ in directories:
            self.appendRow(row_items)
        for row_items, _ in files:
            self.appendRow(row_items)
        self.layoutChanged.emit()


class FilesBrowser(QWidget):
    folder_selected = pyqtSignal(str)
    file_selected = pyqtSignal(dict)
    path_changed = pyqtSignal(str)
    create_folder_requested = pyqtSignal(str)
    busy = pyqtSignal()
    ready = pyqtSignal()

    def __init__(self, communication, file_signals: FileActionSignals, parent=None):
        super().__init__(parent)
        self.project = None
        self.communication = communication
        self.selected_item = None
        self.file_signals = file_signals
        self.setup_ui()

    def update_project(self, project: dict):
        self.project = project
        self.selected_item = {"id": "", "type": "directory"}
        self.fetch_and_populate(project)

    def setup_ui(self):
        self.files_tv = QTreeView()
        self.files_tv.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.files_tv.customContextMenuRequested.connect(self.menu_requested)
        self.files_model = FileBrowserModel()
        self.files_tv.setModel(self.files_model)
        self.files_tv.setSortingEnabled(True)
        self.files_tv.header().setSortIndicatorShown(True)
        self.files_tv.doubleClicked.connect(self.select_file_or_directory)
        self.btn_upload = QPushButton("Upload Files to Rana")
        btn_create_folder = QPushButton("Create New Folder")
        btn_create_folder.clicked.connect(self.show_create_folder_dialog)
        self.btn_new_schematisation = QPushButton("New schematisation")
        self.btn_import_schematisation = QPushButton("Import schematisation")
        btn_layout = QGridLayout()
        btn_layout.addWidget(self.btn_upload, 0, 0)
        btn_layout.addWidget(btn_create_folder, 0, 1)
        btn_layout.addWidget(self.btn_new_schematisation, 1, 0)
        btn_layout.addWidget(self.btn_import_schematisation, 1, 1)
        layout = QVBoxLayout(self)
        layout.addWidget(self.files_tv)
        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def show_create_folder_dialog(self):
        # Make sure this button cannot do anything if the files browser is not in a folder
        dialog = CreateFolderDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.create_folder_requested.emit(dialog.folder_name())

    def refresh(self):
        self.fetch_and_populate(self.project, self.selected_item["id"])
        self.communication.clear_message_bar()

    def select_path(self, selected_path: str):
        # Root level path is expected to be ""
        if selected_path in ["/", "./"]:
            selected_path = ""
        self.selected_item = {"id": selected_path, "type": "directory"}
        self.fetch_and_populate(self.project, selected_path)

    def update(self):
        selected_path = self.selected_item["id"]
        selected_name = Path(selected_path.rstrip("/")).name
        if self.selected_item["type"] == "directory":
            self.fetch_and_populate(self.project, selected_path)
            self.folder_selected.emit(selected_name)
        else:
            self.file_selected.emit(self.selected_item)
        self.communication.clear_message_bar()

    def menu_requested(self, pos):
        index = self.files_tv.indexAt(pos)
        file_item = self.files_model.itemFromIndex(index)
        if not file_item:
            return
        selected_item = file_item.data(Qt.ItemDataRole.UserRole)
        file_actions = get_file_actions_for_data_type(selected_item)
        menu = QMenu(self)
        actions = []
        # create and connect actions
        for file_action in file_actions:
            action = QAction(file_action.value, self)
            action_signal = self.file_signals.get_signal(file_action)
            if file_action == FileAction.RENAME:
                action.triggered.connect(
                    lambda _, selected_item=selected_item: self.edit_file_name(
                        index, selected_item
                    )
                )
            elif file_action == FileAction.VIEW_REVISIONS:
                action.triggered.connect(
                    lambda _, signal=action_signal: signal.emit(
                        self.project, selected_item
                    )
                )
            else:
                action.triggered.connect(
                    lambda _, signal=action_signal: signal.emit(selected_item)
                )
            actions.append(action)
        for i, action in enumerate(actions):
            if file_actions[i] == FileAction.DELETE:
                menu.addSeparator()
            menu.addAction(action)
        menu.popup(self.files_tv.viewport().mapToGlobal(pos))

    def edit_file_name(self, index: QModelIndex, selected_item: dict):
        self.files_model.itemFromIndex(index).setFlags(
            Qt.ItemFlag.ItemIsEditable
            | Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
        )

        def handle_data_changed(topLeft, bottomRight, roles):
            if topLeft == index:  # Only handle the specific item we're editing
                new_name = self.files_model.itemFromIndex(topLeft).text()
                signal = self.file_signals.get_signal(FileAction.RENAME)
                signal.emit(selected_item, new_name)
                self.files_model.dataChanged.disconnect(handle_data_changed)

        # Connect to dataChanged signal
        self.files_model.dataChanged.connect(handle_data_changed)

        # Enter editing mode
        self.files_tv.edit(index)

    def select_file_or_directory(self, index: QModelIndex):
        self.busy.emit()
        self.communication.progress_bar("Loading files...", clear_msg_bar=True)
        # Only allow selection of the first column (filename)
        if index.column() != 0:
            return
        file_item = self.files_model.itemFromIndex(index)
        self.selected_item = file_item.data(Qt.ItemDataRole.UserRole)
        self.update()
        self.ready.emit()

    def fetch_and_populate(self, project: dict, path: str = None):
        params = {"limit": 1000}
        if path:
            params["path"] = path
        self.files = get_tenant_project_files(self.communication, project["id"], params)
        sort_column = self.files_tv.header().sortIndicatorSection()
        sort_order = self.files_tv.header().sortIndicatorOrder()
        self.files_model.clear()
        header = ["Filename", "Data type", "Size", "Last modified"]
        self.files_model.setHorizontalHeaderLabels(header)
        directories = [file for file in self.files if file["type"] == "directory"]
        files = [file for file in self.files if file["type"] == "file"]

        # Add directories first
        for directory in directories:
            dir_name = os.path.basename(directory["id"].rstrip("/"))
            name_item = QStandardItem(dir_icon, dir_name)
            name_item.setToolTip(dir_name)
            name_item.setData(directory, role=Qt.ItemDataRole.UserRole)
            name_item.setData(dir_name.lower(), role=SORT_ROLE)
            self.files_model.appendRow([name_item])

        # Add files second
        for file in files:
            file_name = os.path.basename(file["id"].rstrip("/"))
            name_item = QStandardItem(file_icon, file_name)
            name_item.setToolTip(file_name)
            name_item.setData(file, role=Qt.ItemDataRole.UserRole)
            name_item.setData(file_name.lower(), role=SORT_ROLE)
            data_type = file["data_type"]
            data_type_item = QStandardItem(
                SUPPORTED_DATA_TYPES.get(data_type, data_type)
            )
            size_display = (
                display_bytes(file["size"])
                if data_type != "threedi_schematisation"
                else "N/A"
            )
            size_item = NumericItem(size_display)
            size_item.setData(
                file["size"] if data_type != "threedi_schematisation" else -1,
                role=Qt.ItemDataRole.UserRole,
            )
            last_modified_item = get_timestamp_as_numeric_item(file["last_modified"])
            # Add items to the model
            self.files_model.appendRow(
                [name_item, data_type_item, size_item, last_modified_item]
            )

        self.files_tv.sortByColumn(sort_column, sort_order)
        self.files_tv.setSortingEnabled(True)

        for i in range(len(header)):
            self.files_tv.resizeColumnToContents(i)
        self.files_tv.setColumnWidth(0, 300)


class ProjectsBrowser(QWidget):
    projects_refreshed = pyqtSignal()
    project_selected = pyqtSignal(dict)
    busy = pyqtSignal()
    ready = pyqtSignal()
    users_refreshed = pyqtSignal(list)

    def __init__(self, communication, avatar_cache, parent=None):
        super().__init__(parent)
        self.communication = communication
        self.projects = []
        self.users = []
        self.filtered_projects = []
        self.current_page = 1
        self.items_per_page = 100
        self.project = None
        self.avatar_cache = avatar_cache
        # collect data
        self.fetch_projects()
        self.update_users()
        self.setup_ui()
        self.populate_contributors()
        self.sort_projects(2, Qt.SortOrder.AscendingOrder, populate=False)
        self.populate_projects()

    def set_project_from_id(self, project_id: str):
        for project in self.projects:
            if project["id"] == project_id:
                self.project = project
                return

    def setup_ui(self):
        # Create search box
        self.projects_search = QLineEdit()
        self.projects_search.setPlaceholderText("🔍 Search for project by name")
        self.projects_search.textChanged.connect(self.filter_projects)
        self.projects_search.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        # Create filter by contributor box
        self.contributor_filter = QComboBox()
        self.contributor_filter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.contributor_filter.setEditable(True)
        self.contributor_filter.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        # add auto complete
        self.contributor_filter.completer().setCaseSensitivity(
            Qt.CaseSensitivity.CaseInsensitive
        )
        # setup placeholder and reset filter on no user selected
        if self.contributor_filter.lineEdit():
            self.contributor_filter.lineEdit().setPlaceholderText("All contributors")
            self.contributor_filter.lineEdit().textChanged.connect(
                self._on_contributor_filter_text_changed
            )
        self.contributor_filter.currentIndexChanged.connect(self.filter_projects)
        # Create tree view with project files and model
        self.projects_model = QStandardItemModel()
        self.projects_tv = QTreeView()
        self.projects_tv.setModel(self.projects_model)
        self.projects_tv.setSortingEnabled(True)
        self.projects_tv.header().setSortIndicatorShown(True)
        self.projects_tv.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.projects_tv.customContextMenuRequested.connect(self.show_context_menu)
        self.projects_tv.header().sortIndicatorChanged.connect(self.sort_projects)
        self.projects_model.setHorizontalHeaderLabels(
            ["Project Name", "Contributors", "Last activity", "Created at"]
        )
        avatar_delegate = ContributorAvatarsDelegate(self.projects_tv)
        self.projects_tv.setItemDelegateForColumn(1, avatar_delegate)
        # self.projects_tv.clicked.connect(self.select_project)
        self.projects_tv.doubleClicked.connect(self.select_project)
        # Create navigation buttons
        self.btn_previous = QPushButton("<")
        self.label_page_number = QLabel("Page 1/1")
        self.btn_next = QPushButton(">")
        self.btn_previous.clicked.connect(self.to_previous_page)
        self.btn_next.clicked.connect(self.to_next_page)
        self.refresh_btn = QToolButton()
        self.refresh_btn.setToolTip("Refresh")
        self.refresh_btn.setIcon(refresh_icon)
        # Organize widgets in layouts
        top_layout = QHBoxLayout()
        top_layout.addWidget(self.projects_search)
        top_layout.addWidget(self.contributor_filter)
        top_layout.addWidget(self.refresh_btn)
        pagination_layout = QHBoxLayout()
        pagination_layout.addWidget(self.btn_previous)
        pagination_layout.addWidget(
            self.label_page_number, alignment=Qt.AlignmentFlag.AlignCenter
        )
        pagination_layout.addWidget(self.btn_next)
        layout = QVBoxLayout(self)
        layout.addLayout(top_layout)
        layout.addWidget(self.projects_tv)
        layout.addLayout(pagination_layout)
        self.setLayout(layout)

    def _on_contributor_filter_text_changed(self, text):
        # reset contribute filter with empty text
        if not text:
            self.contributor_filter.setCurrentIndex(-1)

    def fetch_projects(self):
        self.projects = get_tenant_projects(self.communication)

    def update_users(self):
        self.users = list(
            {
                contributor["id"]: contributor
                for project in self.projects
                for contributor in project["contributors"]
            }.values()
        )
        self.users_refreshed.emit(self.users)

    def refresh(self):
        self.current_page = 1
        self.fetch_projects()
        self.update_users()
        self.sort_projects(2, Qt.SortOrder.AscendingOrder, populate=False)
        if self.filter_active:
            self.filter_projects()
        else:
            self.populate_projects()
        self.populate_contributors()
        self.projects_refreshed.emit()

    @property
    def filter_active(self):
        return (
            self.projects_search.text() or self.contributor_filter.currentIndex() >= 0
        )

    def filter_projects(self):
        if not self.filter_active:
            self.filtered_projects = self.projects
        else:
            # create all filters
            project_filters = [
                self.get_projects_filtered_by_name,
                self.get_projects_filtered_by_contributor,
            ]
            # collect all project ids that are included in each active filter
            project_ids = [
                {project["id"] for project in filter_func()}
                for filter_func in project_filters
            ]
            # Find project ids that are included in all filters
            common_ids = set.intersection(*project_ids)
            self.filtered_projects = [
                project for project in self.projects if project["id"] in common_ids
            ]
        self.populate_projects()

    def get_projects_filtered_by_name(self):
        text = self.projects_search.text()
        if text:
            return [
                project
                for project in self.projects
                if text.lower() in project["name"].lower()
            ]
        else:
            return self.projects

    def get_projects_filtered_by_contributor(self):
        selected_user_id = self.contributor_filter.currentData()
        if selected_user_id is None:
            return self.projects
        else:
            selected_projects = []
            for project in self.projects:
                contributors = [
                    contributor["id"] for contributor in project.get("contributors", [])
                ]
                if selected_user_id in contributors:
                    selected_projects.append(project)
            return selected_projects

    def sort_projects(self, column_index: int, order: Qt.SortOrder, populate=True):
        # Ensure indicator is set also on direct call
        self.projects_tv.header().blockSignals(True)
        self.projects_tv.header().setSortIndicator(column_index, order)
        self.projects_tv.header().blockSignals(False)
        self.current_page = 1
        key_funcs = [
            lambda project: project["name"].lower(),
            None,
            lambda project: -convert_to_timestamp(project["last_activity"]),
            lambda project: -convert_to_timestamp(project["created_at"]),
        ]
        key_func = key_funcs[column_index]
        if key_func:
            self.projects.sort(
                key=key_func, reverse=(order == Qt.SortOrder.DescendingOrder)
            )
        if populate:
            if self.filter_active:
                self.filter_projects()
            else:
                self.populate_projects()

    def show_context_menu(self, position):
        # Get the index under the cursor
        index = self.projects_tv.indexAt(position)

        # Check if we clicked on a valid item and it's in column 0
        if not index.isValid() or index.column() != 0:
            return

        # Get the project data
        project_item = self.projects_model.itemFromIndex(index)
        project = project_item.data(Qt.ItemDataRole.UserRole)

        # Create context menu
        menu = QMenu(self)

        # Add menu actions
        open_in_qgis = menu.addAction("Open project in QGIS")
        open_in_web = menu.addAction("Open project in Rana Web")

        # Show the menu and get the selected action
        action = menu.exec(self.projects_tv.viewport().mapToGlobal(position))

        # Handle the selected action
        if action == open_in_qgis:
            self.select_project(index)
        elif action == open_in_web:
            link = f"{base_url()}/{get_tenant_id()}/projects/{project['code']}"
            QDesktopServices.openUrl(QUrl(link))

    def process_project_item(
        self, project: dict
    ) -> list[QStandardItem, QStandardItem, NumericItem]:
        project_name = project["name"]
        # Process project name into item
        name_item = QStandardItem(project_name)
        formatted_project_tooltip = (
            f"{project_name}<br><b><code>{project['code']}</code></b>"
        )
        name_item.setToolTip(formatted_project_tooltip)
        name_item.setData(project, role=Qt.ItemDataRole.UserRole)
        # Process last activity time into item
        last_activity_item = get_timestamp_as_numeric_item(project["last_activity"])
        created_at_item = get_timestamp_as_numeric_item(project["created_at"])
        # process list of contributors into items
        contributors_item = QStandardItem()
        contributors_data = []
        for i, contributor in enumerate(project.get("contributors", [])):
            avatar = (
                self.avatar_cache.get_avatar_for_user(contributor) if i < 3 else None
            )
            contributors_data.append(
                {
                    "id": contributor["id"],
                    "name": contributor["given_name"]
                    + " "
                    + contributor["family_name"],
                    "avatar": avatar,
                }
            )
        contributors_item.setData(contributors_data, Qt.ItemDataRole.UserRole)
        contributors_item.setData(-1, Qt.ItemDataRole.InitialSortOrderRole)
        return [name_item, contributors_item, last_activity_item, created_at_item]

    def populate_projects(self):
        # Paginate projects
        projects = self.filtered_projects if self.filter_active else self.projects
        start_index = (self.current_page - 1) * self.items_per_page
        end_index = start_index + self.items_per_page
        paginated_projects = projects[start_index:end_index]
        # Prepare data for adding
        processed_rows = [
            self.process_project_item(project) for project in paginated_projects
        ]
        # Remove current data just in time
        self.projects_model.removeRows(0, self.projects_model.rowCount())
        # Populate model with new data
        for row in processed_rows:
            self.projects_model.invisibleRootItem().appendRow(row)
        for i in range(self.projects_tv.header().count()):
            self.projects_tv.resizeColumnToContents(i)
        self.projects_tv.setColumnWidth(0, 300)
        self.update_pagination(projects)

    def update_avatar(self, user_id: str):
        avatar = self.avatar_cache.get_avatar_from_cache(user_id)
        # Update contributor_filter
        index = self.contributor_filter.findData(user_id)
        if index != -1:  # -1 means not found
            self.contributor_filter.setItemIcon(index, QIcon(avatar))
        # Update projects model
        root = self.projects_model.invisibleRootItem()
        for row in range(root.rowCount()):
            contributors_item = root.child(row, 1)
            contributors_data = contributors_item.data(Qt.ItemDataRole.UserRole)
            # Check if any contributors in the data match the updated one
            match = next(
                (
                    contributor
                    for contributor in contributors_data
                    if contributor["id"] == user_id
                ),
                None,
            )
            if match and match["avatar"]:
                match["avatar"] = avatar
                contributors_item.setData(contributors_data, Qt.ItemDataRole.UserRole)

    def populate_contributors(self):
        # Collect all unique contributors to the projects
        all_contributors = {
            contributor["id"]: contributor
            for project in self.projects
            for contributor in project["contributors"]
        }
        # Sort users by name, starting with the current user
        my_info = get_user_info(self.communication)
        if my_info and my_info.get("sub") in all_contributors:
            my_id = my_info["sub"]
            my_user = [all_contributors.pop(my_id)]
        else:
            my_id = None
            my_user = []
        sorted_users = my_user + sorted(
            all_contributors.values(),
            key=lambda x: f"{x['given_name']} {x['family_name']}".lower(),
        )
        # Update combo box items
        self.contributor_filter.blockSignals(True)
        self.contributor_filter.clear()
        for user in sorted_users:
            display_name = f"{user['given_name']} {user['family_name']}"
            if user["id"] == my_id:
                display_name += " (You)"
            user_image = self.avatar_cache.get_avatar_for_user(user)
            self.contributor_filter.addItem(
                QIcon(user_image), display_name, userData=user["id"]
            )
        self.contributor_filter.setCurrentIndex(-1)
        self.contributor_filter.blockSignals(False)

    def update_pagination(self, projects: list):
        total_items = len(projects)
        total_pages = (
            math.ceil(total_items / self.items_per_page) if total_items > 0 else 1
        )
        self.label_page_number.setText(f"Page {self.current_page}/{total_pages}")
        self.btn_previous.setDisabled(self.current_page == 1)
        self.btn_next.setDisabled(self.current_page == total_pages)

    def change_page(self, increment: int):
        self.current_page += increment
        self.populate_projects()

    def to_previous_page(self):
        self.change_page(-1)

    def to_next_page(self):
        self.change_page(1)

    def select_project(self, index: QModelIndex):
        self.setEnabled(False)
        self.busy.emit()
        self.communication.progress_bar("Loading project...", clear_msg_bar=True)
        try:
            # Only allow selection of the first column (project name)
            if index.column() != 0:
                return
            project_item = self.projects_model.itemFromIndex(index)
            new_project = project_item.data(Qt.ItemDataRole.UserRole)
            self.project = new_project
            self.project_selected.emit(self.project)
        finally:
            self.communication.clear_message_bar()
            self.ready.emit()
            self.setEnabled(True)


class BreadcrumbType(Enum):
    PROJECTS = "projects"
    FOLDER = "folder"
    FILE = "file"
    REVISIONS = "revisions"
    PROJECT = "project"


BreadcrumbItem = namedtuple("BreadcrumbItem", ["type", "name"])


class BreadcrumbsWidget(QWidget):
    projects_selected = pyqtSignal()
    folder_selected = pyqtSignal(str)
    file_selected = pyqtSignal()

    def __init__(self, communication, parent=None):
        super().__init__(parent)
        self.communication = communication
        self._items: List[BreadcrumbItem] = [
            BreadcrumbItem(BreadcrumbType.PROJECTS, "Projects")
        ]
        self.setup_ui()
        self.update()

    def setup_ui(self):
        self.layout = QHBoxLayout(self)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.create_ellipsis()
        self.setLayout(self.layout)

    def back_to_root(self):
        self._items = self._items[:1]
        self.update()

    def create_ellipsis(self):
        # when deleting and creating this widget on-the-fly qgis crashes with a segfault
        # to avoid this, it is created on ui setup, and just shown and hidden instead
        self.ellipsis = QPushButton()
        self.ellipsis.setIcon(ellipsis_icon)
        self.ellipsis.setIconSize(QSize(20, 20))
        self.ellipsis.setStyleSheet(
            "QPushButton::menu-indicator{ image: url(none.jpg); }"
        )
        context_menu = QMenu()
        self.ellipsis.setMenu(context_menu)
        self.ellipsis.hide()

    def clear(self):
        for i in reversed(range(self.layout.count())):
            widget = self.layout.itemAt(i).widget()
            if widget:
                self.layout.removeWidget(widget)
                if widget == self.ellipsis:
                    self.ellipsis.hide()
                else:
                    widget.deleteLater()

    def get_button(self, index: int, item: BreadcrumbItem) -> QLabel:
        label_text = elide_text(self.font(), item.name, 100)
        # Last item cannot be clicked
        if index == len(self._items) - 1:
            label = QLabel(f"<b>{label_text}</b>")
            label.setTextFormat(Qt.TextFormat.RichText)
        else:
            link = f"<a href='{index}'>{label_text}</a>"
            label = QLabel(link)
            label.setTextFormat(Qt.TextFormat.RichText)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
            label.linkActivated.connect(lambda _, idx=index: self.on_click(idx))
        label.setToolTip(item.name)
        return label

    def _add_separator(self):
        separator_pixmap = separator_icon.pixmap(QSize(16, 16))
        separator = QLabel()
        separator.setPixmap(separator_pixmap)
        self.layout.addWidget(separator)

    def add_path_widgets(
        self, items, leading_separator=False, trailing_separator=False
    ):
        if leading_separator:
            self._add_separator()
        for i, item in items:
            label = self.get_button(i, item)
            self.layout.addWidget(label)
            if (i != items[-1][0]) or trailing_separator:
                self._add_separator()

    def add_path_dropdown_widget(self, items):
        self.layout.addWidget(self.ellipsis)
        self.ellipsis.show()
        context_menu = self.ellipsis.menu()
        context_menu.clear()
        for index, item in items:
            item_text = elide_text(self.font(), item.name, 100)
            context_menu.addAction(item_text, lambda idx=index: self.on_click(idx))

    def update(self):
        self.clear()
        numbered_items = [[i, item] for i, item in enumerate(self._items)]
        if len(self._items) >= 6:
            # with dropdown
            before_dropdown_items = numbered_items[:2]
            dropdown_items = numbered_items[2:-2]
            after_dropdown_items = numbered_items[-2:]
            self.add_path_widgets(before_dropdown_items, trailing_separator=True)
            self.add_path_dropdown_widget(dropdown_items)
            self.add_path_widgets(after_dropdown_items, leading_separator=True)
        else:
            # without dropdown
            self.add_path_widgets(numbered_items)

    def on_click(self, index: int):
        # Truncate items to clicked position
        self._items = self._items[: index + 1]
        if index == 0:  # Projects
            self.projects_selected.emit()
        else:
            self.communication.progress_bar("Loading files...", clear_msg_bar=True)
            clicked_item = self._items[index]
            if clicked_item.type == BreadcrumbType.FILE:
                self.file_selected.emit()
            else:
                # path should be None for project root
                if len(self._items) == 2:
                    path = None
                else:
                    path = "/".join(item.name for item in self._items[2:]) + "/"
                self.folder_selected.emit(path)
            self.communication.clear_message_bar()
        self.update()


class FilesBreadcrumbsWidget(BreadcrumbsWidget):
    """Breadcrumbs widget specialized for file tab"""

    def remove_file(self):
        # remove last item from the path
        if self._items[-1].type == BreadcrumbType.FILE:
            self._items.pop()
        self.update()

    def rename_file(self, new_name):
        if self._items[-1].type == BreadcrumbType.FILE:
            self._items[-1] = BreadcrumbItem(BreadcrumbType.FILE, new_name)
        self.update()

    def add_file(self, file_path):
        # files can only be added after a folder
        if self._items[-1].type == BreadcrumbType.FOLDER:
            self._items.append(BreadcrumbItem(BreadcrumbType.FILE, file_path))
        self.update()

    def add_folder(self, folder_name):
        # folders can only be added after projects or a folder
        if self._items[-1].type in [BreadcrumbType.PROJECTS, BreadcrumbType.FOLDER]:
            self._items.append(BreadcrumbItem(BreadcrumbType.FOLDER, folder_name))
        self.update()

    def add_revisions(self, selected_file):
        # revisions can only be added after a file
        if self._items[-1].type == BreadcrumbType.FOLDER:
            self.add_file(selected_file["id"])
        if self._items[-1].type == BreadcrumbType.FILE:
            self._items.append(BreadcrumbItem(BreadcrumbType.REVISIONS, "Revisions"))
        self.update()

    def set_folders(self, paths):
        for item in paths:
            self._items.append(BreadcrumbItem(BreadcrumbType.FOLDER, item))
        self.update()


class ProcessBreadcrumbsWidget(BreadcrumbsWidget):
    def add_project(self, project_name):
        # folders can only be added after projects or a folder
        if self._items[-1].type in [BreadcrumbType.PROJECTS]:
            self._items.append(BreadcrumbItem(BreadcrumbType.PROJECT, project_name))
        self.update()


class RanaBrowser(QWidget):
    open_wms_selected = pyqtSignal(dict, dict)
    open_in_qgis_selected = pyqtSignal(dict, dict)
    upload_file_selected = pyqtSignal(dict, dict)
    save_vector_styling_selected = pyqtSignal(dict, dict)
    upload_new_file_selected = pyqtSignal(dict, dict)
    download_file_selected = pyqtSignal(dict, dict)
    download_results_selected = pyqtSignal(dict, dict)
    start_simulation_selected = pyqtSignal(dict, dict)
    start_simulation_selected_with_revision = pyqtSignal(dict, dict, int)
    save_revision_selected = pyqtSignal(dict, dict)
    create_model_selected = pyqtSignal(dict)
    create_model_selected_with_revision = pyqtSignal(dict, int)
    delete_model_selected = pyqtSignal(dict, int)
    open_schematisation_selected_with_revision = pyqtSignal(dict, dict)
    delete_file_selected = pyqtSignal(dict, dict)
    rename_file_selected = pyqtSignal(dict, dict, str)
    create_folder_selected = pyqtSignal(dict, dict, str)
    upload_new_schematisation_selected = pyqtSignal(dict, dict)
    import_schematisation_selected = pyqtSignal(dict, dict)
    request_monitoring_project_jobs = pyqtSignal(str)
    project_jobs_added = pyqtSignal(list)
    project_job_updated = pyqtSignal(dict)

    def __init__(self, communication: UICommunication):
        super().__init__()
        self.last_refresh_time = time.time()
        self.communication = communication
        self.avatar_cache = AvatarCache(communication)
        self.setup_ui()
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.auto_refresh)
        self.refresh_timer.start(10000)

    @property
    def project(self):
        return self.projects_browser.project

    @project.setter
    def project(self, project):
        self.projects_browser.project = project

    @property
    def selected_item(self):
        return self.files_browser.selected_item

    def setup_ui(self):
        # Setup widgets
        self.projects_browser = ProjectsBrowser(
            communication=self.communication,
            avatar_cache=self.avatar_cache,
            parent=self,
        )
        self.avatar_cache.update_users_in_thread(self.projects_browser.users)
        file_signals = FileActionSignals()
        self.files_browser = FilesBrowser(
            communication=self.communication, file_signals=file_signals, parent=self
        )
        self.file_view = FileView(
            communication=self.communication,
            file_signals=file_signals,
            avatar_cache=self.avatar_cache,
            parent=self,
        )
        self.revisions_view = RevisionsView(
            communication=self.communication, parent=self
        )
        self.processes_browser = ProcessesBrowser(
            communication=self.communication,
            avatar_cache=self.avatar_cache,
            parent=self,
        )
        self.files_breadcrumbs = FilesBreadcrumbsWidget(
            communication=self.communication, parent=self
        )
        self.processes_breadcrumbs = ProcessBreadcrumbsWidget(
            communication=self.communication, parent=self
        )
        self.breadcrumbs_stack = QStackedWidget(self)
        self.breadcrumbs_stack.addWidget(self.files_breadcrumbs)
        self.breadcrumbs_stack.addWidget(self.processes_breadcrumbs)
        self.breadcrumbs_stack.setCurrentIndex(0)
        # set fixed height because the size hint of the stacked widget is not correct
        self.breadcrumbs_stack.setFixedHeight(25)

        # Organize widgets in stacks and tabs
        self.rana_browser = QStackedWidget()
        self.rana_browser.addWidget(self.projects_browser)
        # Create tab widget for project related actions
        self.project_widget = QTabWidget()
        self.rana_browser.addWidget(self.project_widget)
        self.rana_browser.setCurrentIndex(0)
        refresh_btn = QToolButton()
        refresh_btn.setToolTip("Refresh")
        refresh_btn.setIcon(refresh_icon)
        self.project_widget.setCornerWidget(refresh_btn)
        self.project_widget.currentChanged.connect(self.on_project_tab_changed)
        # Create stacked widget for file browsing
        self.rana_files = QStackedWidget()
        self.rana_files.addWidget(self.files_browser)
        self.rana_files.addWidget(self.file_view)
        self.rana_files.addWidget(self.revisions_view)
        self.project_widget.addTab(self.rana_files, "Files")
        self.project_widget.setCurrentIndex(0)
        # Create stacked widget for processes
        self.rana_processes = QStackedWidget()
        self.rana_processes.addWidget(self.processes_browser)
        self.project_widget.addTab(self.rana_processes, "Processes")
        self.project_widget.currentChanged.connect(self.on_project_tab_changed)
        # Setup top layout with logo and breadcrumbs
        top_layout = QHBoxLayout()
        banner = QSvgWidget(os.path.join(ICONS_DIR, "banner.svg"))
        renderer = banner.renderer()
        original_size = renderer.defaultSize()  # QSize
        width = 150
        height = int(original_size.height() / original_size.width() * width)
        banner.setFixedWidth(width)
        banner.setFixedHeight(height)
        self.logo_label = banner
        self.logo_label.installEventFilter(self)
        self.window().installEventFilter(self)
        top_layout.addWidget(self.breadcrumbs_stack)
        spacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        top_layout.addItem(spacer)
        top_layout.addWidget(self.logo_label)
        # Add components to the layout
        layout = QVBoxLayout(self)
        layout.addLayout(top_layout)
        layout.addWidget(self.rana_browser)
        self.setLayout(layout)
        self.resize(800, self.height())
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        # Connect avatar_cache
        # Note that avatar_cache is only linked to the projects_browser because for now
        # all widgets that use avatars are loaded after the projects browser is initialized
        self.projects_browser.users_refreshed.connect(
            self.avatar_cache.update_users_in_thread
        )
        self.avatar_cache.avatar_changed.connect(self.projects_browser.update_avatar)

        # Disable/enable widgets
        self.projects_browser.busy.connect(lambda: self.disable)
        self.projects_browser.ready.connect(lambda: self.enable)
        self.revisions_view.busy.connect(lambda: self.disable)
        self.revisions_view.ready.connect(lambda: self.enable)
        self.files_browser.busy.connect(lambda: self.disable)
        self.files_browser.ready.connect(lambda: self.enable)

        self.processes_browser.start_monitoring_project_jobs.connect(
            self.request_monitoring_project_jobs.emit
        )
        self.project_jobs_added.connect(self.processes_browser.add_processes)
        self.project_job_updated.connect(self.processes_browser.update_process_state)
        # Connect refresh buttons
        self.projects_browser.refresh_btn.clicked.connect(self.refresh_projects_browser)
        refresh_btn.clicked.connect(self.refresh_project_widget)
        # On selecting a project in the project view
        # - update selected project in file browser and file_view
        # - set breadcrumbs path
        self.projects_browser.project_selected.connect(
            self.files_browser.update_project
        )
        self.projects_browser.project_selected.connect(
            self.processes_browser.update_project
        )
        self.projects_browser.project_selected.connect(self.file_view.update_project)
        # Show file details on selecting file
        self.files_browser.file_selected.connect(
            self.file_view.show_selected_file_details
        )
        # Connect upload button
        self.files_browser.btn_upload.clicked.connect(
            lambda _,: self.upload_new_file_selected.emit(
                self.project, self.selected_item
            )
        )
        # Connect create new folder button
        self.files_browser.create_folder_requested.connect(
            lambda folder_name: self.create_folder_selected.emit(
                self.project, self.selected_item, folder_name
            )
        )
        # Connect file browser context menu signals
        context_menu_signals = (
            (file_signals.file_deletion_requested, self.delete_file_selected),
            (file_signals.open_in_qgis_requested, self.open_in_qgis_selected),
            (file_signals.upload_file_requested, self.upload_file_selected),
            (
                file_signals.save_vector_styling_requested,
                self.save_vector_styling_selected,
            ),
            (file_signals.open_wms_requested, self.open_wms_selected),
            (file_signals.download_file_requested, self.download_file_selected),
            (
                file_signals.download_results_requested,
                self.download_results_selected,
            ),
            (file_signals.save_revision_requested, self.save_revision_selected),
        )
        for file_signal, rana_signal in context_menu_signals:
            file_signal.connect(
                lambda file, signal=rana_signal: signal.emit(self.project, file)
            )
        file_signals.file_rename_requested.connect(
            lambda file, new_name: self.rename_file_selected.emit(
                self.project, file, new_name
            )
        )
        # Connect new schematisation button
        self.files_browser.btn_new_schematisation.clicked.connect(
            lambda _,: self.upload_new_schematisation_selected.emit(
                self.project, self.selected_item
            )
        )
        # Connect import schematisation button
        self.files_browser.btn_import_schematisation.clicked.connect(
            lambda _,: self.import_schematisation_selected.emit(
                self.project, self.selected_item
            )
        )
        # Connect updating folder from breadcrumb
        self.files_breadcrumbs.folder_selected.connect(
            lambda path: self.files_browser.select_path(path)
        )
        self.files_breadcrumbs.file_selected.connect(self.file_view.refresh)
        # File view buttons
        file_signals.view_all_revisions_requested.connect(
            self.revisions_view.show_revisions_for_file
        )
        file_signals.view_all_revisions_requested.connect(
            lambda _, selected_file: self.file_view.update_selected_file(selected_file)
        )
        self.file_view.btn_start_simulation.clicked.connect(
            lambda _: self.start_simulation_selected.emit(
                self.project, self.selected_item
            )
        )
        self.file_view.btn_create_model.clicked.connect(
            lambda _: self.create_model_selected.emit(self.selected_item)
        )
        self.revisions_view.create_3di_model_clicked.connect(
            lambda revision_id: self.create_model_selected_with_revision.emit(
                self.selected_item, revision_id
            )
        )
        self.revisions_view.delete_3di_model_clicked.connect(
            lambda revision_id: self.delete_model_selected.emit(
                self.selected_item, revision_id
            )
        )
        # Start simulation for specific revision
        self.revisions_view.new_simulation_clicked.connect(
            lambda revision_id: self.start_simulation_selected_with_revision.emit(
                self.project, self.selected_item, revision_id
            )
        )
        # Load specific revision of schematisation
        self.revisions_view.open_schematisation_revision_in_qgis_requested.connect(
            self.open_schematisation_selected_with_revision
        )
        # Update breadcrumbs when file browser path changes
        self.projects_browser.project_selected.connect(
            lambda selected_item: self.files_breadcrumbs.add_folder(
                selected_item["name"]
            )
        )
        self.projects_browser.project_selected.connect(
            lambda selected_item: self.processes_breadcrumbs.add_project(
                selected_item["name"]
            )
        )
        self.files_browser.folder_selected.connect(self.files_breadcrumbs.add_folder)
        self.files_browser.file_selected.connect(
            lambda selected_item: self.files_breadcrumbs.add_file(
                selected_item["id"].split("/")[-1]
            )
        )
        file_signals.view_all_revisions_requested.connect(
            lambda _, selected_file: self.files_breadcrumbs.add_revisions(selected_file)
        )
        # Ensure correct page is shown - do this last so all updates are done
        self.projects_browser.projects_refreshed.connect(self.show_projects_browser)
        self.projects_browser.project_selected.connect(
            lambda _: self.show_project_data(self.project_widget.currentWidget(), 0)
        )
        self.files_browser.file_selected.connect(
            lambda _: self.show_project_data(self.rana_files, 1)
        )
        self.files_browser.folder_selected.connect(
            lambda: self.show_project_data(self.rana_files, 0)
        )
        self.file_view.file_showed.connect(
            lambda: self.show_project_data(self.rana_files, 1)
        )
        file_signals.view_all_revisions_requested.connect(
            lambda _: self.show_project_data(self.rana_files, 2)
        )
        self.files_breadcrumbs.projects_selected.connect(self.show_projects_browser)
        self.files_breadcrumbs.projects_selected.connect(
            self.processes_breadcrumbs.back_to_root
        )
        self.processes_breadcrumbs.projects_selected.connect(self.show_projects_browser)
        self.processes_breadcrumbs.projects_selected.connect(
            self.files_breadcrumbs.back_to_root
        )

        self.files_breadcrumbs.folder_selected.connect(
            lambda: self.show_project_data(self.rana_files, 0)
        )
        self.files_breadcrumbs.file_selected.connect(
            lambda: self.show_project_data(self.rana_files, 1)
        )

    def show_projects_browser(self):
        self.rana_browser.setCurrentIndex(0)
        self.rana_files.setCurrentIndex(0)
        self.rana_processes.setCurrentIndex(0)

    def show_project_data(self, parent, index):
        self.rana_browser.setCurrentIndex(1)
        parent.setCurrentIndex(index)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonPress and obj == self.logo_label:
            link = base_url()
            QDesktopServices.openUrl(QUrl(link))
        elif event.type() == QEvent.WindowActivate:
            # prevent multiple events on window activation to cause multiple refresh actions
            if time.time() - self.last_refresh_time > 0.1:
                self.auto_refresh()
        return False

    @pyqtSlot()
    def enable(self):
        self.rana_browser.setEnabled(True)

    @pyqtSlot()
    def disable(self):
        self.rana_browser.setEnabled(False)

    def on_project_tab_changed(self, index):
        self.breadcrumbs_stack.setCurrentIndex(index)
        if index == 0:
            self.project_widget.cornerWidget().show()
        else:
            self.project_widget.cornerWidget().hide()

    def auto_refresh(self):
        # skip auto refresh for projects view to not mess up pagination
        if not self.rana_browser.isEnabled():
            return
        if (
            self.rana_browser.currentIndex() == 0
            and self.rana_files.currentIndex() in [1, 2, 3]
        ) or self.rana_browser.currentIndex() == 1:
            self.refresh()

    def refresh_projects_browser(self):
        self.projects_browser.refresh()
        self.last_refresh_time = time.time()

    def refresh_project_widget(self):
        current_widget = self.project_widget.currentIndex()
        if isinstance(current_widget, QStackedWidget):
            current_widget = current_widget.currentWidget()
        if current_widget and hasattr(current_widget, "refresh"):
            current_widget.refresh()
            self.last_refresh_time = time.time()

    @pyqtSlot()
    def refresh(self):
        current_widget = None
        if self.rana_browser.currentIndex() == 0:
            self.refresh_projects_browser()
        elif self.rana_browser.currentIndex() == 1:
            self.refresh_project_widget()

    def refresh_after_file_delete(self):
        if self.rana_files.currentIndex() == 2:
            self.files_browser.select_path(
                str(Path(self.file_view.selected_file["id"]).parent) + "/"
            )
            self.file_view.selected_file = None
            self.files_breadcrumbs.remove_file()
            self.rana_files.setCurrentIndex(1)
        self.refresh()

    def refresh_after_file_rename(self, new_name):
        if self.rana_files.currentIndex() == 2:
            self.file_view.selected_file["id"] = str(
                Path(self.file_view.selected_file["id"]).with_name(new_name)
            )
            self.files_breadcrumbs.rename_file(new_name)
        self.refresh()

    def start_file_in_qgis(self, project_id: str, online_path: str):
        self.projects_browser.set_project_from_id(project_id)
        if self.project is not None:
            self.communication.log_warn(f"Selecting project {project_id}")
            self.files_browser.selected_item = get_tenant_project_file(
                project_id, {"path": online_path}
            )
        if self.files_browser.selected_item:
            self.files_browser.project = self.projects_browser.project
            self.file_view.project = self.projects_browser.project
            paths = [self.projects_browser.project["name"]] + online_path.split("/")[
                :-1
            ]
            self.files_breadcrumbs.set_folders(paths)
            # handle item as it was selected in the UI
            self.files_browser.update()
            # open in qgis; note that selected_item is either None or a file
            self.open_in_qgis_selected.emit(
                self.projects_browser.project, self.selected_item
            )
            self.communication.log_info(f"Opening file {str(self.selected_item)}")
        else:
            self.project = None
