"""Dialog to browse the folders of a Rana project and pick one."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager

from qgis.core import QgsApplication
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QMessageBox,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from rana_qgis_plugin.network_manager import NetworkUnavailableError
from rana_qgis_plugin.utils.api import RanaFetchError, get_tenant_project_files

PLACEHOLDER_ROLE = Qt.ItemDataRole.UserRole + 1


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


class RanaFolderPicker(QDialog):
    """Browse real project folders and return the selected project path."""

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
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Select")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.tree)
        layout.addWidget(self.error_label)
        layout.addWidget(buttons)

        self.tree.itemExpanded.connect(self.on_item_expanded)
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
        """Expand and select the deepest existing folder on *folder_path*."""
        item = self.tree.topLevelItem(0)
        for segment in (part for part in folder_path.split("/") if part):
            self.ensure_loaded(item)
            item.setExpanded(True)
            child = self.find_child(item, segment)
            if child is None:
                break
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
