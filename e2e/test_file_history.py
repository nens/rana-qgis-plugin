"""E2E tests for file history in the QGIS Browser panel."""

import time
from pathlib import Path

from qgis.PyQt.QtCore import QModelIndex, QPoint, Qt, QTimer
from qgis.PyQt.QtWidgets import QApplication, QFileDialog, QTreeView

from rana_qgis_plugin.data_items.file_actions import FileAction
from rana_qgis_plugin.data_items.file_item import RanaFileDataItem
from rana_qgis_plugin.data_items.folder_item import (
    RanaFilesDataItem,
    RanaFolderDataItem,
)
from rana_qgis_plugin.data_items.project_item import RanaProjectDataItem
from rana_qgis_plugin.widgets.version_history_dialog import RanaHistoryDialog

from .test_utils import click_context_menu_action, make_modal_handler


def test_file_history(plugin, qtbot, qgis_application, rana_project):
    """Check history for the Files root, a folder, and an uploaded file."""
    # Create a folder for the history checks.
    # bypassing UI because that is covered by other tests
    folder_name = f"history_{rana_project['id'][:8]}"
    assert plugin.loader.create_folder(rana_project["id"], "", folder_name) is None

    # Find the project in the Browser.
    plugin.rana_root_item.refresh()
    qtbot.waitUntil(
        lambda: any(
            isinstance(child, RanaProjectDataItem)
            and child.name() == rana_project["name"]
            for child in (plugin.rana_root_item.children() or [])
        ),
        timeout=30000,
    )
    project_item = next(
        child
        for child in plugin.rana_root_item.children()
        if isinstance(child, RanaProjectDataItem)
        and child.name() == rana_project["name"]
    )

    tree = plugin.browser_dock.findChild(QTreeView)
    assert tree is not None, "Browser tree not found"
    model = tree.model()

    # Find a Browser index for a data item.
    def item_index(item, parent=None):
        parent = parent or QModelIndex()
        for row in range(model.rowCount(parent)):
            index = model.index(row, 0, parent)
            source_index = model.mapToSource(index)
            if model.sourceModel().dataItem(source_index) is item:
                return index
            nested = item_index(item, index)
            if nested.isValid():
                return nested
        return QModelIndex()

    # Expand a Browser item.
    def expand_item(item):
        index = item_index(item)
        assert index.isValid(), f"No model index for {item.name()}"
        tree.scrollTo(index)
        tree.setCurrentIndex(index)
        rect = tree.visualRect(index)
        assert rect.isValid(), f"No visual rectangle for {item.name()}"
        qtbot.mouseClick(
            tree.viewport(),
            Qt.MouseButton.LeftButton,
            pos=rect.center() - QPoint(rect.height() // 2, 0),
        )
        tree.expand(index)
        qgis_application.processEvents()

    # Open history and return the number of entries.
    def history_rows(item):
        result = []
        deadline: list[float | None] = [None]

        def inspect_history():
            if deadline[0] is None:
                deadline[0] = time.monotonic() + 30
            dialog = QApplication.activeModalWidget()
            if isinstance(dialog, RanaHistoryDialog) and dialog.current_task is None:
                result.append(dialog.model.rowCount())
                dialog.accept()
                return
            if deadline[0] is not None and time.monotonic() < deadline[0]:
                QTimer.singleShot(100, inspect_history)
            elif isinstance(dialog, RanaHistoryDialog):
                result.append(-1)
                dialog.reject()

        QTimer.singleShot(100, inspect_history)
        click_context_menu_action(qtbot, item, FileAction.VERSION_HISTORY.value)

        qtbot.waitUntil(
            lambda: bool(result),
            timeout=30000,
        )
        return result[0]

    # Open the project and its Files folder.
    expand_item(project_item)
    qtbot.waitUntil(
        lambda: any(
            isinstance(child, RanaFilesDataItem)
            for child in (project_item.children() or [])
        ),
        timeout=30000,
    )
    files_item = next(
        child
        for child in project_item.children()
        if isinstance(child, RanaFilesDataItem)
    )
    expand_item(files_item)
    files_item.refresh()

    # Find the folder created above.
    qtbot.waitUntil(
        lambda: any(
            isinstance(child, RanaFolderDataItem) and child.name() == folder_name
            for child in (files_item.children() or [])
        ),
        timeout=30000,
    )
    folder_item = next(
        child
        for child in files_item.children()
        if isinstance(child, RanaFolderDataItem) and child.name() == folder_name
    )

    # Check history for the Files item and the new folder.
    assert history_rows(files_item) == 1
    assert history_rows(folder_item) == 1
    expand_item(folder_item)

    # Upload a file to the folder.
    # bypassing UI (mostly) because that is covered by other tests
    def select_upload_file(qtbot, modal):
        modal.selectFile(str(Path(__file__).parent / "data" / "upload.gpkg"))
        qtbot.keyClick(modal, Qt.Key.Key_Enter)

    QTimer.singleShot(500, make_modal_handler(qtbot, QFileDialog, select_upload_file))
    plugin.loader.upload_files(
        rana_project,
        folder_name,
        parent=tree,
        refresh_callback=folder_item.refresh_if_populated,
    )
    # Wait for the uploaded file to appear in the Browser.
    qtbot.waitUntil(
        lambda: any(
            isinstance(child, RanaFileDataItem) and child.name() == "upload.gpkg"
            for child in (folder_item.children() or [])
        ),
        timeout=30000,
    )
    file_item = next(
        child
        for child in folder_item.children()
        if isinstance(child, RanaFileDataItem) and child.name() == "upload.gpkg"
    )

    # Check history for the uploaded file.
    assert history_rows(file_item) == 1
