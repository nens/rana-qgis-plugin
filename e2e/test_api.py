import os

from qgis.core import QgsApplication, QgsAuthMethodConfig
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
from rana_qgis_plugin.auth import get_authcfg_id
from rana_qgis_plugin.auth_3di import set_3di_auth
from rana_qgis_plugin.constant import PLUGIN_NAME, RANA_SETTINGS_ENTRY
from rana_qgis_plugin.utils.api import delete_tenant_project_file


def test_smoke(plugin, request):
    plugin.iface.mainWindow().setWindowTitle(request.node.nodeid)
    rana_tool_button = plugin.toolbar.widgetForAction(plugin.action)
    QTest.qWait(1000)
    QTest.mouseClick(rana_tool_button, Qt.LeftButton)
    QTest.qWait(1000)
    assert plugin.rana_browser.projects_browser.projects_tv.model().rowCount() == 1


def test_login_logout(plugin):
    """Test login via toolbar click, then logout, then login again."""
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
    logout_action.trigger()
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

    QTest.mouseClick(rana_tool_button, Qt.LeftButton)
    QTest.qWait(1000)

    # Verify logged-in state again
    menu_texts = [action.text() for action in menu.actions()]
    assert "Logout" in menu_texts
    assert "test user" in menu_texts
    assert plugin.dock_widget.isVisible()


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
