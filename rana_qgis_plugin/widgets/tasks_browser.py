from dataclasses import dataclass

from qgis.PyQt.QtCore import (
    Qt,
    QTimer,
    pyqtSignal,
)
from qgis.PyQt.QtGui import (
    QStandardItem,
    QStandardItemModel,
)
from qgis.PyQt.QtWidgets import (
    QHeaderView,
    QProgressBar,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from rana_qgis_plugin.utils import get_timestamp_as_numeric_item
from rana_qgis_plugin.utils_api import get_user_by_email
from rana_qgis_plugin.widgets.utils_avatars import (
    ContributorAvatarsDelegate,
    get_user_image_from_initials,
)


@dataclass
class TaskData:
    id: int
    name: str
    user_email: str
    created: str
    status: str
    progress: int
    max_progress: int

    def progress_str(self):
        raise NotImplementedError


@dataclass
class SimulationTaskData(TaskData):
    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            id=data["uid"],
            name=data["name"],
            user_email=data["user_name"],
            created=data["date_created"],
            status=data["status"],
            progress=int(data["progress"]),
            max_progress=100,
        )

    def progress_str(self):
        return f"{self.status} ({self.progress}%)"


@dataclass
class ModelTaskData(TaskData):
    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            id=data["id"],
            name=data["name"],
            user_email=data["user_email"],
            created=data["created"],
            status=data["status"],
            progress=int(data["finished_tasks"]),
            max_progress=int(data["total_tasks"]),
        )

    def progress_str(self):
        return f"{self.status} ({self.progress} of {self.max_progress})"


class TasksBrowser(QWidget):
    start_monitoring_simulations = pyqtSignal()
    start_monitoring_model_generation = pyqtSignal()

    def __init__(self, communication, avatar_cache, parent=None):
        # TODO
        # - filter
        # - pagination
        # - only populate on opening
        super().__init__(parent)
        self.communication = communication
        self.avatar_cache = avatar_cache
        self.tasks = []
        self.setup_ui()
        self.simulation_row_map = {}
        self.model_row_map = {}
        QTimer.singleShot(0, lambda: self.start_monitoring_simulations.emit())
        QTimer.singleShot(0, lambda: self.start_monitoring_model_generation.emit())

    def setup_ui(self):
        # TODO: consider using a custom model
        self.tasks_model = QStandardItemModel()
        self.tasks_tv = QTreeView()
        self.tasks_tv.setModel(self.tasks_model)
        self.tasks_tv.setEditTriggers(QTreeView.NoEditTriggers)
        layout = QVBoxLayout(self)
        layout.addWidget(self.tasks_tv)
        self.setLayout(layout)
        # create root items, they will be added on populating
        self.tasks_model.setHorizontalHeaderLabels(["Name", "Who", "Started", "Status"])

        self.simulation_root = QStandardItem("Simulations")
        self.models_root = QStandardItem("Models")
        self.tasks_model.appendRow([self.simulation_root])
        self.tasks_model.appendRow([self.models_root])
        self.tasks_tv.expandAll()
        avatar_delegate = ContributorAvatarsDelegate(self.tasks_tv)
        self.tasks_tv.setItemDelegateForColumn(1, avatar_delegate)
        # TODO: handle this better!
        self.tasks_tv.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tasks_tv.header().setSectionResizeMode(1, QHeaderView.Fixed)
        self.tasks_tv.header().setSectionResizeMode(2, QHeaderView.Fixed)
        self.tasks_tv.header().setSectionResizeMode(3, QHeaderView.Fixed)
        self.tasks_tv.setColumnWidth(1, 50)
        self.tasks_tv.setColumnWidth(2, 100)
        self.tasks_tv.setColumnWidth(3, 10)

    def add_task(self, task, root, row_map):
        name_item = QStandardItem(task.name)
        user = get_user_by_email(task.user_email)
        if user:
            user_data = [
                {
                    "id": user["id"],
                    "name": user["given_name"] + " " + user["family_name"],
                    "avatar": self.avatar_cache.get_avatar_for_user(user),
                }
            ]
        else:
            user_data = [
                {
                    "id": None,
                    "name": "unknown user",
                    "avatar": get_user_image_from_initials("?"),
                }
            ]
        who_item = QStandardItem()
        who_item.setData(user_data, Qt.ItemDataRole.UserRole)
        date_item = get_timestamp_as_numeric_item(task.created)
        status_item = QStandardItem()
        status_item.setData(task.status, Qt.ItemDataRole.UserRole)
        # Create the progress bar
        progress_bar = QProgressBar()
        progress_bar.setFixedWidth(200)
        self.update_pb_progress(progress_bar, task)
        progress_bar.setTextVisible(True)
        row = [name_item, who_item, date_item, status_item]
        root.appendRow(row)
        self.tasks_tv.setIndexWidget(status_item.index(), progress_bar)
        row_map[task.id] = root.rowCount() - 1
        self.tasks_tv.resizeColumnToContents(0)
        self.tasks_tv.resizeColumnToContents(3)

    @staticmethod
    def update_pb_progress(progress_bar, task):
        progress_bar.setValue(task.progress)
        progress_bar.setMaximum(task.max_progress)
        progress_bar.setFormat(task.progress_str())

    def add_simulation_task(self, task_data):
        self.add_task(
            SimulationTaskData.from_dict(task_data),
            self.simulation_root,
            self.simulation_row_map,
        )

    def add_model_task(self, task_data):
        self.add_task(
            ModelTaskData.from_dict(task_data), self.models_root, self.model_row_map
        )

    def update_task(self, task, root, row_map):
        row = row_map.get(task.id, -1)
        if row < 0:
            return
        status_item = root.child(row, 3)
        status_item.setData(task.status, Qt.ItemDataRole.UserRole)
        self.update_pb_progress(self.tasks_tv.indexWidget(status_item.index()), task)

    def update_simulation_task(self, task_data):
        self.update_task(
            SimulationTaskData.from_dict(task_data),
            self.simulation_root,
            self.simulation_row_map,
        )

    def update_model_task(self, task_data):
        self.update_task(
            ModelTaskData.from_dict(task_data), self.models_root, self.model_row_map
        )
