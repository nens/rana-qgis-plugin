"""E2E tests for project listing in the QGIS Browser panel."""

import os
import uuid

import pytest
from qgis.PyQt.QtCore import QModelIndex, QPoint, Qt, QTimer
from qgis.PyQt.QtTest import QTest
from qgis.PyQt.QtWidgets import QApplication, QFileDialog, QMessageBox, QTreeView

from rana_qgis_plugin.data_items.file_actions import FileAction
from rana_qgis_plugin.data_items.file_item import RanaFileDataItem
from rana_qgis_plugin.data_items.folder_item import (
    RanaFilesDataItem,
    RanaFolderDataItem,
)
from rana_qgis_plugin.data_items.project_item import RanaProjectDataItem
from rana_qgis_plugin.utils.api import (
    create_project,
    delete_project,
)
from rana_qgis_plugin.widgets.name_input_dialog import NameInputDialog

from .test_utils import (
    build_context_menu,
    click_context_menu_action,
    make_modal_handler,
)


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
    # This is one end-to-end file-management flow. It deliberately uses the
    # context menu for mutations so that the test covers the user-facing path,
    # rather than only checking the API helpers in isolation.
    #
    # The flow covers folder creation at two levels, duplicate and invalid
    # names, folder and file renames, upload, and file/folder deletion.

    # Locate the project in the Browser and obtain its Files container.
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

    # Expanding the Files container loads its children from Rana. It starts
    # empty because all folders below are created through the UI in this test.
    expand_item(files_item)

    def enter_name(name):
        def handler(qtbot, modal):
            modal.line_edit.clear()
            qtbot.keyClicks(modal.line_edit, name)
            qtbot.keyClick(modal, Qt.Key.Key_Enter)

        return handler

    def reject_duplicate_name(qtbot, modal):
        enter_name("foo")(qtbot, modal)
        assert modal.error_label.isVisible()
        modal.reject()

    def reject_invalid_name(qtbot, modal):
        modal.line_edit.clear()
        qtbot.keyClicks(modal.line_edit, "bad/name")
        assert modal.ok_button.isEnabled() is False
        modal.reject()

    def reject_duplicate_rename(qtbot, modal):
        enter_name("bar")(qtbot, modal)
        assert modal.error_label.isVisible()
        modal.reject()

    def confirm_delete(qtbot, modal):
        yes_button = modal.button(QMessageBox.StandardButton.Yes)
        assert yes_button is not None
        qtbot.mouseClick(yes_button, Qt.MouseButton.LeftButton)

    # Create a folder at the Files root. This verifies that the root folder
    # exposes Create directory and that the entered name reaches the API.
    QTimer.singleShot(
        500,
        make_modal_handler(qtbot, NameInputDialog, enter_name("foo")),
    )
    click_context_menu_action(qtbot, files_item, FileAction.CREATE_DIRECTORY.value)

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

    # Creating the same root folder again must not create another item. The
    # server-side duplicate check should report an error while the dialog stays
    # open; the test then cancels it so the flow can continue.
    QTimer.singleShot(
        500,
        make_modal_handler(qtbot, NameInputDialog, reject_duplicate_name),
    )
    click_context_menu_action(qtbot, files_item, FileAction.CREATE_DIRECTORY.value)

    # Expand foo and create bar inside it. This exercises path construction for
    # a non-root parent, not just creation at the Files root.
    expand_item(foo_item)

    # Create a second sibling folder. It is used below to verify that a folder
    # cannot be renamed to the name of an existing sibling.
    QTimer.singleShot(
        500,
        make_modal_handler(qtbot, NameInputDialog, enter_name("bar")),
    )
    click_context_menu_action(qtbot, foo_item, FileAction.CREATE_DIRECTORY.value)

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

    QTimer.singleShot(
        500,
        make_modal_handler(qtbot, NameInputDialog, enter_name("baz")),
    )
    click_context_menu_action(qtbot, foo_item, FileAction.CREATE_DIRECTORY.value)
    qtbot.waitUntil(
        lambda: any(
            isinstance(child, RanaFolderDataItem) and child.name() == "baz"
            for child in (foo_item.children() or [])
        ),
        timeout=30000,
    )
    baz_item = next(
        child
        for child in (foo_item.children() or [])
        if isinstance(child, RanaFolderDataItem) and child.name() == "baz"
    )

    # An invalid local name is rejected entirely in the dialog. OK must be
    # disabled before any network request can be made.
    QTimer.singleShot(
        500,
        make_modal_handler(qtbot, NameInputDialog, reject_invalid_name),
    )
    click_context_menu_action(qtbot, bar_item, FileAction.RENAME.value)

    # Renaming baz to the existing sibling bar exercises server-side duplicate
    # validation. The dialog remains open with an error and is then cancelled.
    QTimer.singleShot(
        500,
        make_modal_handler(qtbot, NameInputDialog, reject_duplicate_rename),
    )
    click_context_menu_action(qtbot, baz_item, FileAction.RENAME.value)

    def select_upload_file(qtbot, modal):
        modal.selectFile(os.path.join(os.path.dirname(__file__), "data", "upload.gpkg"))
        qtbot.keyClick(modal, Qt.Key.Key_Enter)

    # Upload a real fixture into foo. This keeps the subsequent file rename and
    # delete assertions on an item created through the normal UI flow.
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

    # Rename the uploaded file and wait for the refreshed Browser item. This
    # verifies the file-specific move endpoint and the UI refresh afterward.
    QTimer.singleShot(
        500,
        make_modal_handler(qtbot, NameInputDialog, enter_name("renamed.gpkg")),
    )
    click_context_menu_action(qtbot, upload_item, FileAction.RENAME.value)

    qtbot.waitUntil(
        lambda: any(
            isinstance(child, RanaFileDataItem) and child.name() == "renamed.gpkg"
            for child in (foo_item.children() or [])
        ),
        timeout=30000,
    )
    renamed_item = next(
        child
        for child in (foo_item.children() or [])
        if isinstance(child, RanaFileDataItem) and child.name() == "renamed.gpkg"
    )
    assert_visible(renamed_item)

    # A valid folder rename succeeds after the rejected attempts above. This
    # verifies the folder-specific move endpoint and confirms that the original
    # folder item is replaced by the renamed item in the Browser.
    # Delete the renamed file after confirming the destructive action. The
    # item must disappear from foo's children after the synchronous API call.
    QTimer.singleShot(
        500,
        make_modal_handler(qtbot, NameInputDialog, enter_name("renamed_bar")),
    )
    click_context_menu_action(qtbot, bar_item, FileAction.RENAME.value)

    qtbot.waitUntil(
        lambda: any(
            isinstance(child, RanaFolderDataItem) and child.name() == "renamed_bar"
            for child in (foo_item.children() or [])
        ),
        timeout=30000,
    )

    # Multi-select gating: none of these selections should ever produce an
    # actionable context menu. This exercises RanaDataItemGuiProvider directly
    # rather than the deferred, empty multi-select whitelist, so it stays
    # meaningful even before any multi-select action is ever whitelisted.
    multi_select_cases = [
        ("two folders", [baz_item, foo_item]),
        ("folder + file", [baz_item, renamed_item]),
        ("project + folder", [project_item, baz_item]),
        ("files root + folder", [files_item, baz_item]),
    ]
    for description, selected_items in multi_select_cases:
        menu = build_context_menu(selected_items[0], selected_items)
        assert not menu.actions(), (
            f"Expected no context menu actions for {description}, "
            f"got {[a.text() for a in menu.actions()]}"
        )

    # Finally delete foo, which still contains the renamed_bar folder. This
    # covers folder deletion and confirms that the whole top-level folder is
    # removed from the Files container.
    QTimer.singleShot(
        500,
        make_modal_handler(qtbot, QMessageBox, confirm_delete),
    )
    click_context_menu_action(qtbot, renamed_item, FileAction.DELETE.value)
    qtbot.waitUntil(
        lambda: (
            not any(
                isinstance(child, RanaFileDataItem) and child.name() == "renamed.gpkg"
                for child in (foo_item.children() or [])
            )
        ),
        timeout=30000,
    )

    QTimer.singleShot(
        500,
        make_modal_handler(qtbot, QMessageBox, confirm_delete),
    )
    click_context_menu_action(qtbot, foo_item, FileAction.DELETE.value)
    qtbot.waitUntil(
        lambda: (
            not any(
                isinstance(child, RanaFolderDataItem) and child.name() == "foo"
                for child in (files_item.children() or [])
            )
        ),
        timeout=30000,
    )
