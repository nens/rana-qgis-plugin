import os
from pathlib import Path
from typing import Optional

from qgis.core import QgsApplication
from qgis.PyQt.QtCore import (
    QModelIndex,
    Qt,
    QUrl,
    pyqtSignal,
)
from qgis.PyQt.QtGui import QAction, QDesktopServices, QStandardItem, QStandardItemModel
from qgis.PyQt.QtWidgets import (
    QAbstractItemDelegate,
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from rana_qgis_plugin.auth_3di import has_3di_authcfg
from rana_qgis_plugin.constant import SUPPORTED_DATA_TYPES
from rana_qgis_plugin.icons import (
    add_icon,
    dir_icon,
    download_icon,
    trash_icon,
    upload_icon,
)
from rana_qgis_plugin.utils.api import (
    get_tenant_file_descriptor,
    get_tenant_project_files,
    get_threedi_schematisation,
)
from rana_qgis_plugin.utils.generic import (
    NumericItem,
    display_bytes,
    get_file_icon_name,
)
from rana_qgis_plugin.utils.local_paths import (
    get_local_dir_structure,
    get_local_file_path,
    get_local_results_dir_from_meta,
    get_local_schematisation_revision_dir,
)
from rana_qgis_plugin.utils.settings import hcc_working_dir
from rana_qgis_plugin.utils.time import get_timestamp_as_numeric_item
from rana_qgis_plugin.widgets.utils_file_action import (
    FileAction,
    FileActionSignals,
    copy_wms_url_to_clipboard,
    get_file_actions,
)
from rana_qgis_plugin.widgets.utils_icons import get_icon_from_theme
from rana_qgis_plugin.widgets.utils_view import (
    CheckableHeaderView,
    ContentAwareTreeView,
)

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
        self.files_tv.setHeader(
            CheckableHeaderView(Qt.Orientation.Horizontal, self.files_tv)
        )
        self.files_tv.header().check_state_changed.connect(
            self._on_header_check_state_changed
        )
        self.files_tv.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.files_tv.customContextMenuRequested.connect(self.menu_requested)
        # Ensure there is always empty space at the bottom for right-click context menu
        self.files_tv.setViewportMargins(0, 0, 0, 30)
        self.files_model = FileBrowserModel()
        self.files_tv.setModel(self.files_model)
        self.files_tv.setSortingEnabled(True)
        self.files_tv.header().setStretchLastSection(True)
        self.files_tv.header().setSortIndicatorShown(True)
        self.files_tv.header().setSectionsMovable(False)
        # Remove the branch indicator area so column 0 has no leading indent
        self.files_tv.setRootIsDecorated(False)
        # Set default sort: column 4 (Last modified), descending (newest first)
        # Column 0 is the hidden checkbox column; visible columns start at 1.
        self.files_tv.sortByColumn(4, Qt.SortOrder.DescendingOrder)
        self.files_tv.setColumnHidden(0, True)
        # Disable all user-gesture-triggered editing; rename is started programmatically
        self.files_tv.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.files_tv.doubleClicked.connect(self.select_file_or_directory)
        # Select button for batch operations
        self.select_btn = QPushButton("Select")
        self.select_btn.setCheckable(True)
        self.select_btn.setToolTip("Toggle file selection mode")
        self.select_btn.toggled.connect(self.toggle_select_mode)
        self.btn_upload = QPushButton("Upload Files to Rana")
        self.btn_upload.setIcon(upload_icon)
        self.btn_upload.setToolTip("Upload your files to Rana Web Platform")
        # Add schematisation menu button
        self.btn_add_schematisation = QToolButton()
        self.btn_add_schematisation.setText("Upload schematisation")
        self.btn_add_schematisation.setIcon(add_icon)
        self.btn_add_schematisation.setToolTip(
            "Add schematisation on Rana web platform"
        )
        self.btn_add_schematisation.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        self.btn_add_schematisation.setPopupMode(
            QToolButton.ToolButtonPopupMode.InstantPopup
        )
        schematisation_menu = QMenu(self.btn_add_schematisation)
        schematisation_menu.setToolTipsVisible(True)
        self.action_new_schematisation = schematisation_menu.addAction(
            QgsApplication.getThemeIcon("/mActionNewPage.svg"), "From scratch"
        )
        self.action_new_schematisation.setToolTip(
            "Create a new schematisation on Rana web platform"
        )
        self.action_upload_existing_schematisation = schematisation_menu.addAction(
            dir_icon,
            "Upload existing",
        )
        self.action_upload_existing_schematisation.setToolTip(
            "Upload your local schematisation to Rana web platform"
        )
        self.action_import_schematisation = schematisation_menu.addAction(
            download_icon,
            "Import from HCC",
        )
        self.action_import_schematisation.setToolTip(
            "Import a schematisation from the model databank into Rana web platform"
        )
        self.btn_add_schematisation.setMenu(schematisation_menu)
        # Page 0: Normal mode buttons
        normal_page = QWidget()
        btn_layout = QVBoxLayout(normal_page)
        row1 = QHBoxLayout()
        row1.addWidget(self.btn_upload)
        row1.addWidget(self.btn_add_schematisation)
        btn_layout.addLayout(row1)
        # Page 1: Select mode buttons
        select_page = QWidget()
        select_layout = QHBoxLayout(select_page)
        self.btn_download_selected = QPushButton(download_icon, "Download selected")
        self.btn_download_selected.setToolTip("Download selected file(s)")
        self.btn_delete_selected = QPushButton(trash_icon, "Delete selected")
        self.btn_delete_selected.setToolTip("Delete selected file(s)")
        self.btn_download_selected.setEnabled(False)
        self.btn_delete_selected.setEnabled(False)
        self.btn_download_selected.clicked.connect(self._on_download_selected_clicked)
        self.btn_delete_selected.clicked.connect(self._on_delete_selected_clicked)
        select_layout.addWidget(self.btn_download_selected)
        select_layout.addWidget(self.btn_delete_selected)
        # Stacked widget holding both pages
        self.btn_stack = QStackedWidget()
        self.btn_stack.addWidget(normal_page)
        self.btn_stack.addWidget(select_page)
        self.btn_stack.setSizePolicy(
            self.btn_stack.sizePolicy().horizontalPolicy(),
            QSizePolicy.Fixed,
        )
        layout = QVBoxLayout(self)
        layout.addWidget(self.files_tv)
        layout.addWidget(self.btn_stack)
        self.setLayout(layout)

        self.btn_add_schematisation.setVisible(has_3di_authcfg())
        # Connect checkbox state changes to update batch button states
        self.files_model.itemChanged.connect(self._update_batch_buttons)

    def show_create_folder_dialog(self):
        # Make sure this button cannot do anything if the files browser is not in a folder
        dialog = CreateFolderDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.create_folder_requested.emit(dialog.folder_name())

    def refresh(self):
        # Remember current select mode state
        was_in_select_mode = self.select_btn.isChecked()
        previously_checked = self._get_checked_files() if was_in_select_mode else []
        # Refresh file list
        self.fetch_and_populate(self.project, self.selected_item["id"])
        self.communication.clear_message_bar()
        # Restore select mode and re-check previously selected files
        if was_in_select_mode:
            self.select_btn.setChecked(True)
            # setChecked only emits toggled when state changes; since the button
            # was already checked before refresh, call toggle_select_mode explicitly.
            self.toggle_select_mode(True)
            self._restore_checked_files(previously_checked)

    def _checkbox_column_width(self) -> int:
        """Return a column width snug around the checkbox indicator for the current style.
        Uses PM_IndicatorWidth to match the size used by CheckableHeaderView."""
        cb_width = self.files_tv.style().pixelMetric(
            QStyle.PixelMetric.PM_IndicatorWidth
        )
        return cb_width + 8  # 4px padding on each side

    def toggle_select_mode(self, checked: bool):
        """Toggle Select mode: show/hide checkbox column, swap button sets."""
        self.communication.log_info(f"Toggle select mode: {checked}")
        self.files_tv.setColumnHidden(0, not checked)
        if checked:
            self.files_tv.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
            self.files_tv.header().resizeSection(0, self._checkbox_column_width())
        self.btn_stack.setCurrentIndex(1 if checked else 0)
        if not checked:
            self._clear_all_checkboxes()
            self.files_tv.header().set_check_state(Qt.CheckState.Unchecked)

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

    def _restore_checked_files(self, previously_checked: list):
        """Re-check files that were checked before refresh, matched by file ID."""
        if not previously_checked:
            return
        # Build a set of IDs for fast lookup
        previous_ids = {f["id"] for f in previously_checked}
        # Check rows that match previously checked files
        for row in range(self.files_model.rowCount()):
            name_item = self.files_model.item(row, 1)
            if name_item:
                file_data = name_item.data(Qt.ItemDataRole.UserRole)
                if file_data and file_data.get("id") in previous_ids:
                    checkbox_item = self.files_model.item(row, 0)
                    if checkbox_item and checkbox_item.isCheckable():
                        checkbox_item.setCheckState(Qt.CheckState.Checked)

    def _set_batch_buttons_enabled(self, has_checked: bool):
        """Enable or disable the batch action buttons."""
        self.btn_download_selected.setEnabled(has_checked)
        self.btn_delete_selected.setEnabled(has_checked)

    def _update_batch_buttons(self, item: QStandardItem):
        """Enable/disable batch buttons based on checked count. Called on itemChanged."""
        # Only react to checkbox column changes
        if item.column() != 0:
            return
        has_checked = len(self._get_checked_files()) > 0
        self._set_batch_buttons_enabled(has_checked)
        self._sync_header_checkbox()

    def _on_header_check_state_changed(self, state: int):
        """Called when the user clicks the header checkbox. Check or uncheck all file rows."""
        state = Qt.CheckState(state)
        self.files_model.blockSignals(True)
        try:
            for row in range(self.files_model.rowCount()):
                checkbox_item = self.files_model.item(row, 0)
                if checkbox_item and checkbox_item.isCheckable():
                    checkbox_item.setCheckState(state)
        finally:
            self.files_model.blockSignals(False)
        # blockSignals prevented itemChanged from firing, so the view never got
        # a repaint signal. Emit dataChanged for all of column 0 to trigger it.
        if self.files_model.rowCount() > 0:
            self.files_model.dataChanged.emit(
                self.files_model.index(0, 0),
                self.files_model.index(self.files_model.rowCount() - 1, 0),
            )
        self._set_batch_buttons_enabled(state == Qt.CheckState.Checked)

    def _sync_header_checkbox(self):
        """Update header checkbox to reflect current row check states."""
        total = 0
        checked = 0
        for row in range(self.files_model.rowCount()):
            checkbox_item = self.files_model.item(row, 0)
            if checkbox_item and checkbox_item.isCheckable():
                total += 1
                if checkbox_item.checkState() == Qt.CheckState.Checked:
                    checked += 1
        if total == 0 or checked == 0:
            state = Qt.CheckState.Unchecked
        elif checked == total:
            state = Qt.CheckState.Checked
        else:
            state = Qt.CheckState.PartiallyChecked
        self.files_tv.header().set_check_state(state)

    def _on_download_selected_clicked(self):
        """Emit batch download signal for checked files."""
        checked_files = self._get_checked_files()
        if checked_files:
            self.batch_download_requested.emit(checked_files)

    def _on_delete_selected_clicked(self):
        """Show confirmation dialog before deleting selected files."""
        checked_files = self._get_checked_files()
        if checked_files:
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

    def _show_empty_space_menu(self, pos):
        """Show a context menu with only the 'Create new folder' action."""
        menu = QMenu(self)
        action = QAction("Create new folder", self)
        action.setIcon(QgsApplication.getThemeIcon("/mActionNewFolder.svg"))
        action.triggered.connect(self.show_create_folder_dialog)
        menu.addAction(action)
        menu.popup(self.files_tv.viewport().mapToGlobal(pos))

    def menu_requested(self, pos):
        index = self.files_tv.indexAt(pos)
        file_item = self.files_model.itemFromIndex(index)

        # Click on empty space (below all rows): show create folder menu
        if not index.isValid() or not file_item:
            self._show_empty_space_menu(pos)
            return

        selected_item = file_item.data(Qt.ItemDataRole.UserRole)

        # Click on an empty column of a folder row (cols 2-4 have no item data
        # for folders): show create folder menu
        if not selected_item:
            self._show_empty_space_menu(pos)
            return

        # Click on a file row in a non-name column: no context menu
        if index.column() != 1 and selected_item["type"] != "directory":
            return

        # Click on an item: show item menu
        self._show_item_menu(pos, index, selected_item)

    def _show_item_menu(self, pos, index, selected_item):
        """Show a context menu with actions for the selected file/folder."""
        # For scenarios, fetch the descriptor once and reuse it
        descriptor = None
        if selected_item.get("data_type") == "scenario":
            descriptor = get_tenant_file_descriptor(selected_item["descriptor_id"])
        file_actions = get_file_actions(selected_item, descriptor=descriptor)
        # Resolve local path on demand; filter out action if not available locally
        local_path = self._resolve_local_path(
            selected_item,
            self.project["slug"],
            hcc_working_dir(),
            descriptor=descriptor,
        )
        if not local_path:
            file_actions = [
                a for a in file_actions if a != FileAction.OPEN_IN_FILE_BROWSER
            ]
        menu = QMenu(self)
        menu.setToolTipsVisible(True)
        data_type = selected_item.get("data_type")
        actions = []
        # create and connect actions
        for file_action in file_actions:
            action = QAction(file_action.icon, file_action.value, self)
            action.setToolTip(file_action.get_tooltip(data_type))
            action_signal = self.file_signals.get_signal(file_action)
            if file_action == FileAction.RENAME:
                action.triggered.connect(
                    lambda _, selected_item=selected_item: self.edit_file_name(
                        index, selected_item
                    )
                )
            elif file_action == FileAction.OPEN_IN_BROWSER:
                action.triggered.connect(lambda _: self.open_in_browser(selected_item))
            elif file_action == FileAction.OPEN_IN_FILE_BROWSER:
                action.triggered.connect(
                    lambda _, path=local_path: self.open_in_file_browser(path)
                )
            elif file_action == FileAction.VIEW_REVISIONS:
                action.triggered.connect(
                    lambda _, signal=action_signal: signal.emit(
                        self.project, selected_item
                    )
                )
            elif file_action == FileAction.COPY_WMS_URL:
                action.triggered.connect(
                    lambda _, item=selected_item: copy_wms_url_to_clipboard(
                        item, self.communication
                    )
                )
            else:
                action.triggered.connect(
                    lambda _, signal=action_signal: signal.emit(selected_item)
                )
            actions.append(action)
        for i, action in enumerate(actions):
            if file_actions[i] in (FileAction.DELETE, FileAction.REMOVE_FROM_PROJECT):
                menu.addSeparator()
            menu.addAction(action)
        menu.popup(self.files_tv.viewport().mapToGlobal(pos))

    def open_in_browser(self, selected_item):
        if selected_item.get("data_type") != "threedi_schematisation":
            return
        schematisation = get_threedi_schematisation(
            self.communication, selected_item["descriptor_id"]
        )
        if not schematisation or not schematisation.get("management_url"):
            return
        QDesktopServices.openUrl(QUrl(schematisation["management_url"]))

    def open_in_file_browser(self, local_path: str):
        """Open a local path in the OS file explorer."""
        path = Path(local_path)
        # For files, open the containing directory
        if path.is_file():
            path = path.parent
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _resolve_local_path(
        self,
        file: dict,
        project_slug: str,
        working_dir: str,
        descriptor: dict = None,
    ) -> Optional[str]:
        """Resolve the local path for a file, or return None if not present locally."""
        data_type = file.get("data_type")
        if data_type == "threedi_schematisation":
            return self._resolve_schematisation_local_path(file, working_dir)
        elif data_type == "scenario":
            return self._resolve_scenario_local_path(
                file,
                project_slug,
                working_dir,
                descriptor=descriptor,
            )
        else:
            local_path = get_local_file_path(project_slug, file["id"])
            return local_path if Path(local_path).exists() else None

    def _resolve_schematisation_local_path(
        self, file: dict, working_dir: str
    ) -> Optional[str]:
        """Resolve the local revision directory for a schematisation file."""
        if not working_dir:
            return None
        schematisation = get_threedi_schematisation(
            self.communication, file["descriptor_id"]
        )
        if not schematisation:
            return None
        latest_revision = schematisation.get("latest_revision")
        if not latest_revision:
            return None
        revision_dir = get_local_schematisation_revision_dir(
            working_dir,
            schematisation["schematisation"]["id"],
            schematisation["schematisation"]["name"],
            latest_revision["number"],
            create=False,
        )
        if revision_dir and revision_dir.exists():
            return str(revision_dir)
        return None

    def _resolve_scenario_local_path(
        self,
        file: dict,
        project_slug: str,
        working_dir: str,
        descriptor: dict = None,
    ) -> Optional[str]:
        """Resolve the local results directory for a scenario file."""
        if descriptor is None:
            descriptor = get_tenant_file_descriptor(file["descriptor_id"])
        if not descriptor:
            return None
        meta = descriptor.get("meta")
        if not meta or "id" not in meta:
            return None
        # Try 3Di results path first
        if working_dir:
            results_dir = get_local_results_dir_from_meta(meta, working_dir)
            if results_dir and Path(results_dir).exists():
                return results_dir
        # Fall back to generic local dir structure
        local_dir = get_local_dir_structure(project_slug, file["id"])
        return local_dir if Path(local_dir).exists() else None

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
        self.files_tv.setColumnHidden(0, not self.select_btn.isChecked())
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
