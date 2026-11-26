"""Dialog to browse the folders of a Rana project and pick one."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager

from qgis.core import QgsApplication
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QFont
from qgis.PyQt.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from rana_qgis_plugin.network_manager import NetworkUnavailableError
from rana_qgis_plugin.utils.api import RanaFetchError, get_tenant_project_files
from rana_qgis_plugin.widgets.name_input_dialog import (
    NameInputDialog,
    validate_item_name,
)

PLACEHOLDER_ROLE = Qt.ItemDataRole.UserRole + 1
VIRTUAL_ROLE = Qt.ItemDataRole.UserRole + 2
VIRTUAL_TOOLTIP = "New folder, created when results are uploaded"


@contextmanager
def busy_cursor() -> Iterator[None]:
    QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
    try:
        yield
    finally:
        QApplication.restoreOverrideCursor()


def error_message(error: Exception) -> str:
    if isinstance(error, RanaFetchError):
        return error.msg
    return "No network connection."


def is_virtual(item: QTreeWidgetItem) -> bool:
    return bool(item.data(0, VIRTUAL_ROLE))


class RanaFolderPicker(QDialog):
    """Browse real project folders, add virtual ones, and return the selected path."""

    def __init__(
        self,
        project: dict,
        start_folder: str,
        list_folders: Callable = get_tenant_project_files,
        parent=None,
    ):
        super().__init__(parent)
        self.project = project
        self.list_folders = list_folders
        self.setWindowTitle("Select results folder")
        self.setMinimumWidth(420)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.error_label = QLabel()
        self.error_label.setVisible(False)
        self.new_button = QPushButton("New folder…")
        self.rename_button = QPushButton("Rename…")
        self.delete_button = QPushButton("Delete")
        self.new_button.clicked.connect(self.new_folder)
        self.rename_button.clicked.connect(self.rename_folder)
        self.delete_button.clicked.connect(self.delete_folder)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Select")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        actions = QHBoxLayout()
        for button in (self.new_button, self.rename_button, self.delete_button):
            actions.addWidget(button)
        actions.addStretch()

        layout = QVBoxLayout(self)
        layout.addWidget(self.tree)
        layout.addWidget(self.error_label)
        layout.addLayout(actions)
        layout.addWidget(buttons)

        self.tree.itemExpanded.connect(self.on_item_expanded)
        self.tree.currentItemChanged.connect(self.update_buttons)
        root = QTreeWidgetItem(self.tree, [project.get("name", project["id"])])
        root.setIcon(0, QgsApplication.getThemeIcon("mIconFolder.svg"))
        try:
            with busy_cursor():
                self.load_children(root)
                self.expand_to(start_folder)
        except (NetworkUnavailableError, RanaFetchError) as error:
            QMessageBox.warning(parent, "Select results folder", error_message(error))
            self.reject()

    def expand_to(self, folder_path: str) -> None:
        """Expand and select *folder_path*. Missing segments become virtual folders."""
        item = self.tree.topLevelItem(0)
        for segment in (part for part in folder_path.split("/") if part):
            self.ensure_loaded(item)
            item.setExpanded(True)
            child = self.find_child(item, segment)
            if child is None:
                child = self.add_virtual_folder(item, segment)
            item = child
        self.ensure_loaded(item)
        item.setExpanded(True)
        self.tree.setCurrentItem(item)

    def find_child(self, item: QTreeWidgetItem, name: str) -> QTreeWidgetItem | None:
        for index in range(item.childCount()):
            if item.child(index).text(0) == name:
                return item.child(index)
        return None

    def item_path(self, item: QTreeWidgetItem) -> str:
        """Project path with trailing slash, derived from the ancestors. Root is ''."""
        if item.parent() is None:
            return ""
        return f"{self.item_path(item.parent())}{item.text(0)}/"

    def needs_load(self, item: QTreeWidgetItem) -> bool:
        return item.childCount() == 1 and bool(item.child(0).data(0, PLACEHOLDER_ROLE))

    def ensure_loaded(self, item: QTreeWidgetItem) -> None:
        if self.needs_load(item):
            self.load_children(item)

    def load_children(self, item: QTreeWidgetItem) -> None:
        """Fetch the subfolders of *item* and replace its placeholder."""
        path = self.item_path(item)
        params = {"path": path} if path else None
        entries = self.list_folders(self.project["id"], params=params)
        item.takeChildren()
        for entry in entries:
            if entry["type"] != "directory":
                continue
            name = entry["id"].rstrip("/").rsplit("/", 1)[-1]
            child = QTreeWidgetItem(item, [name])
            child.setIcon(0, QgsApplication.getThemeIcon("mIconFolder.svg"))
            placeholder = QTreeWidgetItem(child, ["Loading…"])
            placeholder.setData(0, PLACEHOLDER_ROLE, True)

    def add_virtual_folder(self, parent: QTreeWidgetItem, name: str) -> QTreeWidgetItem:
        """Add a folder that exists only in the dialog until results are uploaded."""
        child = QTreeWidgetItem(parent, [name])
        child.setData(0, VIRTUAL_ROLE, True)
        child.setIcon(0, QgsApplication.getThemeIcon("mActionNewFolder.svg"))
        font = QFont()
        font.setItalic(True)
        child.setFont(0, font)
        child.setToolTip(0, VIRTUAL_TOOLTIP)
        return child

    def validate_name(
        self,
        parent: QTreeWidgetItem,
        name: str,
        skip: QTreeWidgetItem | None = None,
    ) -> str | None:
        """Return an error for *name* under *parent*, or None if it is free."""
        error = validate_item_name(name)
        if error:
            return error
        try:
            self.ensure_loaded(parent)
        except (NetworkUnavailableError, RanaFetchError) as load_error:
            return f"Could not check existing folders: {error_message(load_error)}"
        for index in range(parent.childCount()):
            sibling = parent.child(index)
            if sibling is skip:
                continue
            if sibling.text(0).casefold() == name.casefold():
                return f'A folder named "{sibling.text(0)}" already exists.'
        return None

    def new_folder(self) -> None:
        parent = self.tree.currentItem() or self.tree.topLevelItem(0)
        dialog = NameInputDialog(
            "New folder",
            "Folder name:",
            "",
            lambda name: self.create_virtual_folder(parent, name),
            self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.tree.setCurrentItem(self.find_child(parent, dialog.line_edit.text()))

    def create_virtual_folder(self, parent: QTreeWidgetItem, name: str) -> str | None:
        error = self.validate_name(parent, name)
        if error:
            return error
        self.add_virtual_folder(parent, name)
        return None

    def rename_folder(self) -> None:
        item = self.tree.currentItem()
        if item is None or not is_virtual(item):
            return
        dialog = NameInputDialog(
            "Rename folder",
            "New name:",
            item.text(0),
            lambda name: self.rename_virtual_folder(item, name),
            self,
        )
        dialog.exec()

    def rename_virtual_folder(self, item: QTreeWidgetItem, name: str) -> str | None:
        error = self.validate_name(item.parent(), name, skip=item)
        if error:
            return error
        item.setText(0, name)
        return None

    def delete_folder(self) -> None:
        item = self.tree.currentItem()
        if item is None or not is_virtual(item):
            return
        parent = item.parent()
        parent.removeChild(item)
        self.tree.setCurrentItem(parent)

    def update_buttons(self, current: QTreeWidgetItem | None, _previous) -> None:
        virtual = current is not None and is_virtual(current)
        self.rename_button.setEnabled(virtual)
        self.delete_button.setEnabled(virtual)

    def on_item_expanded(self, item: QTreeWidgetItem) -> None:
        if not self.needs_load(item):
            return
        try:
            with busy_cursor():
                self.load_children(item)
            self.error_label.setVisible(False)
        except (NetworkUnavailableError, RanaFetchError) as error:
            self.error_label.setText(f"Could not load folders: {error_message(error)}")
            self.error_label.setVisible(True)

    def selected_folder(self) -> str:
        item = self.tree.currentItem()
        return self.item_path(item) if item is not None else ""
