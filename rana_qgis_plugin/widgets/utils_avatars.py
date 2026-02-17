from qgis.PyQt.QtCore import (
    QObject,
    QRectF,
    QRunnable,
    Qt,
    QThreadPool,
    pyqtSignal,
)
from qgis.PyQt.QtGui import QPainter, QPainterPath, QPixmap
from qgis.PyQt.QtWidgets import QApplication

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
