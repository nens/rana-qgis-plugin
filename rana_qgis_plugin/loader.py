"""Central loader: owns background workers and the avatar cache."""

from typing import TYPE_CHECKING

from qgis.PyQt.QtCore import QObject, QThreadPool, pyqtSignal, pyqtSlot
from qgis.PyQt.QtGui import QPixmap

from rana_qgis_plugin.widgets.utils_avatars import AvatarCache
from rana_qgis_plugin.workers.avatars import AvatarWorker

if TYPE_CHECKING:
    from rana_qgis_plugin.communication import UICommunication


class Loader(QObject):
    """Signal-based orchestrator for background work.

    Widgets connect to Loader signals rather than managing threads themselves.
    Currently handles avatar fetching; designed to grow with future background tasks.
    """

    avatar_updated = pyqtSignal(str, QPixmap)

    def __init__(self, communication: "UICommunication", parent=None):
        super().__init__(parent)
        self.avatar_cache = AvatarCache(communication)
        self.avatar_cache.avatar_changed.connect(self._on_avatar_changed)
        self._communication = communication
        self._avatar_pool = QThreadPool()
        self._avatar_pool.setMaxThreadCount(1)
        self._avatar_worker: AvatarWorker | None = None

    def fetch_avatars(self, users: list[dict]) -> None:
        """Start a background fetch of real avatars for the given users."""
        if not users:
            return
        if self._avatar_worker is not None:
            self._avatar_worker.cancel()
        self._avatar_worker = AvatarWorker(self._communication, users)
        self._avatar_worker.signals.avatar_ready.connect(
            self.avatar_cache.update_avatar
        )
        self._avatar_pool.start(self._avatar_worker)

    @pyqtSlot(str)
    def _on_avatar_changed(self, user_id: str) -> None:
        avatar = self.avatar_cache.get_avatar_from_cache(user_id)
        if avatar:
            self.avatar_updated.emit(user_id, avatar)

    def shutdown(self) -> None:
        """Cancel pending work and drain the pool. Call on plugin unload."""
        if self._avatar_worker is not None:
            self._avatar_worker.cancel()
        self._avatar_pool.waitForDone(3000)
