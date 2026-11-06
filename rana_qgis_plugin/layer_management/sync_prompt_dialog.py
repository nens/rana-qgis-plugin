from pathlib import PurePosixPath

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon, QPalette
from qgis.PyQt.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from rana_qgis_plugin.icons import dir_icon, rana_icon
from rana_qgis_plugin.layer_management.sync_changes import (
    ChangedFile,
    SyncChanges,
    SyncFileKey,
    SyncKind,
)
from rana_qgis_plugin.layer_management.sync_summary import build_summary
from rana_qgis_plugin.utils.generic import get_file_icon_name
from rana_qgis_plugin.widgets.utils_icons import get_icon_from_theme

SECTION_TITLES = {SyncKind.DATA: "Data changes:", SyncKind.STYLE: "Style changes:"}
DEFAULT_WIDTH = 480
DEFAULT_HEIGHT = 420
MIN_WIDTH = 320
CHECKABLE_PARENT_FLAGS = (
    Qt.ItemFlag.ItemIsEnabled
    | Qt.ItemFlag.ItemIsUserCheckable
    | Qt.ItemFlag.ItemIsAutoTristate
)
CHECKABLE_FILE_FLAGS = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable
DISPLAY_ONLY_FLAGS = Qt.ItemFlag.ItemIsEnabled


class SyncDialog(QDialog):
    """Lists the files and layers that a sync covers, and lets the user deselect files.

    The dialog only collects the choice: callers read `selected(kind)` and decide
    what to dispatch. Everything starts checked.
    """

    def __init__(
        self,
        parent,
        title: str,
        confirm_label: str,
        cancel_label: str,
        changes: SyncChanges,
        show_kinds: bool = True,
        project_names: dict[str, str] | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setSizeGripEnabled(True)
        self.setMinimumWidth(MIN_WIDTH)
        self.resize(DEFAULT_WIDTH, DEFAULT_HEIGHT)
        self.show_kinds = show_kinds
        self.project_names = project_names or {}
        self.file_items: dict[SyncKind, dict[SyncFileKey, QTreeWidgetItem]] = {
            kind: {} for kind in SyncKind
        }

        summary_label = QLabel(build_summary(changes, include_kinds=show_kinds))
        summary_label.setWordWrap(True)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setFrameShape(QFrame.Shape.NoFrame)
        tree_palette = self.tree.palette()
        tree_palette.setColor(
            QPalette.ColorRole.Base, self.palette().color(QPalette.ColorRole.Window)
        )
        self.tree.setPalette(tree_palette)
        for kind in SyncKind:
            self.add_section(kind, changes.files(kind))
        self.tree.expandAll()

        self.confirm_button = QPushButton(confirm_label)
        self.confirm_button.clicked.connect(self.accept)
        cancel_button = QPushButton(cancel_label)
        cancel_button.clicked.connect(self.reject)
        button_row = QHBoxLayout()
        button_row.addStretch()
        button_row.addWidget(self.confirm_button)
        button_row.addWidget(cancel_button)

        layout = QVBoxLayout(self)
        layout.addWidget(summary_label)
        layout.addWidget(self.tree, 1)
        layout.addLayout(button_row)

        self.tree.itemChanged.connect(self.on_item_changed)
        self.update_confirm_button()

    def add_section(
        self, kind: SyncKind, files: dict[SyncFileKey, ChangedFile]
    ) -> None:
        if not files:
            return
        section = (
            self.add_checkable_parent(self.tree, SECTION_TITLES[kind])
            if self.show_kinds
            else self.tree.invisibleRootItem()
        )
        projects: dict[str, QTreeWidgetItem] = {}
        folders: dict[tuple[str, tuple[str, ...]], QTreeWidgetItem] = {}
        ordered = sorted(
            files.items(), key=lambda item: (item[0].project_id, item[1].path)
        )
        for key, changed in ordered:
            if key.project_id not in projects:
                projects[key.project_id] = self.add_checkable_parent(
                    section,
                    self.project_names.get(key.project_id, key.project_id),
                    rana_icon,
                )
            parent = projects[key.project_id]
            path = PurePosixPath(changed.path)
            for depth in range(1, len(path.parts)):
                folder_path = path.parts[:depth]
                folder_key = (key.project_id, folder_path)
                if folder_key not in folders:
                    folders[folder_key] = self.add_checkable_parent(
                        parent, folder_path[-1], dir_icon
                    )
                parent = folders[folder_key]
            file_item = QTreeWidgetItem(parent, [path.name])
            file_item.setIcon(
                0, get_icon_from_theme(get_file_icon_name(changed.icon_type))
            )
            file_item.setFlags(CHECKABLE_FILE_FLAGS)
            file_item.setCheckState(0, Qt.CheckState.Checked)
            for layer in changed.layers:
                layer_item = QTreeWidgetItem(file_item, [layer.name])
                layer_item.setIcon(
                    0, get_icon_from_theme(get_file_icon_name(layer.icon_type))
                )
                layer_item.setFlags(DISPLAY_ONLY_FLAGS)
            self.file_items[kind][key] = file_item

    @staticmethod
    def add_checkable_parent(
        parent: QTreeWidget | QTreeWidgetItem, text: str, icon: QIcon | None = None
    ) -> QTreeWidgetItem:
        item = QTreeWidgetItem(parent, [text])
        if icon is not None:
            item.setIcon(0, icon)
        item.setFlags(CHECKABLE_PARENT_FLAGS)
        item.setCheckState(0, Qt.CheckState.Checked)
        return item

    def selected(self, kind: SyncKind) -> set[SyncFileKey]:
        """Return the keys of the files of `kind` that are checked."""
        return {
            key
            for key, item in self.file_items[kind].items()
            if item.checkState(0) == Qt.CheckState.Checked
        }

    def on_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        self.update_confirm_button()

    def update_confirm_button(self) -> None:
        self.confirm_button.setEnabled(any(self.selected(kind) for kind in SyncKind))
