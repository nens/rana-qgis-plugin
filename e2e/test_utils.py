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
