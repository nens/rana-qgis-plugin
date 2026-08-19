import time
from typing import Sequence

from qgis.core import QgsDataItem, QgsMapRendererParallelJob
from qgis.gui import QgsDataItemGuiContext, QgsGui
from qgis.PyQt.QtCore import QPoint, QSize, Qt, QTimer
from qgis.PyQt.QtGui import QImage
from qgis.PyQt.QtTest import QTest
from qgis.PyQt.QtWidgets import QApplication, QFileDialog, QMenu, QTreeView


def build_context_menu(
    data_item: QgsDataItem, selected_items: Sequence[QgsDataItem]
) -> QMenu:
    """Build a context menu the way the QGIS Browser panel actually does.

    Combines the legacy item.actions() entries with whatever every registered
    QgsDataItemGuiProvider.populateContextMenu() adds/removes, passing the full
    current selection along — this is what makes multi-select-aware gating
    (e.g. RanaDataItemGuiProvider) observable in tests.
    """
    menu = QMenu()
    for action in data_item.actions(menu):
        menu.addAction(action)

    context = QgsDataItemGuiContext()
    registry = QgsGui.dataItemGuiProviderRegistry()
    for provider in registry.providers() if registry is not None else []:
        provider.populateContextMenu(data_item, menu, list(selected_items), context)

    return menu


def click_context_menu_action(qtbot, data_item: QgsDataItem, action_text: str) -> None:
    """Build the context menu for a data item, show it, and click the named action.

    This mimics exactly what the QGIS Browser panel does: it calls item.actions()
    to populate a QMenu, then the user clicks an entry.
    """
    menu = build_context_menu(data_item, [data_item])

    target = next((a for a in menu.actions() if a.text() == action_text), None)
    assert target is not None, f"Action '{action_text}' not found in context menu"

    menu.show()
    qtbot.waitExposed(menu)

    action_rect = menu.actionGeometry(target)
    qtbot.mouseClick(menu, Qt.MouseButton.LeftButton, pos=action_rect.center())
    QTest.qWait(100)


def make_modal_handler(qtbot, modal_type, action, timeout=30000, poll_interval=500):
    """Create a handler that polls for an active modal and applies an action..

    Schedules itself repeatedly via QTimer until the expected modal appears or
    the timeout expires. This avoids the one-shot timing problem where the modal
    has not appeared yet when the timer fires (common on slow CI runners).

    Args:
        qtbot: The pytest-qt bot instance.
        modal_type: The expected widget class (e.g. QMessageBox, QFileDialog).
        action: A callable(qtbot, modal) that performs the dismissal.
        timeout: Maximum time in ms to keep polling (default 30000).
        poll_interval: How often to check for the modal in ms (default 500).

    Returns:
        A no-arg callable suitable for QTimer.singleShot.

    Example::

        def dismiss(qtbot, modal):
            qtbot.keyClick(modal, Qt.Key.Key_Enter)

        QTimer.singleShot(500, make_modal_handler(qtbot, QMessageBox, dismiss))
    """
    deadline = [None]

    def handler():
        if deadline[0] is None:
            deadline[0] = time.monotonic() + timeout / 1000.0

        modal = QApplication.activeModalWidget() or QApplication.activeWindow()
        if isinstance(modal, modal_type):
            modal.setFocus()
            QTest.qWait(200)
            action(qtbot, modal)
            return

        if time.monotonic() < deadline[0]:
            QTimer.singleShot(poll_interval, handler)

    return handler


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


def canvas_to_image(canvas) -> QImage:
    """Renders the QgsMapCanvas to a QImage and returns it. Useful for pixelperfect assertions."""
    settings = canvas.mapSettings()
    settings.setFlag(settings.Antialiasing, False)
    settings.setFlag(settings.UseAdvancedEffects, False)

    settings.setOutputSize(QSize(800, 600))
    settings.setDevicePixelRatio(1)

    job = QgsMapRendererParallelJob(settings)
    job.start()
    job.waitForFinished()

    return job.renderedImage().convertToFormat(QImage.Format_ARGB32)


def images_equal(img1: QImage, img2: QImage) -> bool:
    if img1.size() != img2.size() or img1.format() != img2.format():
        print(
            f"Image size or format mismatch: {img1.size()} != {img2.size()} or {img1.format()} != {img2.format()}"
        )
        return False

    width = img1.width()
    height = img1.height()

    for y in range(height):
        for x in range(width):
            if img1.pixel(x, y) != img2.pixel(x, y):
                print(
                    f"Pixel mismatch at ({x}, {y}): {img1.pixel(x, y)} != {img2.pixel(x, y)}"
                )
                return False
    return True


# def press_button_with_moderator(qtbot, modal, key, moderator_key=Qt.Key_Shift):
#     """Click the moderator and target key. Useful for navigating dialogs with
#     keyboard shortcuts that require a modifier key, such as Shift+Tab."""
#     # Note that Qt only picks up a key_moderator combination when there is a small pause between
#     # press and release.
#     qtbot.keyPress(modal, moderator_key)
#     qtbot.keyPress(modal, key)
#     QTest.qWait(100)
#     qtbot.keyRelease(modal, key)
#     qtbot.keyRelease(modal, moderator_key)
