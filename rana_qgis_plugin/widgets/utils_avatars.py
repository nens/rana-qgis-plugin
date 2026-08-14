from qgis.PyQt.QtCore import (
    QObject,
    QRectF,
    Qt,
    pyqtSignal,
)
from qgis.PyQt.QtGui import QImage, QPainter, QPainterPath, QPixmap
from qgis.PyQt.QtWidgets import QApplication

from rana_qgis_plugin.utils.api import get_user_image


def get_user_image_from_initials(initials: str) -> QPixmap:
    # Ensure initials are capitalized and within two characters
    initials = initials.upper()

    size = 32  # Size of the icon
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Determine colors based on theme
    theme_background_color = QApplication.palette().window().color()
    theme_text_color = QApplication.palette().text().color()

    # Draw circular background
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(theme_background_color)
    painter.setPen(theme_text_color)
    painter.drawEllipse(QRectF(0, 0, size, size))

    # Draw initials
    text_rect = QRectF(0, 0, size, size)
    painter.setPen(theme_text_color)
    font = painter.font()
    font.setPointSize(14)
    painter.setFont(font)
    painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, initials)

    painter.end()

    return pixmap


def create_user_image(image):
    size = 32
    pixmap = QPixmap.fromImage(image)
    # Scale maintaining aspect ratio
    scaled_pixmap = pixmap.scaled(
        size,
        size,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )

    # Calculate offsets to center the image
    x_offset = max(0, (scaled_pixmap.width() - size) // 2)
    y_offset = max(0, (scaled_pixmap.height() - size) // 2)

    # Create the target rounded pixmap
    rounded = QPixmap(size, size)
    rounded.fill(Qt.GlobalColor.transparent)

    # Create a path for circular mask
    path = QPainterPath()
    path.addEllipse(QRectF(0, 0, size, size))

    # Paint the original pixmap with circular mask
    painter = QPainter(rounded)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setClipPath(path)

    # Draw the pixmap from the calculated offset position
    painter.drawPixmap(
        0,
        0,
        size,
        size,  # target rectangle
        scaled_pixmap,  # source pixmap
        x_offset,
        y_offset,  # source position
        size,
        size,  # source size
    )
    painter.end()

    return rounded


def get_avatar(user, try_remote=True, create_from_initials=True) -> QPixmap:
    if not user:
        try_remote = False
        user = {}
    final_pixmap = None
    if try_remote:
        bin_image = get_user_image(user["id"])
        if bin_image:
            final_pixmap = create_user_image(bin_image)
    if not final_pixmap and create_from_initials:
        initials = (user.get("given_name", "?")[0]) + (user.get("family_name", "?")[0])
        final_pixmap = get_user_image_from_initials(initials)
    return final_pixmap


class AvatarCache(QObject):
    # Avatar session cache
    avatar_changed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.cache: dict[str, QPixmap] = {}

    def get_avatar_from_cache(self, user_id: str) -> QPixmap | None:
        return self.cache.get(user_id, None)

    def get_avatar_for_user(self, user: dict) -> QPixmap:
        if user["id"] not in self.cache:
            self.cache[user["id"]] = get_avatar(user, try_remote=False)
        return self.cache[user["id"]]

    def update_avatar(self, user_id: str, image: QImage):
        """Convert a QImage to a circular QPixmap and update the cache.

        The conversion to QPixmap must happen on the main thread.
        """
        if not image or image.isNull():
            return
        new_avatar = create_user_image(image)
        current_avatar = self.cache.get(user_id, None)
        if current_avatar and not current_avatar.isNull():
            if new_avatar.toImage() == current_avatar.toImage():
                return
        self.cache[user_id] = new_avatar
        self.avatar_changed.emit(user_id)
