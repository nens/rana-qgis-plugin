"""E2E tests for project listing in the QGIS Browser panel."""

import os
import uuid

import pytest
from qgis.PyQt.QtCore import QModelIndex, QPoint, Qt, QTimer
from qgis.PyQt.QtTest import QTest
from qgis.PyQt.QtWidgets import QFileDialog, QTreeView

from rana_qgis_plugin.data_items.file_actions import FileAction
from rana_qgis_plugin.data_items.file_item import RanaFileDataItem
from rana_qgis_plugin.data_items.folder_item import (
    RanaFilesDataItem,
    RanaFolderDataItem,
)
from rana_qgis_plugin.data_items.project_item import RanaProjectDataItem
from rana_qgis_plugin.utils.api import (
    create_project,
    create_tenant_project_directory,
    delete_project,
)

from .test_utils import click_context_menu_action, make_modal_handler


@pytest.fixture
def authenticated(plugin, qtbot, qgis_application):
    """Ensure the QGIS auth manager has resolved the authcfg by performing one API call."""
    root = plugin.rana_root_item
    root.refresh()
    qtbot.waitUntil(
        lambda: root.children() is not None,
        timeout=30000,
    )


@pytest.fixture
def rana_project(authenticated, plugin):
    result = create_project(
        {"code": f"e2e_{uuid.uuid4().hex[:24]}", "name": f"e2e_{uuid.uuid4().hex[:56]}"}
    )
    assert result is not None, "create_project failed — check authentication"
    yield result
    if result.get("id"):
        delete_project(result["id"])


def get_child_names(plugin):
    plugin.rana_root_item.refresh()
    return [
        child.name()
        for child in (plugin.rana_root_item.children() or [])
        if isinstance(child, RanaProjectDataItem)
    ]


def test_project_listing(plugin, qtbot, rana_project):
    # Step 1: project created by fixture — assert it appears after refresh
    qtbot.waitUntil(
        lambda: rana_project["name"] in get_child_names(plugin),
        timeout=30000,
    )
    qtbot.waitUntil(
        lambda: rana_project["name"] in get_child_names(plugin),
        timeout=30000,
    )

    # Step 2: delete project via API, refresh, assert it disappears
    delete_project(rana_project["id"])
    rana_project["id"] = None  # prevent double-delete in fixture teardown

    qtbot.waitUntil(
        lambda: rana_project["name"] not in get_child_names(plugin),
        timeout=30000,
    )


def test_files(plugin, qtbot, qgis_application, rana_project):
    # Add folders to project
    create_tenant_project_directory(rana_project["id"], "foo")
    create_tenant_project_directory(rana_project["id"], "foo/bar")
    # Get project and get Files root
    qtbot.waitUntil(
        lambda: rana_project["name"] in get_child_names(plugin),
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

    def assert_visible(item):
        index = item_index(item)
        assert index.isValid(), f"No model index for {item.name()}"
        assert tree.isExpanded(index.parent()), f"Parent of {item.name()} is collapsed"
        assert tree.isRowHidden(index.row(), index.parent()) is False, item.name()

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
        for child in (project_item.children() or [])
        if isinstance(child, RanaFilesDataItem)
    )

    expand_item(files_item)
    qtbot.waitUntil(
        lambda: any(
            isinstance(child, RanaFolderDataItem) and child.name() == "foo"
            for child in (files_item.children() or [])
        ),
        timeout=30000,
    )
    foo_item = next(
        child
        for child in (files_item.children() or [])
        if isinstance(child, RanaFolderDataItem) and child.name() == "foo"
    )
    assert_visible(foo_item)

    expand_item(foo_item)
    qtbot.waitUntil(
        lambda: any(
            isinstance(child, RanaFolderDataItem) and child.name() == "bar"
            for child in (foo_item.children() or [])
        ),
        timeout=30000,
    )
    bar_item = next(
        child
        for child in (foo_item.children() or [])
        if isinstance(child, RanaFolderDataItem) and child.name() == "bar"
    )
    assert_visible(bar_item)

    def select_upload_file(qtbot, modal):
        modal.selectFile(os.path.join(os.path.dirname(__file__), "data", "upload.gpkg"))
        qtbot.keyClick(modal, Qt.Key.Key_Enter)

    QTimer.singleShot(500, make_modal_handler(qtbot, QFileDialog, select_upload_file))
    click_context_menu_action(qtbot, foo_item, FileAction.UPLOAD_FILES.value)

    qtbot.waitUntil(
        lambda: any(
            isinstance(child, RanaFileDataItem) and child.name() == "upload.gpkg"
            for child in (foo_item.children() or [])
        ),
        timeout=30000,
    )
    upload_item = next(
        child
        for child in (foo_item.children() or [])
        if isinstance(child, RanaFileDataItem) and child.name() == "upload.gpkg"
    )
    assert_visible(upload_item)
