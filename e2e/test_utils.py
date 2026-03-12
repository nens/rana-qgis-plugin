from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtTest import QTest
from qgis.PyQt.QtWidgets import QTreeView


def click_tree_item(tree: QTreeView, index, qtbot):
    """Click on a specific position in a QTreeView item, ensuring it is visible and focused."""
    # Ensure item is visible
    qtbot.waitExposed(tree)
    tree.setFocus()
    tree.scrollTo(index)

    # Get item rectangle
    rect = tree.visualRect(index)
    assert rect.isValid()

    with qtbot.waitSignal(tree.doubleClicked):
        # Note that we require two consecutive double clicks to ensure it is registered as a double click
        qtbot.mouseDClick(tree.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())
        QTest.qWait(50)
        qtbot.mouseDClick(tree.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())


def press_button_with_moderator(qtbot, modal, key, moderator_key=Qt.Key_Shift):
    """Click the moderator and target key. Useful for navigating dialogs with
    keyboard shortcuts that require a modifier key, such as Shift+Tab."""
    # Note that Qt only picks up a key_moderator combination when there is a small pause between
    # press and release.
    qtbot.keyPress(modal, moderator_key)
    qtbot.keyPress(modal, key)
    QTest.qWait(100)
    qtbot.keyRelease(modal, key)
    qtbot.keyRelease(modal, moderator_key)
