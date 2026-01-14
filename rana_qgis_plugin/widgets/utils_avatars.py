from qgis.PyQt.QtCore import (
    QObject,
    QPoint,
    QRect,
    QRectF,
    QRunnable,
    QSize,
    Qt,
    QThreadPool,
    pyqtSignal,
)
from qgis.PyQt.QtGui import QPainter, QPainterPath, QPixmap
from qgis.PyQt.QtWidgets import QApplication, QStyledItemDelegate, QToolTip

from rana_qgis_plugin.utils_api import get_user_image


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


def get_avatar(
    user, communication, try_remote=True, create_from_initials=True
) -> QPixmap:
    final_pixmap = None
    if try_remote:
        bin_image = get_user_image(communication, user["id"])
        if bin_image:
            final_pixmap = create_user_image(bin_image)
    elif create_from_initials:
        final_pixmap = get_user_image_from_initials(
            user["given_name"][0] + user["family_name"][0]
        )
    return final_pixmap


# We need a separate signals class since QRunnable cannot have signals
class AvatarWorkerSignals(QObject):
    finished = pyqtSignal()
    avatar_ready = pyqtSignal(str, "QPixmap")


class AvatarWorker(QRunnable):
    def __init__(self, communication, users: list[dict]):
        super().__init__()
        self.communication = communication
        self.users = users
        self.signals = AvatarWorkerSignals()

    def run(self):
        for user in self.users:
            new_avatar = get_avatar(
                user, self.communication, create_from_initials=False
            )
            if new_avatar:
                self.signals.avatar_ready.emit(user["id"], new_avatar)
        self.signals.finished.emit()


class AvatarCache(QObject):
    # Avatar session cache
    avatar_changed = pyqtSignal(str)

    def __init__(self, communication):
        super().__init__()
        self.communication = communication
        self.cache: dict[str, QPixmap] = {}
        self.thread_pool = QThreadPool()

    def get_avatar_from_cache(self, user_id: str) -> QPixmap | None:
        return self.cache.get(user_id, None)

    def get_avatar_for_user(self, user: dict) -> QPixmap:
        if user["id"] not in self.cache:
            self.cache[user["id"]] = get_avatar(
                user, self.communication, try_remote=False
            )
        return self.cache[user["id"]]

    def update_users_in_thread(self, users: list[dict]):
        worker = AvatarWorker(self.communication, users)
        worker.signals.avatar_ready.connect(self._update_avatar)
        self.thread_pool.start(worker)

    def _update_avatar(self, user_id: str, new_avatar: QPixmap):
        current_avatar = self.cache.get(user_id, None)
        if not new_avatar or new_avatar.isNull():
            changed = False
        elif not current_avatar or current_avatar.isNull():
            changed = True
        elif new_avatar.toImage() == current_avatar.toImage():
            changed = False
        else:
            changed = True
        if changed:
            self.cache[user_id] = new_avatar
            self.avatar_changed.emit(user_id)


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
