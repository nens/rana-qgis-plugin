import os

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
from rana_qgis_plugin.utils.generic import get_local_file_path


def _open_project(plugin, qtbot):
    """Open the Rana browser and select the first project."""
    rana_tool_button = plugin.toolbar.widgetForAction(plugin.action)
    QTest.mouseClick(rana_tool_button, Qt.LeftButton)
    qtbot.waitUntil(
        lambda: plugin.rana_browser.projects_browser.projects_tv.model().rowCount() > 0,
        timeout=30000,
    )
    click_tree_item(
        plugin.rana_browser.projects_browser.projects_tv,
        plugin.rana_browser.projects_browser.projects_tv.model().index(0, 0),
        qtbot,
    )
    qtbot.waitUntil(
        lambda: plugin.rana_browser.rana_files.currentIndex() == 0,
        timeout=30000,
    )


def _find_file_row(files_browser, filename):
    """Return the row index of a file by name, or None if not found."""
    for row in range(files_browser.files_model.rowCount()):
        name_item = files_browser.files_model.item(row, 1)
        if name_item:
            file_data = name_item.data(Qt.ItemDataRole.UserRole)
            if file_data and file_data.get("id") == filename:
                return row
    return None


def test_smoke(plugin, qtbot, request):
    plugin.iface.mainWindow().setWindowTitle(request.node.nodeid)
    _open_project(plugin, qtbot)
    assert plugin.rana_browser.projects_browser.projects_tv.model().rowCount() == 1


def test_upload(plugin, qtbot, request, clean_upload_file):
    plugin.iface.mainWindow().setWindowTitle(request.node.nodeid)
    _open_project(plugin, qtbot)

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
        "/root/Rana/plugin-test/files/upload/upload.gpkg"
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


def test_select_download_and_delete(plugin, qtbot, request, clean_upload_file):
    """Upload a file, then use select mode to download and delete it."""
    plugin.iface.mainWindow().setWindowTitle(request.node.nodeid)
    _open_project(plugin, qtbot)

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

    # Navigate back to file list view
    plugin.rana_browser.rana_files.setCurrentIndex(0)
    qtbot.waitUntil(
        lambda: plugin.rana_browser.rana_files.currentIndex() == 0,
        timeout=10000,
    )

    # Toggle select mode
    files_browser = plugin.rana_browser.files_browser
    QTest.mouseClick(files_browser.select_btn, Qt.LeftButton)
    qtbot.waitUntil(lambda: files_browser.select_btn.isChecked(), timeout=5000)

    # Find and select the uploaded file
    file_row = _find_file_row(files_browser, "upload.gpkg")
    assert file_row is not None, "upload.gpkg not found in file list"
    files_browser.files_model.item(file_row, 0).setCheckState(Qt.CheckState.Checked)

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

    # Re-select for delete
    files_browser.files_model.item(file_row, 0).setCheckState(Qt.CheckState.Checked)
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
