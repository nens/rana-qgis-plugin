from qgis.PyQt.QtCore import Qt, QTimer
from qgis.PyQt.QtTest import QTest
from qgis.PyQt.QtWidgets import QApplication, QFileDialog, QMessageBox, QTreeView


def click_tree_item(tree: QTreeView, index, qtbot):
    # Ensure item is visible
    qtbot.waitExposed(tree)
    tree.setFocus()
    tree.scrollTo(index)

    # Get item rectangle
    rect = tree.visualRect(index)
    assert rect.isValid()

    with qtbot.waitSignal(tree.doubleClicked):
        qtbot.mouseDClick(tree.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())
        QTest.qWait(50)
        qtbot.mouseDClick(tree.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())


def test_smoke(plugin, request):
    plugin.iface.mainWindow().setWindowTitle(request.node.nodeid)
    rana_tool_button = plugin.toolbar.widgetForAction(plugin.action)
    QTest.qWait(1000)
    QTest.mouseClick(rana_tool_button, Qt.LeftButton)
    QTest.qWait(1000)
    assert plugin.rana_browser.projects_browser.projects_tv.model().rowCount() == 1


def test_upload(plugin, qtbot, request):
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

    assert True

    # TODO
    # assert not plugin.rana_browser.files_browser.isVisible()

    def handle_dialog2():
        modal = QApplication.activeModalWidget()
        assert isinstance(modal, QMessageBox)
        modal.setFocus()
        # QTest.qWait(1000)
        qtbot.keyPress(modal, Qt.Key_Shift)
        qtbot.keyPress(modal, Qt.Key_Tab)
        QTest.qWait(100)
        qtbot.keyRelease(modal, Qt.Key_Tab)
        qtbot.keyRelease(modal, Qt.Key_Shift)
        # QTest.qWait(1000)
        qtbot.keyClick(modal, Qt.Key.Key_Enter)

    QTimer.singleShot(8000, handle_dialog2)

    with qtbot.waitSignal(plugin.loader.file_upload_finished):

        def handle_dialog():
            modal = QApplication.activeModalWidget()
            assert isinstance(modal, QFileDialog)
            # QTest.qWait(1000)
            modal.setFocus()
            modal.selectFile("upload.gpkg")  # Clear any selected file
            # QTest.qWait(1000)
            qtbot.keyClick(modal, Qt.Key.Key_Enter)

        QTimer.singleShot(2000, handle_dialog)
        QTest.mouseClick(plugin.rana_browser.files_browser.btn_upload, Qt.LeftButton)

    QTest.qWait(10000)

    # Check whether File view is visible and contains the uploaded file
    # TODO
    # assert plugin.rana_browser.files_browser.isVisible()

    # Check whether the map layer was added to the canvas
    assert any(
        "upload.gpkg" in layer.name() for layer in plugin.iface.mapCanvas().layers()
    )
