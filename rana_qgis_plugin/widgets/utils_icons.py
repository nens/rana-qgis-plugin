import hashlib
import time
from pathlib import Path

from qgis.core import QgsApplication
from qgis.PyQt.QtCore import QBuffer, QByteArray, QRectF, QSize, Qt
from qgis.PyQt.QtGui import QImage, QPainter, QPainterPath, QPixmap
from qgis.PyQt.QtWidgets import QApplication, QLabel

from rana_qgis_plugin.constant import PLUGIN_NAME
from rana_qgis_plugin.utils_api import get_user_image


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


def get_avatar(user, communication):
    cache = ImageCache(PLUGIN_NAME)
    image_name = f"avatar_{user['id']}.bin"
    bin_image = cache.get_cached_image(image_name)
    if not bin_image:
        bin_image = get_user_image(communication, user["id"])
    if bin_image:
        cache.cache_image(image_name, bin_image)
        return create_user_image(bin_image)
    else:
        return get_user_image_from_initials(
            user["given_name"][0] + user["family_name"][0]
        )


class ImageCache:
    def __init__(self, plugin_name: str):
        # Convert QgsApplication path to Path object and create cache directory
        self.cache_dir = (
            Path(QgsApplication.qgisSettingsDirPath()) / "cache" / plugin_name
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_cached_image(self, url: str) -> Path | None:
        # Create a unique filename based on URL
        filename = hashlib.md5(url.encode()).hexdigest() + ".png"
        cache_path = self.cache_dir / filename

        if cache_path.exists():
            # Check if cache is not too old (e.g., 7 days)
            if time.time() - cache_path.stat().st_mtime < 7 * 24 * 3600:
                return cache_path

        return None

    def cache_image(self, image_name: str, image_data) -> Path:
        """Cache image data to file.

        Args:
            image_name: Name to use for the cached file
            image_data: Either bytes or QImage to cache

        Returns:
            Path to the cached file
        """
        cache_path = self.cache_dir / image_name

        if isinstance(image_data, QImage):
            # Convert QImage to bytes
            byte_array = QByteArray()
            buffer = QBuffer(byte_array)
            buffer.open(QBuffer.WriteOnly)
            image_data.save(buffer, "PNG")
            cache_path.write_bytes(byte_array.data())
        else:
            # Assume it's already bytes
            cache_path.write_bytes(image_data)

        return cache_path

    def clear_old_cache(self, max_age_days: int = 7) -> None:
        """Clear cache files older than max_age_days."""
        current_time = time.time()
        for cache_file in self.cache_dir.glob("*.png"):
            if current_time - cache_file.stat().st_mtime > max_age_days * 24 * 3600:
                cache_file.unlink(missing_ok=True)

    def get_cache_size(self) -> int:
        """Get total size of cached files in bytes."""
        return sum(f.stat().st_size for f in self.cache_dir.glob("*.png"))

    def clear_all_cache(self) -> None:
        """Remove all cached files."""
        for cache_file in self.cache_dir.glob("*.png"):
            cache_file.unlink(missing_ok=True)
