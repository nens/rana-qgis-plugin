from dataclasses import dataclass

from qgis.PyQt.QtCore import QEvent, QSize, Qt, QTimer, pyqtSignal
from qgis.PyQt.QtGui import QStandardItem, QStandardItemModel, QTextDocument
from qgis.PyQt.QtWidgets import (
    QApplication,
    QHeaderView,
    QProgressBar,
    QSizePolicy,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QToolTip,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from rana_qgis_plugin.utils import convert_to_timestamp, get_timestamp_as_numeric_item
from rana_qgis_plugin.utils_api import get_project_jobs, get_user_by_email
from rana_qgis_plugin.widgets.utils_avatars import (
    ContributorAvatarsDelegate,
    get_user_image_from_initials,
)


class WordWrapDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        options = QStyleOptionViewItem(option)
        self.initStyleOption(options, index)
        options.features |= QStyleOptionViewItem.WrapText
        style = (
            QApplication.style() if options.widget is None else options.widget.style()
        )
        style.drawControl(QStyle.CE_ItemViewItem, options, painter)

    def sizeHint(self, option, index):
        options = QStyleOptionViewItem(option)
        self.initStyleOption(options, index)
        options.features |= QStyleOptionViewItem.WrapText

        # Calculate required size with wrapping
        doc = QTextDocument()
        doc.setHtml(options.text)
        doc.setTextWidth(option.rect.width())

        # Convert float height to int using round or int
        return QSize(option.rect.width(), int(doc.size().height()))

    def helpEvent(self, event, view, option, index):
        """Handle tooltip events to show the full text when hovering."""
        if not event or not view or event.type() != QEvent.ToolTip:
            return super().helpEvent(event, view, option, index)

        text = index.data(Qt.DisplayRole)
        if not text:
            return super().helpEvent(event, view, option, index)

        QToolTip.showText(event.globalPos(), text)
        return True


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
        return f"{self.status} ({self.progress}%)"

    @property
    def created_timestamp(self):
        return convert_to_timestamp(self.created)


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
        if self.max_progress == self.progress:
            return self.status
        else:
            return f"{self.status} ({self.progress} of {self.max_progress})"


class TasksBrowser(QWidget):
    start_monitoring_simulations = pyqtSignal()
    start_monitoring_model_generation = pyqtSignal()
    start_monitoring_project_jobs = pyqtSignal(str)

    def __init__(self, communication, avatar_cache, parent=None):
        super().__init__(parent)
        self.communication = communication
        self.avatar_cache = avatar_cache
        self.tasks = []
        self.setup_ui()
        self.row_map = {}
        # QTimer.singleShot(0, lambda: self.start_monitoring_simulations.emit())
        # QTimer.singleShot(0, lambda: self.start_monitoring_model_generation.emit())

    def update_project(self, project: dict):
        # Remove cached data
        self.tasks_model.removeRows(0, self.tasks_model.rowCount())
        self.row_map.clear()
        # Start monitor jobs for the selected project
        self.start_monitoring_project_jobs.emit(project["id"])

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
        avatar_delegate = ContributorAvatarsDelegate(self.tasks_tv)
        self.tasks_tv.setItemDelegateForColumn(1, avatar_delegate)
        name_delegate = WordWrapDelegate(self.tasks_tv)
        self.tasks_tv.setItemDelegateForColumn(0, name_delegate)
        self.tasks_tv.setWordWrap(True)
        self.tasks_tv.setUniformRowHeights(False)
        self.tasks_tv.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.setContentsMargins(0, 0, 0, 0)
        self.tasks_tv.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tasks_tv.header().setSectionResizeMode(1, QHeaderView.Fixed)
        self.tasks_tv.header().setSectionResizeMode(2, QHeaderView.Fixed)
        self.tasks_tv.header().setSectionResizeMode(3, QHeaderView.Fixed)
        self.tasks_tv.setColumnWidth(1, 50)
        self.tasks_tv.setColumnWidth(2, 150)
        self.tasks_tv.setColumnWidth(3, 160)
        self.tasks_tv.header().setStretchLastSection(False)

    def add_task(self, task):
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
        progress_bar.setFixedWidth(160)
        self.update_pb_progress(progress_bar, task)
        progress_bar.setTextVisible(True)
        row = [name_item, who_item, date_item, status_item]
        self.tasks_model.insertRow(0, row)
        self.tasks_tv.setIndexWidget(status_item.index(), progress_bar)
        for id in self.row_map:
            self.row_map[id] += 1
        self.row_map[task.id] = 0
        self.tasks_tv.resizeColumnToContents(0)

    @staticmethod
    def update_pb_progress(progress_bar, task):
        progress_bar.setValue(task.progress)
        progress_bar.setMaximum(task.max_progress)
        progress_bar.setFormat(task.progress_str())

    def get_rana_jobs(self, project_id):
        self.tasks_model.removeRows(0, self.tasks_model.rowCount())

        # project_id = "zBmCQhv3"
        jobs = get_project_jobs(self.communication, project_id)["items"]
        for job in jobs:
            # TODO: note that email should be replaced by id
            self.add_task(
                TaskData(
                    id=job["id"],
                    name=job["name"],
                    user_email=job["creator"]["email"],
                    created=job["created_at"],
                    status=job["state"]["type"],
                    progress=int(100 * job["state"]["progress"]),
                    max_progress=100,
                )
            )

    def add_processes(self, job_list: list[dict]):
        for job in job_list:
            # TODO: note that email should be replaced by id
            self.add_task(
                TaskData(
                    id=job["id"],
                    name=job["name"],
                    user_email=job["creator"]["email"],
                    created=job["created_at"],
                    status=job["state"]["type"],
                    progress=int(100 * job["state"]["progress"]),
                    max_progress=100,
                )
            )

    def update_process_state(self, job_dict: dict):
        task = TaskData(
            id=job["id"],
            name=job["name"],
            user_email=job["creator"]["email"],
            created=job["created_at"],
            status=job["state"]["type"],
            progress=int(100 * job["state"]["progress"]),
            max_progress=100,
        )
        row = self.row_map.get(task.id, -1)
        if row < 0:
            return
        status_item = self.tasks_model.child(row, 3)
        status_item.setData(task.status, Qt.ItemDataRole.UserRole)
        self.update_pb_progress(self.tasks_tv.indexWidget(status_item.index()), task)
