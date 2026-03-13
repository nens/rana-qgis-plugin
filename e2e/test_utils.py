from qgis.core import QgsMapRendererParallelJob
from qgis.PyQt.QtCore import QSize, Qt
from qgis.PyQt.QtGui import QImage
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


def canvas_to_image(canvas) -> QImage:
    """Renders the QgsMapCanvas to a QImage and returns it. Useful for pixelperfect assertions."""
    settings = canvas.mapSettings()
    settings.setFlag(settings.Antialiasing, False)
    settings.setFlag(settings.UseAdvancedEffects, False)

    width = canvas.size().width()
    height = canvas.size().height()
    settings.setOutputSize(QSize(width, height))
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
