from qgis.PyQt.QtCore import Qt, QTimer
from qgis.PyQt.QtTest import QTest
from qgis.PyQt.QtWidgets import QApplication, QFileDialog, QTreeView


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


def test_smoke(plugin):
    rana_tool_button = plugin.toolbar.widgetForAction(plugin.action)
    QTest.qWait(1000)
    QTest.mouseClick(rana_tool_button, Qt.LeftButton)
    QTest.qWait(1000)
    assert plugin.rana_browser.projects_browser.projects_tv.model().rowCount() == 1


def test_upload(plugin, qtbot):
    rana_tool_button = plugin.toolbar.widgetForAction(plugin.action)
    QTest.mouseClick(rana_tool_button, Qt.LeftButton)

    # Select the one and only project
    click_tree_item(
        plugin.rana_browser.projects_browser.projects_tv,
        plugin.rana_browser.projects_browser.projects_tv.model().index(0, 0),
        qtbot,
    )
    QTest.qWait(2000)

    def handle_dialog():
        # Get the active modal widget
        modal = QApplication.activeModalWidget()
        assert isinstance(modal, QFileDialog)
        print("Dialog opened successfully")
        QTest.qWait(1000)
        # Close the dialog
        modal.setFocus()  # Ensure the file dialog has focus
        modal.selectFile("upload.gpkg")  # Clear any selected file
        QTest.qWait(2000)
        qtbot.keyClick(modal, Qt.Key.Key_Enter)

    QTimer.singleShot(1000, handle_dialog)
    QTest.mouseClick(plugin.rana_browser.files_browser.btn_upload, Qt.LeftButton)
    QTest.qWait(2000)

    assert False
