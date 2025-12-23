import hashlib
import time
from pathlib import Path

from qgis.core import QgsApplication
from qgis.PyQt.QtCore import QBuffer, QByteArray, QPoint, QRect, QRectF, QSize, Qt
from qgis.PyQt.QtGui import QImage, QPainter, QPainterPath, QPixmap
from qgis.PyQt.QtWidgets import QApplication, QLabel, QStyledItemDelegate, QToolTip

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
    theme_background_color = QApplication.palette().window().color()
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


class ContributorAvatarsDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.avatar_size = 24
        self.max_avatars = 3

    def paint(self, painter: QPainter, option, index):
        contributors = index.data(Qt.ItemDataRole.UserRole)
        if not contributors:
            return

        # Calculate number of remaining contributors
        remaining = max(len(contributors) - self.max_avatars, 0)
        # Only show first 3 avatars
        visible_contributors = contributors[: self.max_avatars]

        x = option.rect.x() + (len(visible_contributors) - 1) * (self.avatar_size) // 2
        y = option.rect.y() + (option.rect.height() - self.avatar_size) // 2

        # Draw avatars
        for contributor in visible_contributors[::-1]:
            avatar = contributor.get("avatar")
            if avatar and not avatar.isNull():
                scaled_avatar = avatar.scaled(
                    self.avatar_size,
                    self.avatar_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                point = QPoint(x, y)
                painter.drawPixmap(point, scaled_avatar)
                x -= self.avatar_size // 2

        # Draw +m if there are remaining contributors
        if remaining > 0:
            painter.save()
            remaining_text = f"+{remaining}"
            # Position text after the last avatar
            text_x = option.rect.x() + 2 * self.avatar_size

            # Set up text style
            font = painter.font()
            font.setBold(True)
            painter.setFont(font)

            # Get font metrics to calculate vertical centering
            metrics = painter.fontMetrics()
            text_height = metrics.height()

            # Calculate y position to center the text vertically in the available space
            text_y = y + (self.avatar_size + metrics.ascent()) // 2

            # Draw the +m text
            painter.drawText(text_x, text_y, remaining_text)
            painter.restore()

    def sizeHint(self, option, index):
        contributors = index.data(Qt.ItemDataRole.UserRole)
        if not contributors:
            return QSize(0, self.avatar_size)

        visible_count = min(len(contributors), 3)
        width = self.avatar_size + (visible_count - 1) * self.avatar_size // 2

        # Add extra space for the +m text if needed
        if len(contributors) > 3:
            width += self.avatar_size  # Extra space for "+m" text

        return QSize(width, self.avatar_size)

    def helpEvent(self, event, view, option, index):
        if not event or not view:
            return False
        contributors = index.data(Qt.ItemDataRole.UserRole)
        if not contributors:
            return False

        mouse_pos = event.pos()
        radius = self.avatar_size // 2

        # Calculate the starting position (same as in paint method)
        x = option.rect.x()
        y = option.rect.y() + (option.rect.height() - self.avatar_size) // 2

        # Convert mouse position to be relative to the cell
        mouse_x = mouse_pos.x() - option.rect.x()
        mouse_y = mouse_pos.y() - option.rect.y()
        center_y = y + radius - option.rect.y()
        dy2 = (mouse_y - center_y) ** 2
        rad2 = radius**2

        # Check if mouse is over the +m text
        visible_contributors = contributors[: self.max_avatars]
        text_x = x + 2 * self.avatar_size
        if len(contributors) > self.max_avatars:
            text_rect = QRect(text_x, y, self.avatar_size, self.avatar_size)
            if text_rect.contains(mouse_pos):
                remaining = contributors[3:]
                tooltip = "Additional contributors:\n" + "\n".join(
                    c.get("name", "") for c in remaining if c.get("name")
                )
                QToolTip.showText(event.globalPos(), tooltip, view)
                return True

        # Check each visible avatar from front to back (reverse order of drawing)
        for contributor in visible_contributors:
            center_x = x + radius - option.rect.x()
            # If mouse is within the circle
            if ((mouse_x - center_x) ** 2 + dy2) <= rad2:
                name = contributor.get("name", "")
                if name:
                    QToolTip.showText(event.globalPos(), name, view)
                    return True
            # Move to next avatar position
            x += self.avatar_size // 2

        # Hide tooltip if we're not over any avatar
        QToolTip.hideText()
        return True
