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
        # TODO: use a more elegant solution, like a model
        self.simulation_row_map = {}
        self.model_row_map = {}
        QTimer.singleShot(0, lambda: self.start_monitoring_simulations.emit())
        QTimer.singleShot(0, lambda: self.start_monitoring_model_generation.emit())
        # self.populate_tasks()

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

    def update_simulation_task(self, task_data):
        row = self.simulation_row_map.get(task_data["uid"])
        if not row:
            return
        status_item = self.simulation_root.child(row, 3)
        status_item.setData(task_data["status"], Qt.ItemDataRole.UserRole)
        progress_bar = self.tasks_tv.indexWidget(status_item.index())
        progress = int(task_data["progress"])
        progress_bar.setValue(progress)
        progress_bar.setFormat(f"{task_data['status']} ({progress}%)")

    def add_simulation_task(self, task_data):
        root = self.simulation_root
        name_item = QStandardItem(task_data["name"])
        # TODO: link to rana user and show icon - wait for open PRs
        user = get_user_by_email(task_data["user_name"])
        user_str = f"{user['given_name'][0]}{user['family_name'][0]}" if user else "?"
        who_item = QStandardItem(user_str)
        date_item = get_timestamp_as_numeric_item(task_data["date_created"])
        status_item = QStandardItem()
        status_item.setData(task_data["status"], Qt.ItemDataRole.UserRole)
        # Create the progress bar
        progress_bar = QProgressBar()
        progress_bar.setValue(int(task_data["progress"]))
        progress_bar.setMaximum(100)
        progress_bar.setFormat(f"{task_data['status']} ({int(task_data['progress'])}%)")
        progress_bar.setTextVisible(True)
        row = [name_item, who_item, date_item, status_item]
        root.appendRow(row)
        self.tasks_tv.setIndexWidget(status_item.index(), progress_bar)
        self.simulation_row_map[task_data["uid"]] = root.rowCount() - 1

    def add_model_task(self, task_data):
        root = self.models_root
        name_item = QStandardItem(task_data["name"])
        # TODO: link to rana user and show icon - wait for open PRs
        user = get_user_by_email(task_data["user_email"])
        user_str = f"{user['given_name'][0]}{user['family_name'][0]}" if user else "?"
        who_item = QStandardItem(user_str)
        date_item = get_timestamp_as_numeric_item(task_data["created"])
        status_item = QStandardItem()
        status_item.setData(task_data["status"], Qt.ItemDataRole.UserRole)
        # Create the progress bar
        progress_bar = QProgressBar()
        progress_bar.setValue(int(task_data["finished_tasks"]))
        progress_bar.setMaximum(int(task_data["total_tasks"]))
        progress_bar.setFormat(
            f"{task_data['status']} ({progress_bar.value()} of {progress_bar.maximum()})"
        )
        progress_bar.setTextVisible(True)
        row = [name_item, who_item, date_item, status_item]
        root.appendRow(row)
        self.tasks_tv.setIndexWidget(status_item.index(), progress_bar)
        self.model_row_map[task_data["id"]] = root.rowCount() - 1

    def update_model_task(self, task_data):
        row = self.model_row_map.get(task_data["id"], -1)
        if row < 0:
            return
        status_item = self.models_root.child(row, 3)
        status_item.setData(task_data["status"], Qt.ItemDataRole.UserRole)
        progress_bar = self.tasks_tv.indexWidget(status_item.index())
        progress_bar.setValue(int(task_data["finished_tasks"]))
        progress_bar.setMaximum(int(task_data["total_tasks"]))
        progress_bar.setFormat(
            f"{task_data['status']} ({progress_bar.value()} of {progress_bar.maximum()})"
        )
