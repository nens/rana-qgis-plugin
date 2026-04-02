from qgis.PyQt.QtCore import (
    QObject,
    QRunnable,
    pyqtSignal,
)
from qgis.PyQt.QtGui import QPixmap

from rana_qgis_plugin.widgets.utils_avatars import get_avatar


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
