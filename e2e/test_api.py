import os
import shutil
import uuid
from pathlib import Path

import pytest
from qgis.core import QgsApplication, QgsAuthMethodConfig
from qgis.PyQt.QtCore import Qt, QTimer
from qgis.PyQt.QtGui import QImage
from qgis.PyQt.QtTest import QTest
from qgis.PyQt.QtWidgets import QApplication, QFileDialog, QMessageBox

from e2e.test_utils import (
    canvas_to_image,
    click_tree_item,
    images_equal,
    make_modal_handler,
    press_button_with_moderator,
)
from rana_qgis_plugin.auth import get_authcfg_id
from rana_qgis_plugin.auth_3di import set_3di_auth
from rana_qgis_plugin.constant import PLUGIN_NAME, RANA_SETTINGS_ENTRY
from rana_qgis_plugin.utils.api import (
    create_project,
    delete_project,
)
from rana_qgis_plugin.utils.local_paths import get_local_file_path


def _open_project(plugin, qtbot, project_name):
    """Open the Rana browser and select the first project."""
    row = _find_project_row(plugin.rana_browser.projects_browser, project_name)
    click_tree_item(
        plugin.rana_browser.projects_browser.projects_tv,
        plugin.rana_browser.projects_browser.projects_tv.model().index(row, 0),
        qtbot,
    )
    # Wait until RanaBrowser switched to project widget
    qtbot.waitUntil(
        lambda: plugin.rana_browser.rana_browser.currentIndex() == 1,
        timeout=30000,
    )


def _click_all_checkboxes(files_browser, qtbot):
    """Click each checkbox in the files tree view one by one."""
    for row in range(files_browser.files_model.rowCount()):
        checkbox_index = files_browser.files_model.index(row, 0)
        item = files_browser.files_model.item(row, 0)
        if item is None or not (item.flags() & Qt.ItemFlag.ItemIsUserCheckable):
            continue
        files_browser.files_tv.scrollTo(checkbox_index)
        rect = files_browser.files_tv.visualRect(checkbox_index)
        assert rect.isValid(), f"Invalid rect for checkbox at row {row}"
        qtbot.mouseClick(
            files_browser.files_tv.viewport(), Qt.LeftButton, pos=rect.center()
        )
        QTest.qWait(200)


def _find_file_row(files_browser, filename):
    """Return the row index of a file by name, or None if not found."""
    for row in range(files_browser.files_model.rowCount()):
        name_item = files_browser.files_model.item(row, 1)
        if name_item:
            file_data = name_item.data(Qt.ItemDataRole.UserRole)
            if file_data and file_data.get("id") == filename:
                return row
    return None


def _find_project_row(project_browser, project_name):
    """Return the row index of a project by name, or None if not found."""
    for row in range(project_browser.projects_model.rowCount()):
        name_item = project_browser.projects_model.item(row, 0)
        if name_item:
            project = name_item.text()
            if project == project_name:
                return row
    return None


@pytest.fixture(scope="function")
def login(plugin, qtbot):
    """Open the Rana browser and select the first project."""
    rana_tool_button = plugin.toolbar.widgetForAction(plugin.action)
    QTest.mouseClick(rana_tool_button, Qt.LeftButton)


@pytest.fixture(scope="function")
def rana_project(plugin, login):
    name = "test_project_" + str(uuid.uuid4())
    result = create_project({"code": name[:32], "name": name[:64]})
    plugin.rana_browser.refresh()
    print(result)
    yield result["name"]
    # Stop the auto-refresh timer before the delete_project() network call.
    # delete_project() spins QCoreApplication.processEvents() while waiting
    # for the reply; if the timer fires during that spin it starts a nested
    # fetch_and_populate() which can deadlock with the outer processEvents()
    # loop.
    plugin.rana_browser.refresh_timer.stop()
    delete_project(result["id"])


def test_smoke(plugin, qtbot, request):
    plugin.iface.mainWindow().setWindowTitle(request.node.nodeid)

    assert not plugin.dock_widget
    rana_tool_button = plugin.toolbar.widgetForAction(plugin.action)
    QTest.mouseClick(rana_tool_button, Qt.LeftButton)
    QTest.qWait(1000)
    assert plugin.dock_widget.isVisible()


