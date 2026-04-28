import os
from pathlib import Path

from qgis.PyQt.QtCore import (
    QModelIndex,
    Qt,
    pyqtSignal,
)
from qgis.PyQt.QtGui import (
    QAction,
    QStandardItem,
    QStandardItemModel,
)
from qgis.PyQt.QtWidgets import (
    QAbstractItemDelegate,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from rana_qgis_plugin.auth_3di import has_3di_authcfg
from rana_qgis_plugin.constant import SUPPORTED_DATA_TYPES
from rana_qgis_plugin.icons import dir_icon
from rana_qgis_plugin.utils.api import get_tenant_project_files
from rana_qgis_plugin.utils.generic import (
    NumericItem,
    display_bytes,
    get_file_icon_name,
)
from rana_qgis_plugin.utils.time import get_timestamp_as_numeric_item
from rana_qgis_plugin.widgets.utils_file_action import (
    FileAction,
    FileActionSignals,
    get_file_actions_for_data_type,
)
from rana_qgis_plugin.widgets.utils_icons import get_icon_from_theme
from rana_qgis_plugin.widgets.utils_view import ContentAwareTreeView

# allow for using specific data just for sorting
SORT_ROLE = Qt.ItemDataRole.UserRole + 1


class FileBrowserModel(QStandardItemModel):
    def sort(self, column, order=Qt.SortOrder.AscendingOrder):
        # Do not sort checkbox column
        if column == 0:
            return
        self.layoutAboutToBeChanged.emit()

        directories = []
        files = []

        # First separate directories and files
        # Col 1 holds the name item with UserRole data
        while self.rowCount() > 0:
            row_items = self.takeRow(0)
            if not row_items:
                continue
            item_type = row_items[1].data(Qt.ItemDataRole.UserRole).get("type")
            if item_type == "directory":
                sort_text = row_items[1].data(Qt.ItemDataRole.DisplayRole) or ""
                directories.append((row_items, sort_text))
            else:
                # try to use SORT_ROLE data before using UserRole data, then fall back to display text
                sort_text = (
                    row_items[column].data(SORT_ROLE)
                    or row_items[column].data(Qt.ItemDataRole.UserRole)
                    or row_items[column].data(Qt.ItemDataRole.DisplayRole)
                    or ""
                )
                files.append((row_items, sort_text))

        # Sort directories always by name (col 1), files by the requested column
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
    batch_download_requested = pyqtSignal(list)  # list of file dicts
    batch_delete_requested = pyqtSignal(list)
    busy = pyqtSignal()
    ready = pyqtSignal()

    def __init__(self, communication, file_signals: FileActionSignals, parent=None):
        super().__init__(parent)
        self.project = None
        self.communication = communication
        self.selected_item = None
        self.file_signals = file_signals
        self._pending_close_editor_handler = None
        self.setup_ui()

    def update_project(self, project: dict):
        self.project = project
        self.selected_item = {"id": "", "type": "directory"}
        self.fetch_and_populate(project)

    def setup_ui(self):
        self.files_tv = ContentAwareTreeView()
        self.files_tv.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.files_tv.customContextMenuRequested.connect(self.menu_requested)
        self.files_model = FileBrowserModel()
        self.files_tv.setModel(self.files_model)
        self.files_tv.setSortingEnabled(True)
        self.files_tv.header().setSortIndicatorShown(True)
        self.files_tv.header().setSectionsMovable(False)
        # Set default sort: column 4 (Last modified), descending (newest first)
        # Column 0 is the hidden checkbox column; visible columns start at 1.
        self.files_tv.sortByColumn(4, Qt.SortOrder.DescendingOrder)
        self.files_tv.setColumnHidden(0, True)
        self.files_tv.doubleClicked.connect(self.select_file_or_directory)
        # Select button for batch operations
        self.select_btn = QPushButton("Select")
        self.select_btn.setCheckable(True)
        self.select_btn.toggled.connect(self.toggle_select_mode)
        self.btn_upload = QPushButton("Upload Files to Rana")
        btn_create_folder = QPushButton("Create New Folder")
        btn_create_folder.clicked.connect(self.show_create_folder_dialog)
        self.btn_new_schematisation = QPushButton("New schematisation")
        self.btn_import_schematisation = QPushButton("Import schematisation")
        # Page 0: Normal mode buttons
        normal_page = QWidget()
        btn_layout = QGridLayout(normal_page)
        btn_layout.addWidget(self.btn_upload, 0, 0)
        btn_layout.addWidget(btn_create_folder, 0, 1)
        btn_layout.addWidget(self.btn_new_schematisation, 1, 0)
        btn_layout.addWidget(self.btn_import_schematisation, 1, 1)
        # Page 1: Select mode buttons
        select_page = QWidget()
        select_layout = QHBoxLayout(select_page)
        self.btn_download_selected = QPushButton("Download selected")
        self.btn_delete_selected = QPushButton("Delete selected")
        self.btn_download_selected.setEnabled(False)
        self.btn_delete_selected.setEnabled(False)
        self.btn_download_selected.clicked.connect(
            lambda: self.batch_download_requested.emit(self._get_checked_files())
        )
        self.btn_delete_selected.clicked.connect(self._on_delete_selected_clicked)
        select_layout.addWidget(self.btn_download_selected)
        select_layout.addWidget(self.btn_delete_selected)
        # Stacked widget holding both pages
        self.btn_stack = QStackedWidget()
        self.btn_stack.addWidget(normal_page)
        self.btn_stack.addWidget(select_page)
        layout = QVBoxLayout(self)
        layout.addWidget(self.files_tv)
        layout.addWidget(self.btn_stack)
        self.setLayout(layout)

        self.btn_new_schematisation.setVisible(has_3di_authcfg())
        self.btn_import_schematisation.setVisible(has_3di_authcfg())
        # Connect checkbox state changes to update batch button states
        self.files_model.itemChanged.connect(self._update_batch_buttons)

    def show_create_folder_dialog(self):
        # Make sure this button cannot do anything if the files browser is not in a folder
        dialog = CreateFolderDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.create_folder_requested.emit(dialog.folder_name())

    def refresh(self):
        self.fetch_and_populate(self.project, self.selected_item["id"])
        self.communication.clear_message_bar()

    def toggle_select_mode(self, checked: bool):
        """Toggle Select mode: show/hide checkbox column, swap button sets."""
        self.files_tv.setColumnHidden(0, not checked)
        self.btn_stack.setCurrentIndex(1 if checked else 0)
        if not checked:
            self._clear_all_checkboxes()

    def _clear_all_checkboxes(self):
        """Uncheck all file rows."""
        for row in range(self.files_model.rowCount()):
            checkbox_item = self.files_model.item(row, 0)
            if checkbox_item and checkbox_item.isCheckable():
                checkbox_item.setCheckState(Qt.CheckState.Unchecked)

    def _get_checked_files(self) -> list:
        """Return list of file dicts for all checked rows."""
        checked_files = []
        for row in range(self.files_model.rowCount()):
            checkbox_item = self.files_model.item(row, 0)
            if checkbox_item and checkbox_item.checkState() == Qt.CheckState.Checked:
                # Col 1 is the name item with UserRole data
                name_item = self.files_model.item(row, 1)
                if name_item:
                    file_data = name_item.data(Qt.ItemDataRole.UserRole)
                    if file_data:
                        checked_files.append(file_data)
        return checked_files

    def _update_batch_buttons(self, item: QStandardItem):
        """Enable/disable batch buttons based on checked count. Called on itemChanged."""
        if item.column() != 0:
            # Only react to checkbox column changes
            return
        has_checked = len(self._get_checked_files()) > 0
        self.btn_download_selected.setEnabled(has_checked)
        self.btn_delete_selected.setEnabled(has_checked)

    def _on_delete_selected_clicked(self):
        """Show confirmation dialog before deleting selected files."""
        checked_files = self._get_checked_files()
        if not checked_files:
            return
        file_count = len(checked_files)
        msg = f"Delete {file_count} file{'s' if file_count > 1 else ''}?"
        if self.communication.ask(self, "Confirm Delete", msg):
            self.batch_delete_requested.emit(checked_files)

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
        """Start in-place editing of the filename for the given item.

        Opens the inline editor on the filename column.  When the editor
        closes with a commit, emits the rename signal with the new name.
        If the name is unchanged the signal is not emitted.
        """
        name_index = index.sibling(index.row(), 1)
        name_item = self.files_model.itemFromIndex(name_index)
        if name_item is None:
            return

        original_name = name_item.text()
        delegate = self.files_tv.itemDelegate()

        # Disconnect any stale handler from a previous rename
        if self._pending_close_editor_handler is not None:
            delegate.closeEditor.disconnect(self._pending_close_editor_handler)
            self._pending_close_editor_handler = None

        def on_close_editor(editor, hint):
            delegate.closeEditor.disconnect(on_close_editor)
            self._pending_close_editor_handler = None
            if hint == QAbstractItemDelegate.EndEditHint.NoHint:
                # editing was cancelled (Escape)
                return
            new_name = editor.text().strip()
            if new_name and new_name != original_name:
                self.file_signals.get_signal(FileAction.RENAME).emit(
                    selected_item, new_name
                )

        self._pending_close_editor_handler = on_close_editor
        delegate.closeEditor.connect(on_close_editor)
        self.files_tv.setCurrentIndex(name_index)
        self.files_tv.edit(name_index)

    def select_file_or_directory(self, index: QModelIndex):
        """Handle double-click on tree view. Dispatch to select or navigate."""
        # Only allow selection of the first visible column (filename = col 1)
        if index.column() != 1:
            return
        # In select mode, toggle checkbox instead of navigating
        if self.select_btn.isChecked():
            self._toggle_file_checkbox(index)
        else:
            self._navigate_to_file_or_directory(index)

    def _toggle_file_checkbox(self, index: QModelIndex):
        """Toggle checkbox for a file in select mode. Directories are not toggleable."""
        file_item = self.files_model.itemFromIndex(index)
        selected_item = file_item.data(Qt.ItemDataRole.UserRole)
        # Only toggle checkbox for files, not directories
        if selected_item.get("type") == "file":
            checkbox_item = self.files_model.item(index.row(), 0)
            if checkbox_item and checkbox_item.isCheckable():
                new_state = (
                    Qt.CheckState.Unchecked
                    if checkbox_item.checkState() == Qt.CheckState.Checked
                    else Qt.CheckState.Checked
                )
                checkbox_item.setCheckState(new_state)

    def _navigate_to_file_or_directory(self, index: QModelIndex):
        """Navigate to directory or view file details in normal mode."""
        self.busy.emit()
        self.communication.progress_bar("Loading files...", clear_msg_bar=True)
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
        header = ["", "Filename", "Data type", "Size", "Last modified"]
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
            # Col 0: empty non-checkable placeholder (directories cannot be batch-selected)
            placeholder = QStandardItem()
            placeholder.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.files_model.appendRow([placeholder, name_item])

        # Add files second
        for file in files:
            file_name = os.path.basename(file["id"].rstrip("/"))
            file_icon = get_icon_from_theme(get_file_icon_name(file["data_type"]))
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
            last_modified_item.setData(
                last_modified_item.data(Qt.ItemDataRole.UserRole), role=SORT_ROLE
            )
            # Col 0: checkable item for Select mode (hidden by default)
            checkbox_item = QStandardItem()
            checkbox_item.setCheckState(Qt.CheckState.Unchecked)
            checkbox_item.setFlags(
                Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled
            )
            # Add items to the model
            self.files_model.appendRow(
                [
                    checkbox_item,
                    name_item,
                    data_type_item,
                    size_item,
                    last_modified_item,
                ]
            )

        self.files_tv.sortByColumn(sort_column, sort_order)
        self.files_tv.setSortingEnabled(True)
        # model.clear() resets hidden columns; restore after each populate
        self.files_tv.setColumnHidden(0, True)

        self.files_tv.resize_columns_aware_of_collapsed_items()


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
