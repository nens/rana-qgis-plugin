from qgis.core import QgsApplication
from qgis.PyQt.QtCore import QRectF, QSize, Qt
from qgis.PyQt.QtGui import (
    QPainter,
    QPainterPath,
    QPixmap,
)
from qgis.PyQt.QtWidgets import QApplication, QLabel


def get_icon_from_theme(icon_name: str) -> QPixmap:
    return QgsApplication.getThemeIcon(icon_name).pixmap(QSize(32, 32))


def get_icon_label(icon: QPixmap) -> QLabel:
    icon_label = QLabel()
    icon_label.setPixmap(icon)
    return icon_label


def get_user_image_from_initials(initials: str) -> QPixmap:
    # Ensure initials are capitalized and within two characters
    initials = initials.upper()

    size = 32  # Size of the icon
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    # Determine colors based on theme
    theme_background_color = Qt.transparent
    theme_text_color = QApplication.palette().text().color()

    # Draw circular background
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(theme_background_color)
    painter.setPen(theme_text_color)
    painter.drawEllipse(QRectF(0, 0, size, size))

    # Draw initials
    text_rect = QRectF(0, 0, size, size)
    painter.setPen(theme_text_color)
    font = painter.font()
    font.setPointSize(14)
    painter.setFont(font)
    painter.drawText(text_rect, Qt.AlignCenter, initials)

    painter.end()

    return pixmap


def create_user_image(image):
    size = 32
    pixmap = QPixmap.fromImage(image)
    # Scale maintaining aspect ratio
    scaled_pixmap = pixmap.scaled(
        size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
    )

    # Calculate offsets to center the image
    x_offset = max(0, (scaled_pixmap.width() - size) // 2)
    y_offset = max(0, (scaled_pixmap.height() - size) // 2)

    # Create the target rounded pixmap
    rounded = QPixmap(size, size)
    rounded.fill(Qt.transparent)

    # Create a path for circular mask
    path = QPainterPath()
    path.addEllipse(QRectF(0, 0, size, size))

    # Paint the original pixmap with circular mask
    painter = QPainter(rounded)
    painter.setRenderHint(QPainter.Antialiasing)
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
