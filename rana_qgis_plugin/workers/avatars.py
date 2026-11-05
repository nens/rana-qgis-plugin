from qgis.PyQt.QtCore import (
    QObject,
    QRunnable,
    pyqtSignal,
)
from qgis.PyQt.QtGui import QImage

from rana_qgis_plugin.utils.api import get_user_image


# We need a separate signals class since QRunnable cannot have signals
class AvatarWorkerSignals(QObject):
    finished = pyqtSignal(object)
    avatar_ready = pyqtSignal(str, QImage)
    avatar_failed = pyqtSignal(str, str)


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
            user_id = user["id"]
            try:
                image = get_user_image(user_id)
                if image is None:
                    continue
                if image.isNull():
                    raise ValueError("Received an invalid user image")
                self.signals.avatar_ready.emit(user_id, image)
            except Exception as error:
                self.signals.avatar_failed.emit(user_id, str(error))
        self.signals.finished.emit(self)