def test_create_project(plugin, login, qtbot, request, rana_project):
    plugin.iface.mainWindow().setWindowTitle(request.node.nodeid)

    # Wait until projects list is populated
    qtbot.waitUntil(
        lambda: plugin.rana_browser.projects_browser.projects_tv.model().rowCount() > 0,
        timeout=30000,
    )
    assert (
        _find_project_row(plugin.rana_browser.projects_browser, rana_project)
        is not None
    )


def test_login_logout(plugin, request):
    """Test login via toolbar click, then logout, then login again."""
    plugin.iface.mainWindow().setWindowTitle(request.node.nodeid)

    # Step 1: Click toolbar button to trigger login
    rana_tool_button = plugin.toolbar.widgetForAction(plugin.action)
    QTest.mouseClick(rana_tool_button, Qt.LeftButton)
    QTest.qWait(1000)

    # Verify logged-in state
    menu = plugin.iface.mainWindow().getPluginMenu(PLUGIN_NAME)
    menu_texts = [action.text() for action in menu.actions()]
    assert "Logout" in menu_texts
    assert "test user" in menu_texts
    assert plugin.dock_widget is not None
    assert plugin.dock_widget.isVisible()

    # Step 2: Trigger logout via menu action
    logout_action = next(a for a in menu.actions() if a.text() == "Logout")
    menu.popup(menu.mapToGlobal(menu.rect().topLeft()))
    QTest.qWait(100)
    action_rect = menu.actionGeometry(logout_action)
    QTest.mouseClick(menu, Qt.LeftButton, pos=action_rect.center())
    QTest.qWait(500)

    # Verify logged-out state
    menu_texts = [action.text() for action in menu.actions()]
    assert "Logout" not in menu_texts
    assert "test user" not in menu_texts
    assert "Open Rana Panel" in menu_texts
    assert not plugin.dock_widget.isVisible()
    assert get_authcfg_id() is None

    # Step 3: Re-insert auth configs and login again via toolbar click
    auth_manager = QgsApplication.authManager()
    authcfg = QgsAuthMethodConfig()
    authcfg.setName(RANA_SETTINGS_ENTRY)
    authcfg.setMethod("Basic")
    authcfg.setConfig("username", "__key__")
    authcfg.setConfig("password", os.getenv("RANA_PAK", "test_secret"))
    assert authcfg.isValid()
    auth_manager.storeAuthenticationConfig(authcfg)
    set_3di_auth("test_api_key")

    login_action = next(a for a in menu.actions() if a.text() == "Open Rana Panel")
    menu.popup(menu.mapToGlobal(menu.rect().topLeft()))
    QTest.qWait(100)
    action_rect = menu.actionGeometry(login_action)
    QTest.mouseClick(menu, Qt.LeftButton, pos=action_rect.center())
    QTest.qWait(1000)

    # Verify logged-in state again
    menu_texts = [action.text() for action in menu.actions()]
    assert "Logout" in menu_texts
    assert "test user" in menu_texts
    assert plugin.dock_widget.isVisible()


def test_upload(plugin, qtbot, request, rana_project):
    plugin.iface.mainWindow().setWindowTitle(request.node.nodeid)
    _open_project(plugin, qtbot, rana_project)

    # Check we don't start in file detail view
    assert plugin.rana_browser.rana_files.currentIndex() != 1

    def handle_dialog_load_layer(qtbot, modal):
        # Note that this might not work for native widgets (in that case
        # dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True) should be set)
        QTest.qWait(1000)
        press_button_with_moderator(qtbot, modal, Qt.Key_Tab)
        QTest.qWait(1000)
        qtbot.keyClick(modal, Qt.Key.Key_Enter)

    QTimer.singleShot(
        500, make_modal_handler(qtbot, QMessageBox, handle_dialog_load_layer)
    )

    with qtbot.waitSignal(plugin.loader.file_upload_finished, timeout=30000):

        def handle_dialog_select_file(qtbot, modal):
            QTest.qWait(500)
            modal.selectFile("upload.gpkg")
            QTest.qWait(500)
            qtbot.keyClick(modal, Qt.Key.Key_Enter)

        QTimer.singleShot(
            500, make_modal_handler(qtbot, QFileDialog, handle_dialog_select_file)
        )
        QTest.mouseClick(plugin.rana_browser.files_browser.btn_upload, Qt.LeftButton)

    # Wait for layer to appear on canvas
    qtbot.waitUntil(
        lambda: any(
            "test" in layer.name() for layer in plugin.iface.mapCanvas().layers()
        ),
        timeout=30000,
    )

    # Check we end in file detail view
    assert plugin.rana_browser.rana_files.currentIndex() == 1

    # Check whether the map layer was added to the canvas
    assert any("test" in layer.name() for layer in plugin.iface.mapCanvas().layers())
    assert (
        f"/root/Rana/{rana_project[:31]}/files/upload/upload.gpkg"
        in plugin.iface.mapCanvas().layers()[0].dataProvider().dataSourceUri()
    )
    expected_image = QImage(
        os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "data",
            "actual_upload_rendering.png",
        )
    )
    assert not expected_image.isNull(), "Expected image failed to load"
    actual_image = canvas_to_image(plugin.iface.mapCanvas())
    assert images_equal(
        expected_image.convertToFormat(QImage.Format_ARGB32),
        actual_image.convertToFormat(QImage.Format_ARGB32),
    )


