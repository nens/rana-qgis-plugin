import os
import time
from collections import namedtuple
from enum import Enum
from pathlib import Path
from typing import List

from qgis.PyQt.QtCore import (
    QEvent,
    QModelIndex,
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
    QStandardItem,
    QStandardItemModel,
)
from qgis.PyQt.QtSvg import QSvgWidget
from qgis.PyQt.QtWidgets import (
    QDialog,
    QDialogButtonBox,
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
    display_bytes,
    elide_text,
    get_threedi_api,
)
from rana_qgis_plugin.utils_api import (
    get_tenant_project_file,
    get_tenant_project_file_history,
    get_tenant_project_files,
    get_threedi_schematisation,
)
from rana_qgis_plugin.utils_settings import base_url
from rana_qgis_plugin.utils_time import get_timestamp_as_numeric_item
from rana_qgis_plugin.widgets.file_view import FileView
from rana_qgis_plugin.widgets.processes_browser import ProcessesBrowser
from rana_qgis_plugin.widgets.projects_browser import ProjectsBrowser
from rana_qgis_plugin.widgets.publications_browser import PublicationsBrowser
from rana_qgis_plugin.widgets.utils_avatars import AvatarCache
from rana_qgis_plugin.widgets.utils_file_action import (
    FileAction,
    FileActionSignals,
    get_file_actions_for_data_type,
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
        self.files_tv.header().setSectionsMovable(False)
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


class GenericBreadCrumbsWidget(BreadcrumbsWidget):
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
    save_raster_styling_selected = pyqtSignal(dict, dict)
    upload_new_file_selected = pyqtSignal(dict, dict)
    download_file_selected = pyqtSignal(dict, dict)
    download_results_selected = pyqtSignal(dict, dict)
    start_simulation_selected = pyqtSignal(dict, dict)
    start_simulation_selected_with_revision = pyqtSignal(dict, dict, int)
    save_revision_selected = pyqtSignal(dict, dict)
    create_model_selected = pyqtSignal(dict, dict)
    create_model_selected_with_revision = pyqtSignal(dict, dict, int)
    delete_model_selected = pyqtSignal(dict, int)
    open_schematisation_selected_with_revision = pyqtSignal(dict, dict)
    delete_file_selected = pyqtSignal(dict, dict)
    rename_file_selected = pyqtSignal(dict, dict, str)
    create_folder_selected = pyqtSignal(dict, dict, str)
    upload_new_schematisation_selected = pyqtSignal(dict, dict)
    import_schematisation_selected = pyqtSignal(dict, dict)
    project_jobs_added = pyqtSignal(list)
    project_job_updated = pyqtSignal(dict)
    project_publication_added = pyqtSignal(list)
    project_publication_updated = pyqtSignal(dict)
    update_avatar_cache = pyqtSignal(list)
    view_file_after_open = pyqtSignal(dict)
    project_changed = pyqtSignal(str)

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
        self.publications_browser = PublicationsBrowser(
            communication=self.communication,
            avatar_cache=self.avatar_cache,
            parent=self,
        )
        self.files_breadcrumbs = FilesBreadcrumbsWidget(
            communication=self.communication, parent=self
        )
        self.processes_breadcrumbs = GenericBreadCrumbsWidget(
            communication=self.communication, parent=self
        )
        self.publications_breadcrumbs = GenericBreadCrumbsWidget(
            communication=self.communication, parent=self
        )
        self.breadcrumbs_stack = QStackedWidget(self)
        self.breadcrumbs_stack.addWidget(self.files_breadcrumbs)
        self.breadcrumbs_stack.addWidget(self.processes_breadcrumbs)
        self.breadcrumbs_stack.addWidget(self.publications_breadcrumbs)
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
        # Create stacked widget for publications
        self.rana_publications = QStackedWidget()
        self.rana_publications.addWidget(self.publications_browser)
        self.project_widget.addTab(self.rana_publications, "Publications")
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
        self.projects_browser.users_refreshed.connect(self.update_avatar_cache.emit)
        self.avatar_cache.avatar_changed.connect(self.projects_browser.update_avatar)

        # Disable/enable widgets
        self.projects_browser.busy.connect(lambda: self.disable)
        self.projects_browser.ready.connect(lambda: self.enable)
        self.revisions_view.busy.connect(lambda: self.disable)
        self.revisions_view.ready.connect(lambda: self.enable)
        self.files_browser.busy.connect(lambda: self.disable)
        self.files_browser.ready.connect(lambda: self.enable)

        # Connect widgets that use monitoring
        self.project_jobs_added.connect(self.processes_browser.add_items)
        self.project_job_updated.connect(self.processes_browser.update_job_state)
        self.project_publication_added.connect(self.publications_browser.add_items)
        self.project_publication_updated.connect(self.publications_browser.update_item)
        # TODO add publicaitons widget

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
        self.projects_browser.project_selected.connect(
            self.publications_browser.update_project
        )
        self.projects_browser.project_selected.connect(self.file_view.update_project)
        self.projects_browser.project_selected.connect(
            lambda project: self.project_changed.emit(project["id"])
        )
        # Show file details on selecting file
        self.files_browser.file_selected.connect(
            self.file_view.show_selected_file_details
        )
        # Show file details after opening a file
        self.view_file_after_open.connect(self.files_browser.file_selected.emit)
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
            (
                file_signals.save_raster_styling_requested,
                self.save_raster_styling_selected,
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
            lambda _: self.create_model_selected.emit(self.project, self.selected_item)
        )
        self.revisions_view.create_3di_model_clicked.connect(
            lambda revision_id: self.create_model_selected_with_revision.emit(
                self.project, self.selected_item, revision_id
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
        self.projects_browser.project_selected.connect(
            lambda selected_item: self.publications_breadcrumbs.add_project(
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
        # Ensure all breadcrumbs are reset on selecting project
        for breadcrumb in [
            self.files_breadcrumbs,
            self.processes_breadcrumbs,
            self.publications_breadcrumbs,
        ]:
            breadcrumb.projects_selected.connect(self.show_projects_browser)
            for other_breadcrumb in [
                self.files_breadcrumbs,
                self.processes_breadcrumbs,
                self.publications_breadcrumbs,
            ]:
                if other_breadcrumb != breadcrumb:
                    breadcrumb.projects_selected.connect(other_breadcrumb.back_to_root)
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

    def show_processes_overview(self):
        if self.rana_browser.currentIndex() != 1:
            # going to the processes view can only happen when the project widget is shown
            return
        self.project_widget.setCurrentIndex(1)
        self.rana_processes.setCurrentIndex(0)

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
        for i in range(self.breadcrumbs_stack.count()):
            self.breadcrumbs_stack.widget(i).setEnabled(True)
        self.rana_browser.setEnabled(True)

    @pyqtSlot()
    def disable(self):
        for i in range(self.breadcrumbs_stack.count()):
            self.breadcrumbs_stack.widget(i).setEnabled(False)
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
        current_widget = self.project_widget.currentWidget()
        if isinstance(current_widget, QStackedWidget):
            current_widget = current_widget.currentWidget()
        if current_widget and hasattr(current_widget, "refresh"):
            current_widget.refresh()
            self.last_refresh_time = time.time()

    def reset(self):
        self.disable()
        self.rana_browser.setCurrentIndex(0)
        for widget_idx in range(self.breadcrumbs_stack.count()):
            self.breadcrumbs_stack.widget(widget_idx).back_to_root()
        self.projects_browser.refresh()
        self.enable()

    @pyqtSlot()
    def refresh(self):
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
