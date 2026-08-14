from qgis.PyQt.QtCore import (
    QObject,
    QRunnable,
    pyqtSignal,
)
from qgis.PyQt.QtGui import QImage

from rana_qgis_plugin.utils.api import get_user_image


# We need a separate signals class since QRunnable cannot have signals
class AvatarWorkerSignals(QObject):
    finished = pyqtSignal()
    avatar_ready = pyqtSignal(str, QImage)


class AvatarWorker(QRunnable):
    def __init__(self, communication, users: list[dict]):
        super().__init__()
        self.communication = communication
        self.users = users
        self.signals = AvatarWorkerSignals()
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        for user in self.users:
            if self._cancelled:
                break
            image = get_user_image(user["id"])
            if image and not image.isNull():
                self.signals.avatar_ready.emit(user["id"], image)
        self.signals.finished.emit()