def test_select_download_and_delete(plugin, qtbot, request, rana_project):
    """Upload a file, then use select mode to download and delete it."""
    plugin.iface.mainWindow().setWindowTitle(request.node.nodeid)
    _open_project(plugin, qtbot, rana_project)

    def handle_dialog_load_layer(qtbot, modal):
        QTest.qWait(1000)
        press_button_with_moderator(qtbot, modal, Qt.Key_Tab)
        QTest.qWait(1000)
        qtbot.keyClick(modal, Qt.Key.Key_Enter)

    QTimer.singleShot(
        500, make_modal_handler(qtbot, QMessageBox, handle_dialog_load_layer)
    )

    with qtbot.waitSignal(plugin.loader.file_upload_finished, timeout=30000):

        def handle_dialog_select_file(qtbot, modal):
            QTest.qWait(500)
            modal.selectFile("upload.gpkg")
            QTest.qWait(500)
            qtbot.keyClick(modal, Qt.Key.Key_Enter)

        QTimer.singleShot(
            500, make_modal_handler(qtbot, QFileDialog, handle_dialog_select_file)
        )
        QTest.mouseClick(plugin.rana_browser.files_browser.btn_upload, Qt.LeftButton)

    # Wait for the load-layer message box to be dismissed before proceeding
    qtbot.waitUntil(
        lambda: not isinstance(
            QApplication.activeModalWidget() or QApplication.activeWindow(),
            QMessageBox,
        ),
        timeout=30000,
    )

    # Wait for file detail view to be shown after upload
    qtbot.waitUntil(
        lambda: plugin.rana_browser.rana_files.currentIndex() == 1,
        timeout=30000,
    )

    # Navigate back to file list view by clicking the folder breadcrumb
    breadcrumbs = plugin.rana_browser.files_breadcrumbs
    breadcrumbs.on_click(1)  # index 1 is the project root folder
    qtbot.waitUntil(
        lambda: plugin.rana_browser.rana_files.currentIndex() == 0,
        timeout=10000,
    )
    assert plugin.rana_browser.rana_files.currentIndex() == 0

    # Toggle select mode
    files_browser = plugin.rana_browser.files_browser
    QTest.mouseClick(files_browser.select_btn, Qt.LeftButton)
    qtbot.waitUntil(lambda: files_browser.select_btn.isChecked(), timeout=5000)

    # Select all files by clicking each checkbox
    _click_all_checkboxes(files_browser, qtbot)

    # Download selected file
    assert files_browser.btn_download_selected.isEnabled()

    def dismiss_download_msg(qtbot, modal):
        qtbot.keyClick(modal, Qt.Key.Key_Enter)

    with qtbot.waitSignal(plugin.loader.file_download_finished, timeout=30000):
        QTimer.singleShot(
            500, make_modal_handler(qtbot, QMessageBox, dismiss_download_msg)
        )
        QTest.mouseClick(files_browser.btn_download_selected, Qt.LeftButton)

    QTest.qWait(500)
    local_path = get_local_file_path(plugin.rana_browser.project["slug"], "upload.gpkg")
    assert os.path.exists(local_path), f"Downloaded file not found at {local_path}"

    # Toggle select mode off and on to clear all checkboxes
    QTest.mouseClick(files_browser.select_btn, Qt.LeftButton)
    qtbot.waitUntil(lambda: not files_browser.select_btn.isChecked(), timeout=5000)
    QTest.mouseClick(files_browser.select_btn, Qt.LeftButton)
    qtbot.waitUntil(lambda: files_browser.select_btn.isChecked(), timeout=5000)

    # Verify all checkboxes are unchecked
    for row in range(files_browser.files_model.rowCount()):
        item = files_browser.files_model.item(row, 0)
        if item and item.isCheckable():
            assert item.checkState() == Qt.CheckState.Unchecked

    # Select all files for delete by clicking each checkbox
    _click_all_checkboxes(files_browser, qtbot)
    QTest.qWait(500)

    def confirm_delete(qtbot, modal):
        yes_button = modal.button(QMessageBox.StandardButton.Yes)
        if yes_button:
            QTest.mouseClick(yes_button, Qt.LeftButton)

    QTimer.singleShot(500, make_modal_handler(qtbot, QMessageBox, confirm_delete))
    QTest.mouseClick(files_browser.btn_delete_selected, Qt.LeftButton)
    QTest.qWait(1000)

    # Verify file is gone from the list
    assert _find_file_row(files_browser, "upload.gpkg") is None, (
        "upload.gpkg should have been deleted from the file list"
    )


