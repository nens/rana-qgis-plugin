import os

from qgis.PyQt.QtCore import Qt, QTimer
from qgis.PyQt.QtGui import QImage
from qgis.PyQt.QtTest import QTest
from qgis.PyQt.QtWidgets import QApplication, QFileDialog, QMessageBox

from e2e.test_utils import (
    canvas_to_image,
    click_tree_item,
    images_equal,
    press_button_with_moderator,
)
from rana_qgis_plugin.utils.api import delete_tenant_project_file
from rana_qgis_plugin.utils.generic import get_local_file_path


def test_smoke(plugin, request):
    plugin.iface.mainWindow().setWindowTitle(request.node.nodeid)
    rana_tool_button = plugin.toolbar.widgetForAction(plugin.action)
    QTest.qWait(1000)
    QTest.mouseClick(rana_tool_button, Qt.LeftButton)
    QTest.qWait(1000)
    assert plugin.rana_browser.projects_browser.projects_tv.model().rowCount() == 1


def test_upload(plugin, qtbot, request):
    # Delete the file from previous runs if it exists
    delete_tenant_project_file("NEEjN2HZ", {"path": "upload.gpkg"})

    plugin.iface.mainWindow().setWindowTitle(request.node.nodeid)
    rana_tool_button = plugin.toolbar.widgetForAction(plugin.action)
    QTest.mouseClick(rana_tool_button, Qt.LeftButton)
    QTest.qWait(2000)
    # Select the one and only project
    click_tree_item(
        plugin.rana_browser.projects_browser.projects_tv,
        plugin.rana_browser.projects_browser.projects_tv.model().index(0, 0),
        qtbot,
    )
    QTest.qWait(2000)

    # Check we don't start in file detail view
    assert plugin.rana_browser.rana_files.currentIndex() != 1

    def handle_dialog_load_layer():
        # Note that this might not for native widgets (in that case dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True) should be set)
        modal = QApplication.activeModalWidget()
        assert isinstance(modal, QMessageBox)
        modal.setFocus()
        QTest.qWait(1000)
        press_button_with_moderator(qtbot, modal, Qt.Key_Tab)
        QTest.qWait(1000)
        qtbot.keyClick(modal, Qt.Key.Key_Enter)

    QTimer.singleShot(10000, handle_dialog_load_layer)

    with qtbot.waitSignal(plugin.loader.file_upload_finished):

        def handle_dialog_select_file():
            modal = QApplication.activeModalWidget()
            assert isinstance(modal, QFileDialog)
            QTest.qWait(500)
            modal.setFocus()
            modal.selectFile("upload.gpkg")  # Clear any selected file
            QTest.qWait(500)
            qtbot.keyClick(modal, Qt.Key.Key_Enter)

        QTimer.singleShot(3000, handle_dialog_select_file)
        QTest.mouseClick(plugin.rana_browser.files_browser.btn_upload, Qt.LeftButton)

    QTest.qWait(13000)

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

    # Delete the file
    delete_tenant_project_file("NEEjN2HZ", {"path": "upload.gpkg"})


