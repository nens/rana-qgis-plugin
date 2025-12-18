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


def get_user_image_from_initials(initials: str):
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
    painter.setBrush(theme_background_color)
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(QRectF(0, 0, size, size))

    # Draw initials
    text_rect = QRectF(0, 0, size, size)
    painter.setPen(theme_text_color)
    font = painter.font()
    font.setPointSize(12)
    painter.setFont(font)
    painter.drawText(text_rect, Qt.AlignCenter, initials)

    painter.end()

    return pixmap


def create_user_image(image):
    size = 32
    pixmap = QPixmap.fromImage(image)
    # rounded = QPixmap(size, size)
    # rounded.fill(Qt.transparent)
    #
    # # Create a path for circular mask
    # path = QPainterPath()
    # path.addEllipse(QRectF(0, 0, size, size))
    #
    # # Paint the original pixmap with circular mask
    # painter = QPainter(rounded)
    # painter.setRenderHint(QPainter.Antialiasing)
    # painter.setClipPath(path)
    # painter.drawPixmap(
    #     0,
    #     0,
    #     pixmap.scaled(
    #         size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
    #     ),
    # )
    # painter.end()
    return pixmap.scaled(32, 32)