def test_upload_case_conflict(plugin, qtbot, request, rana_project):
    """Uploading a file whose name matches an existing server file case-insensitively
    should warn the user and not complete the upload."""
    plugin.iface.mainWindow().setWindowTitle(request.node.nodeid)
    _open_project(plugin, qtbot, rana_project)

    # Phase 1: upload upload.gpkg to establish a server-side file.
    # Dismiss the "load layer?" prompt with Escape to avoid opening the file in the plugin.
    def dismiss_load_layer(qtbot, modal):
        qtbot.keyClick(modal, Qt.Key.Key_Escape)

    QTimer.singleShot(500, make_modal_handler(qtbot, QMessageBox, dismiss_load_layer))

    with qtbot.waitSignal(plugin.loader.file_upload_finished, timeout=30000):

        def handle_dialog_select_upload(qtbot, modal):
            QTest.qWait(500)
            modal.selectFile("upload.gpkg")
            QTest.qWait(500)
            qtbot.keyClick(modal, Qt.Key.Key_Enter)

        QTimer.singleShot(
            500, make_modal_handler(qtbot, QFileDialog, handle_dialog_select_upload)
        )
        QTest.mouseClick(plugin.rana_browser.files_browser.btn_upload, Qt.LeftButton)

    # Phase 2: attempt to upload Upload.gpkg (case-variant of the file already on the server).
    # The API should reject it with a 400; the plugin should emit file_upload_failed
    # and show a warning rather than completing the upload.
    original_file = Path(__file__).parent.resolve().joinpath("data", "upload.gpkg")
    case_dup_file = Path(__file__).parent.resolve().joinpath("data", "Upload.gpkg")
    if not case_dup_file.exists():
        shutil.copy(original_file, case_dup_file)

    error_shown = []

    def dismiss_error(qtbot, modal):
        error_shown.append(modal.text())
        qtbot.keyClick(modal, Qt.Key.Key_Enter)

    QTimer.singleShot(500, make_modal_handler(qtbot, QMessageBox, dismiss_error))

    with qtbot.waitSignal(plugin.loader.file_upload_failed, timeout=15000):

        def handle_dialog_select_case_variant(qtbot, modal):
            QTest.qWait(500)
            modal.selectFile("Upload.gpkg")
            QTest.qWait(500)
            qtbot.keyClick(modal, Qt.Key.Key_Enter)

        QTimer.singleShot(
            500,
            make_modal_handler(qtbot, QFileDialog, handle_dialog_select_case_variant),
        )
        QTest.mouseClick(plugin.rana_browser.files_browser.btn_upload, Qt.LeftButton)

    # An error dialog must have been shown mentioning case sensitivity.
    assert error_shown, "Expected an error dialog to appear for the case-conflict"

    # The case-variant must not appear as a new file in the browser.
    assert _find_file_row(plugin.rana_browser.files_browser, "Upload.gpkg") is None, (
        "Upload.gpkg should not have been uploaded to the server"
    )
    # The original file must still be present.
    assert (
        _find_file_row(plugin.rana_browser.files_browser, "upload.gpkg") is not None
    ), "upload.gpkg should still be present on the server"
    case_dup_file.unlink()