def test_select_download_and_delete(plugin, qtbot, request):
    """Upload a file, then use select mode to download and delete it."""
    # Delete the file from previous runs if it exists
    delete_tenant_project_file("NEEjN2HZ", {"path": "upload.gpkg"})
    # Navigate to files browser and upload a file
    plugin.iface.mainWindow().setWindowTitle(request.node.nodeid)
    rana_tool_button = plugin.toolbar.widgetForAction(plugin.action)
    QTest.mouseClick(rana_tool_button, Qt.LeftButton)
    QTest.qWait(2000)
    # Select the one and only project
    click_tree_item(
        plugin.rana_browser.projects_browser.projects_tv,
        plugin.rana_browser.projects_browser.projects_tv.model().index(0, 0),
        qtbot,
    )
    QTest.qWait(2000)

    def handle_dialog_load_layer():
        modal = QApplication.activeModalWidget()
        assert isinstance(modal, QMessageBox)
        modal.setFocus()
        QTest.qWait(1000)
        press_button_with_moderator(qtbot, modal, Qt.Key_Tab)
        QTest.qWait(1000)
        qtbot.keyClick(modal, Qt.Key.Key_Enter)

    QTimer.singleShot(10000, handle_dialog_load_layer)
    with qtbot.waitSignal(plugin.loader.file_upload_finished, timeout=30000):

        def handle_dialog_select_file():
            modal = QApplication.activeModalWidget()
            assert isinstance(modal, QFileDialog)
            QTest.qWait(500)
            modal.setFocus()
            modal.selectFile("upload.gpkg")
            QTest.qWait(500)
            qtbot.keyClick(modal, Qt.Key.Key_Enter)

        QTimer.singleShot(3000, handle_dialog_select_file)
        QTest.mouseClick(plugin.rana_browser.files_browser.btn_upload, Qt.LeftButton)

    # Navigate back to file list view
    QTest.qWait(500)
    plugin.rana_browser.rana_files.setCurrentIndex(0)
    assert plugin.rana_browser.rana_files.currentIndex() == 0

    # Toggle select mode
    files_browser = plugin.rana_browser.files_browser
    QTest.mouseClick(files_browser.select_btn, Qt.LeftButton)
    QTest.qWait(500)
    assert files_browser.select_btn.isChecked()
    # Select file
    file_row = None
    for row in range(files_browser.files_model.rowCount()):
        name_item = files_browser.files_model.item(row, 1)
        if name_item:
            file_data = name_item.data(Qt.ItemDataRole.UserRole)
            if file_data and file_data.get("id") == "upload.gpkg":
                file_row = row
                break
    assert file_row is not None, "upload.gpkg not found in file list"
    checkbox_item = files_browser.files_model.item(file_row, 0)
    checkbox_item.setCheckState(Qt.CheckState.Checked)
    # Download selected file
    assert files_browser.btn_download_selected.isEnabled()
    with qtbot.waitSignal(plugin.loader.file_download_finished, timeout=30000):

        def handle_dialog_download_finished():
            modal = QApplication.activeWindow()
            if isinstance(modal, QMessageBox):
                modal.setFocus()
                qtbot.keyClick(modal, Qt.Key.Key_Enter)
            else:
                QTimer.singleShot(500, handle_dialog_download_finished)

        QTimer.singleShot(500, handle_dialog_download_finished)
        QTest.mouseClick(files_browser.btn_download_selected, Qt.LeftButton)
    QTest.qWait(2000)
    local_path = get_local_file_path(plugin.rana_browser.project["slug"], "upload.gpkg")
    assert os.path.exists(local_path), f"Downloaded file not found at {local_path}"
    # Delete selected file
    checkbox_item = files_browser.files_model.item(file_row, 0)
    checkbox_item.setCheckState(Qt.CheckState.Checked)
    QTest.qWait(500)

    def handle_delete_confirmation():
        modal = QApplication.activeWindow()
        if isinstance(modal, QMessageBox):
            yes_button = modal.button(QMessageBox.StandardButton.Yes)
            if yes_button:
                QTest.mouseClick(yes_button, Qt.LeftButton)
        else:
            QTimer.singleShot(500, handle_delete_confirmation)

    QTimer.singleShot(500, handle_delete_confirmation)
    QTest.mouseClick(files_browser.btn_delete_selected, Qt.LeftButton)
    QTest.qWait(1000)
    file_found = False
    for row in range(files_browser.files_model.rowCount()):
        name_item = files_browser.files_model.item(row, 1)
        if name_item:
            file_data = name_item.data(Qt.ItemDataRole.UserRole)
            if file_data and file_data.get("id") == "upload.gpkg":
                file_found = True
                break
    assert not file_found, "upload.gpkg should have been deleted from the file list"
