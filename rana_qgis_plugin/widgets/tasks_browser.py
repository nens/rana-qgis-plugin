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
    QProgressBar,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from rana_qgis_plugin.utils import get_timestamp_as_numeric_item
from rana_qgis_plugin.utils_api import get_user_by_email


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

    def __init__(self, communication, parent=None):
        # TODO
        # - filter
        # - pagination
        # - only populate on opening
        # - avatars (waiting for prs)
        super().__init__(parent)
        self.communication = communication
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

    def add_task(self, task, root, row_map):
        name_item = QStandardItem(task.name)
        # TODO: link to rana user and show icon - wait for open PRs
        user = get_user_by_email(task.user_email)
        user_str = f"{user['given_name'][0]}{user['family_name'][0]}" if user else "?"
        who_item = QStandardItem(user_str)
        date_item = get_timestamp_as_numeric_item(task.created)
        status_item = QStandardItem()
        status_item.setData(task.status, Qt.ItemDataRole.UserRole)
        # Create the progress bar
        progress_bar = QProgressBar()
        self.update_pb_progress(progress_bar, task)
        progress_bar.setTextVisible(True)
        row = [name_item, who_item, date_item, status_item]
        root.appendRow(row)
        self.tasks_tv.setIndexWidget(status_item.index(), progress_bar)
        row_map[task.id] = root.rowCount() - 1

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
