import math
import os
from collections import namedtuple
from enum import Enum
from pathlib import Path
from typing import List

from qgis.PyQt.QtCore import (
    QEvent,
    QModelIndex,
    QObject,
    QSettings,
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
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
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

from rana_qgis_plugin.auth_3di import get_3di_auth
from rana_qgis_plugin.communication import UICommunication
from rana_qgis_plugin.constant import SUPPORTED_DATA_TYPES
from rana_qgis_plugin.icons import ICONS_DIR, dir_icon, file_icon, refresh_icon
from rana_qgis_plugin.simulation.threedi_calls import (
    ThreediCalls,
    get_api_client_with_personal_api_token,
)
from rana_qgis_plugin.utils import (
    NumericItem,
    convert_to_local_time,
    convert_to_timestamp,
    display_bytes,
    elide_text,
    format_activity_time,
    get_timestamp_as_numeric_item,
)
from rana_qgis_plugin.utils_api import (
    get_frontend_settings,
    get_tenant_file_descriptor,
    get_tenant_project_file,
    get_tenant_project_file_history,
    get_tenant_project_files,
    get_tenant_projects,
    get_threedi_schematisation,
    get_user_info,
)
from rana_qgis_plugin.utils_settings import base_url
from rana_qgis_plugin.widgets.utils_file_action import (
    FileAction,
    FileActionSignals,
    get_file_actions_for_data_type,
)
from rana_qgis_plugin.widgets.utils_icons import (
    AvatarCache,
    ContributorAvatarsDelegate,
    get_icon_from_theme,
)


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
            nof_models = 0
            # retrieve schematisation and revisions
            schematisation = get_threedi_schematisation(
                self.communication, selected_file["descriptor_id"]
            )
            _, personal_api_token = get_3di_auth()
            frontend_settings = get_frontend_settings()
            api_url = frontend_settings["hcc_url"].rstrip("/")
            threedi_api = get_api_client_with_personal_api_token(
                personal_api_token, api_url
            )
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
                    nof_models += 1
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
        self.revisions_model.setColumnCount(2)
        self.revisions_model.setHorizontalHeaderLabels(["Timestamp", "Event"])
        latest = False
        threedi_revision = sim_btn_data = model_btn_data = threedi_schematisation = None
        for i, (commit_date, event, *schematisation_related) in enumerate(rows):
            if schematisation_related:
                (
                    sim_btn_data,
                    model_btn_data,
                    threedi_revision,
                    threedi_schematisation,
                    latest,
                ) = schematisation_related
                self.revisions_model.setColumnCount(4)
                self.revisions_model.setHorizontalHeaderLabels(
                    ["Timestamp", "Event", "Simulation", "Rana Model"]
                )
            commit_item = get_timestamp_as_numeric_item(commit_date)
            if latest:
                commit_item.setText(commit_item.text() + " (latest)")
            # We store the revision object for loading specific revisions in menu_requested.
            if threedi_revision:
                commit_item.setData((threedi_revision, threedi_schematisation))
            self.revisions_model.appendRow(
                [
                    commit_item,
                    QStandardItem(event),
                ]
            )
            for col_idx, btn_data in enumerate([sim_btn_data, model_btn_data], 2):
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

        resize_columns = [0] if not threedi_revision else [0, 2, 3]
        for col_idx in resize_columns:
            self.revisions_table.horizontalHeader().setSectionResizeMode(
                col_idx, QHeaderView.ResizeToContents
            )
        self.revisions_table.resizeColumnsToContents()
        self.ready.emit()


class FileView(QWidget):
    file_showed = pyqtSignal()
    show_revisions_clicked = pyqtSignal(dict, dict)

    def __init__(self, communication, file_signals: FileActionSignals, parent=None):
        super().__init__(parent)
        self.communication = communication
        self.selected_file = None
        self.project = None
        self.file_signals = file_signals
        self.setup_ui()

    def update_project(self, project: dict):
        self.project = project

    def setup_ui(self):
        self.file_table_widget = QTableWidget(1, 2)
        self.file_table_widget.horizontalHeader().setVisible(False)
        self.file_table_widget.verticalHeader().setVisible(False)
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
        layout = QVBoxLayout(self)
        layout.addWidget(self.file_table_widget)
        layout.addLayout(file_action_btn_layout)
        layout.addLayout(button_layout)
        self.setLayout(layout)

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
        # Enable editing for the filename in row 0, column 1
        item = self.file_table_widget.item(0, 1)
        item.setFlags(
            Qt.ItemFlag.ItemIsEditable
            | Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
        )

        def handle_data_changed(row, column):
            if row == 0 and column == 1:  # Ensure changes are in the correct cell
                new_name = self.file_table_widget.item(row, column).text()
                self.file_signals.get_signal(FileAction.RENAME).emit(
                    selected_item, new_name
                )
                # disconnect handler if still connected
                try:
                    self.file_table_widget.itemChanged.disconnect(handle_data_changed)
                except:
                    pass

        # Connect to the itemChanged signal
        self.file_table_widget.itemChanged.connect(
            lambda item: handle_data_changed(item.row(), item.column())
        )

        # Enter editing mode
        self.file_table_widget.editItem(item)

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

    def show_selected_file_details(self, selected_file):
        tooltips = {}
        self.update_selected_file(selected_file)
        filename = os.path.basename(selected_file["id"].rstrip("/"))
        username = (
            selected_file["user"]["given_name"]
            + " "
            + selected_file["user"]["family_name"]
        )
        data_type = selected_file["data_type"]
        meta = None
        descriptor = get_tenant_file_descriptor(selected_file["descriptor_id"])
        meta = descriptor["meta"] if descriptor else None
        description = descriptor["description"] if descriptor else None

        last_modified = convert_to_local_time(selected_file["last_modified"])
        display_last_modified = format_activity_time(selected_file["last_modified"])
        if last_modified != display_last_modified:
            tooltips["Last modified"] = last_modified
        size = (
            display_bytes(selected_file["size"])
            if data_type != "threedi_schematisation"
            else "N/A"
        )
        file_details = [
            ("Name", filename),
            ("Size", size),
            ("File type", selected_file["media_type"]),
            ("Data type", SUPPORTED_DATA_TYPES.get(data_type, data_type)),
            ("Added by", username),
            ("Last modified", display_last_modified),
            ("Description", description),
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
            scenario_details = [
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
            file_details.extend(scenario_details)
        if data_type == "threedi_schematisation":
            schematisation = get_threedi_schematisation(
                self.communication, selected_file["descriptor_id"]
            )
            if schematisation:
                revision = schematisation["latest_revision"]
                schematisation_details = [
                    ("Schematisation ID", schematisation["schematisation"]["id"]),
                    ("Latest revision ID", revision["id"] if revision else None),
                    (
                        "Latest revision number",
                        revision["number"] if revision else None,
                    ),
                ]
                if revision and revision.get("has_threedimodel"):
                    self.btn_stack.setCurrentIndex(0)
                else:
                    self.btn_stack.setCurrentIndex(1)
                self.btn_stack.show()
                file_details.extend(schematisation_details)
            else:
                self.btn_stack.hide()
                self.communication.show_error("Failed to download 3Di schematisation.")
        else:
            self.btn_stack.hide()
            self.btn_stack.hide()
        self.update_file_action_buttons(selected_file)
        self.file_table_widget.clearContents()
        self.file_table_widget.setRowCount(len(file_details))
        self.file_table_widget.horizontalHeader().setStretchLastSection(True)
        for i, (label, value) in enumerate(file_details):
            label_item = QTableWidgetItem(label)
            label_item.setFlags(
                Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
            )
            value_item = QTableWidgetItem(str(value))
            value_item.setFlags(
                Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
            )
            if label in tooltips:
                value_item.setToolTip(tooltips[label])
            self.file_table_widget.setItem(i, 0, label_item)
            self.file_table_widget.setItem(i, 1, value_item)
        self.file_table_widget.resizeColumnsToContents()

    def refresh(self):
        assert self.selected_file
        self.selected_file = get_tenant_project_file(
            self.project["id"], {"path": self.selected_file["id"]}
        )
        last_modified_key = (
            f"{self.project['name']}/{self.selected_file['id']}/last_modified"
        )
        # ensure any signals (from rename) are disconnected before updating data
        try:
            self.file_table_widget.itemChanged.disconnect()
        except TypeError:
            pass
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
        self.files_model = QStandardItemModel()
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
        self.files = get_tenant_project_files(
            self.communication,
            project["id"],
            {"path": path} if path else None,
        )
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
            self.files_model.appendRow([name_item])

        # Add files second
        for file in files:
            file_name = os.path.basename(file["id"].rstrip("/"))
            name_item = QStandardItem(file_icon, file_name)
            name_item.setToolTip(file_name)
            name_item.setData(file, role=Qt.ItemDataRole.UserRole)
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

    def __init__(self, communication, avatar_cache, parent=None):
        super().__init__(parent)
        self.communication = communication
        self.projects = []
        self.users = []
        self.filtered_projects = []
        self.current_page = 1
        self.items_per_page = 25
        self.project = None
        self.avatar_cache = avatar_cache
        # collect data
        self.fetch_projects()
        self.update_users()
        # start thread to retrieve actual avatars
        self.avatar_cache.avatar_changed.connect(self.update_avatar)
        self.avatar_cache.update_users_in_thread(self.users)
        self.setup_ui()
        self.populate_contributors()
        self.populate_projects()
        self.projects_tv.header().setSortIndicator(2, Qt.SortOrder.DescendingOrder)

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
        self.contributor_filter.currentIndexChanged.connect(self.filter_projects)
        # Create tree view with project files and model
        self.projects_model = QStandardItemModel()
        self.projects_tv = QTreeView()
        self.projects_tv.setModel(self.projects_model)
        self.projects_tv.setSortingEnabled(True)
        self.projects_tv.header().setSortIndicatorShown(True)
        self.projects_model.setHorizontalHeaderLabels(
            ["Project Name", "Contributors", "Last activity"]
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
        # Organize widgets in layouts
        top_layout = QHBoxLayout()
        top_layout.addWidget(self.projects_search)
        top_layout.addWidget(self.contributor_filter)
        pagination_layout = QHBoxLayout()
        pagination_layout.addWidget(self.btn_previous)
        pagination_layout.addWidget(self.label_page_number)
        pagination_layout.addWidget(self.btn_next)
        layout = QVBoxLayout(self)
        layout.addLayout(top_layout)
        layout.addWidget(self.projects_tv)
        layout.addLayout(pagination_layout)
        self.setLayout(layout)

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

    def refresh(self):
        self.current_page = 1
        self.fetch_projects()
        self.update_users()
        self.avatar_cache.update_users_in_thread(self.users)
        if self.filter_active:
            self.filter_projects()
        else:
            self.populate_projects()
        self.populate_contributors()
        self.projects_tv.header().setSortIndicator(2, Qt.SortOrder.DescendingOrder)
        self.projects_refreshed.emit()

    @property
    def filter_active(self):
        return self.projects_search.text() or self.contributor_filter.currentIndex() > 0

    def filter_projects(self):
        self.current_page = 1
        if not self.filter_active:
            self.filtered_projects = []
        else:
            project_filters = [
                self.get_projects_filtered_by_name,
                self.get_projects_filtered_by_contributor,
            ]
            project_ids = [
                {project["id"] for project in filter_func()}
                for filter_func in project_filters
            ]
            # Find project ids that are present in all filters
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

    def sort_projects(self, column_index: int, order: Qt.SortOrder):
        self.current_page = 1
        key_funcs = [
            lambda project: project["name"].lower(),
            lambda project: -convert_to_timestamp(project["last_activity"]),
        ]
        key_func = key_funcs[column_index]
        self.projects.sort(
            key=key_func, reverse=(order == Qt.SortOrder.DescendingOrder)
        )
        if self.active_filter:
            self.filter_projects()
            return
        self.populate_projects()

    def process_project_item(
        self, project: dict
    ) -> list[QStandardItem, QStandardItem, NumericItem]:
        project_name = project["name"]
        # Process project name into item
        name_item = QStandardItem(project_name)
        name_item.setToolTip(project_name)
        name_item.setData(project, role=Qt.ItemDataRole.UserRole)
        # Process last activity time into item
        last_activity_item = get_timestamp_as_numeric_item(project["last_activity"])
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
        return [name_item, contributors_item, last_activity_item]

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
        self.contributor_filter.addItem(
            QIcon(get_icon_from_theme("mActionFilter2.svg")), "All contributors"
        )
        for user in sorted_users:
            display_name = f"{user['given_name']} {user['family_name']}"
            if user["id"] == my_id:
                display_name += " (You)"
            user_image = self.avatar_cache.get_avatar_for_user(user)
            self.contributor_filter.addItem(
                QIcon(user_image), display_name, userData=user["id"]
            )
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


BreadcrumbItem = namedtuple("BreadcrumbItem", ["type", "name"])


class BreadCrumbsWidget(QWidget):
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

    def setup_ui(self):
        self.layout = QHBoxLayout(self)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.layout)

    def clear(self):
        for i in reversed(range(self.layout.count())):
            widget = self.layout.itemAt(i).widget()
            if widget:
                self.layout.removeWidget(widget)
                widget.deleteLater()

    def update(self):
        self.clear()
        for i, item in enumerate(self._items):
            label = self.get_button(i, item)
            self.layout.addWidget(label)
            if i != len(self._items) - 1:
                separator = QLabel(">")
                self.layout.addWidget(separator)

    def get_button(self, index: int, item: BreadcrumbItem) -> QLabel:
        label_text = elide_text(self.font(), item.name, 100)
        # Last item cannot be clicked
        if index == len(self._items) - 1:
            label = QLabel(label_text)
        else:
            link = f"<a href='{index}'>{label_text}</a>"
            label = QLabel(link)
            label.setTextFormat(Qt.TextFormat.RichText)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
            label.linkActivated.connect(lambda _, idx=index: self.on_click(idx))
        return label

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

    def __init__(self, communication: UICommunication):
        super().__init__()
        self.communication = communication
        self.avatar_cache = AvatarCache(communication)
        self.setup_ui()
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.auto_refresh)
        self.refresh_timer.start(60000)

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
        self.rana_browser = QTabWidget()
        self.rana_processes = QWidget()
        self.rana_files = QStackedWidget()
        self.rana_browser.addTab(self.rana_files, "Files")
        self.rana_browser.setCurrentIndex(0)
        self.rana_browser.tabBar().setTabVisible(0, False)
        # Set up breadcrumbs, browser and file view widgets
        self.breadcrumbs = BreadCrumbsWidget(
            communication=self.communication, parent=self
        )
        refresh_btn = QToolButton()
        refresh_btn.setToolTip("Refresh")
        refresh_btn.setIcon(refresh_icon)
        refresh_btn.clicked.connect(self.refresh)

        # Setup top layout with logo and breadcrumbs
        top_layout = QGridLayout()

        banner = QSvgWidget(os.path.join(ICONS_DIR, "banner.svg"))
        renderer = banner.renderer()
        original_size = renderer.defaultSize()  # QSize
        width = 150
        height = int(original_size.height() / original_size.width() * width)
        banner.setFixedWidth(width)
        banner.setFixedHeight(height)
        logo_label = banner
        logo_label.installEventFilter(self)

        top_layout.addWidget(self.breadcrumbs, 0, 0, 1, 3)
        spacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        top_layout.addItem(spacer, 0, 3, 1, 1)
        top_layout.addWidget(logo_label, 0, 4)
        spacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        top_layout.addItem(spacer, 1, 0, 1, 1)
        top_layout.addWidget(refresh_btn, 1, 4, Qt.AlignRight)

        # Add components to the layout
        layout = QVBoxLayout(self)
        layout.addLayout(top_layout)
        layout.addWidget(self.rana_browser)
        self.setLayout(layout)
        self.resize(800, self.height())
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        # Setup widgets that populate the rana widget
        file_signals = FileActionSignals()
        self.projects_browser = ProjectsBrowser(
            communication=self.communication,
            avatar_cache=self.avatar_cache,
            parent=self,
        )
        self.files_browser = FilesBrowser(
            communication=self.communication, file_signals=file_signals, parent=self
        )
        self.file_view = FileView(
            communication=self.communication, file_signals=file_signals, parent=self
        )
        self.revisions_view = RevisionsView(
            communication=self.communication, parent=self
        )
        # Disable/enable widgets
        self.projects_browser.busy.connect(lambda: self.disable)
        self.projects_browser.ready.connect(lambda: self.enable)
        self.revisions_view.busy.connect(lambda: self.disable)
        self.revisions_view.ready.connect(lambda: self.enable)
        self.files_browser.busy.connect(lambda: self.disable)
        self.files_browser.ready.connect(lambda: self.enable)
        # Add browsers and file view to rana widget
        self.rana_files.addWidget(self.projects_browser)
        self.rana_files.addWidget(self.files_browser)
        self.rana_files.addWidget(self.file_view)
        self.rana_files.addWidget(self.revisions_view)
        # On selecting a project in the project view
        # - update selected project in file browser and file_view
        # - set breadcrumbs path
        self.projects_browser.project_selected.connect(
            self.files_browser.update_project
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
        self.breadcrumbs.folder_selected.connect(
            lambda path: self.files_browser.select_path(path)
        )
        self.breadcrumbs.file_selected.connect(self.file_view.refresh)
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
            lambda selected_item: self.breadcrumbs.add_folder(selected_item["name"])
        )
        self.files_browser.folder_selected.connect(self.breadcrumbs.add_folder)
        self.files_browser.file_selected.connect(
            lambda selected_item: self.breadcrumbs.add_file(
                selected_item["id"].split("/")[-1]
            )
        )
        file_signals.view_all_revisions_requested.connect(
            lambda _, selected_file: self.breadcrumbs.add_revisions(selected_file)
        )
        # Ensure correct page is shown - do this last zo all updates are done
        self.projects_browser.projects_refreshed.connect(
            lambda: self.rana_files.setCurrentIndex(0)
        )
        self.projects_browser.project_selected.connect(
            lambda _: self.rana_files.setCurrentIndex(1)
        )
        self.files_browser.folder_selected.connect(
            lambda: self.rana_files.setCurrentIndex(1)
        )
        self.files_browser.file_selected.connect(
            lambda _: self.rana_files.setCurrentIndex(2)
        )
        self.file_view.file_showed.connect(lambda: self.rana_files.setCurrentIndex(2))
        file_signals.view_all_revisions_requested.connect(
            lambda _: self.rana_files.setCurrentIndex(3)
        )
        self.breadcrumbs.projects_selected.connect(
            lambda: self.rana_files.setCurrentIndex(0)
        )
        self.breadcrumbs.folder_selected.connect(
            lambda: self.rana_files.setCurrentIndex(1)
        )
        self.breadcrumbs.file_selected.connect(
            lambda: self.rana_files.setCurrentIndex(2)
        )

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonPress:
            link = base_url()
            QDesktopServices.openUrl(QUrl(link))
        return False

    @pyqtSlot()
    def enable(self):
        self.rana_browser.setEnabled(True)

    @pyqtSlot()
    def disable(self):
        self.rana_browser.setEnabled(False)

    def auto_refresh(self):
        # skip auto refresh for projects view to not mess up pagination
        if (
            self.rana_files.currentIndex() in [1, 2, 3]
            and self.rana_browser.isEnabled()
        ):
            self.refresh()

    @pyqtSlot()
    def refresh(self):
        if hasattr(self.rana_files.currentWidget(), "refresh"):
            self.rana_files.currentWidget().refresh()
        else:
            raise Exception("Attempted refresh on widget without refresh support")

    def refresh_after_file_delete(self):
        if self.rana_files.currentIndex() == 2:
            self.files_browser.select_path(
                str(Path(self.file_view.selected_file["id"]).parent) + "/"
            )
            self.file_view.selected_file = None
            self.breadcrumbs.remove_file()
            self.rana_files.setCurrentIndex(1)
        self.refresh()

    def refresh_after_file_rename(self, new_name):
        if self.rana_files.currentIndex() == 2:
            self.file_view.selected_file["id"] = str(
                Path(self.file_view.selected_file["id"]).with_name(new_name)
            )
            self.breadcrumbs.rename_file(new_name)
        self.refresh()

    def start_file_in_qgis(self, project_id: str, online_path: str):
        self.projects_browser.set_project_from_id(project_id)
        if self.project is not None:
            self.communication.log_warn(f"Selecting project {project_id}")
            self.files_browser.selected_item = get_tenant_project_file(
                project_id, {"path": online_path}
            )
        if self.files_browser.selected_item:
            paths = [self.projects_browser.project["name"]] + online_path.split("/")[
                :-1
            ]
            self.breadcrumbs.set_folders(paths)
            # handle item as it was selected in the UI
            self.files_browser.update()
            # open in qgis; note that selected_item is either None or a file
            self.open_in_qgis_selected.emit(
                self.projects_browser.project, self.selected_item
            )
            self.communication.log_info(f"Opening file {str(self.selected_item)}")
        else:
            self.project = None
