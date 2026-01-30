from dataclasses import dataclass

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import (
    QStandardItem,
    QStandardItemModel,
)
from qgis.PyQt.QtWidgets import (
    QHeaderView,
    QLabel,
    QProgressBar,
    QSizePolicy,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from rana_qgis_plugin.utils import convert_to_timestamp, get_timestamp_as_numeric_item
from rana_qgis_plugin.utils_api import get_tenant_id
from rana_qgis_plugin.utils_settings import base_url
from rana_qgis_plugin.widgets.utils_delegates import (
    ContributorAvatarsDelegate,
    WordWrapDelegate,
)


@dataclass
class JobData:
    id: int
    name: str
    user: str
    created: str
    status: str
    progress: int
    max_progress: int
    process_id: int | None

    def progress_str(self):
        return f"{self.status} ({self.progress}%)"

    @property
    def created_timestamp(self):
        return convert_to_timestamp(self.created)

    @property
    def user_name(self):
        return self.user["given_name"] + " " + self.user["family_name"]

    @classmethod
    def from_job_dict(cls, job: dict):
        from qgis.core import Qgis, QgsMessageLog

        try:
            return cls(
                id=job["id"],
                name=job["name"],
                user=job["creator"],
                created=job["created_at"],
                status=job["state"]["type"],
                progress=int(100 * job["state"]["progress"]),
                max_progress=100,
                process_id=job["process"].get("id") if job["process"] else None,
            )
        except Exception as e:
            QgsMessageLog.logMessage(f"create job {job=}", "DEBUG", Qgis.Info)
            raise e


class ProcessesBrowser(QWidget):
    start_monitoring_simulations = pyqtSignal()
    start_monitoring_model_generation = pyqtSignal()
    start_monitoring_project_jobs = pyqtSignal(str)

    def __init__(self, communication, avatar_cache, parent=None):
        super().__init__(parent)
        self.communication = communication
        self.avatar_cache = avatar_cache
        self.setup_ui()
        self.row_map = {}
        self.project = {}

    def update_project(self, project: dict):
        # Remove cached data
        self.processes_model.removeRows(0, self.processes_model.rowCount())
        self.row_map.clear()
        self.project = project
        # Start monitor jobs for the selected project
        self.start_monitoring_project_jobs.emit(project["id"])

    def setup_ui(self):
        self.processes_model = QStandardItemModel()
        self.processes_tv = QTreeView()
        self.processes_tv.setModel(self.processes_model)
        self.processes_tv.setEditTriggers(QTreeView.NoEditTriggers)
        layout = QVBoxLayout(self)
        layout.addWidget(self.processes_tv)
        self.setLayout(layout)
        # create root items, they will be added on populating
        self.processes_model.setHorizontalHeaderLabels(
            ["Name", "Who", "Started", "Status"]
        )
        avatar_delegate = ContributorAvatarsDelegate(self.processes_tv)
        self.processes_tv.setItemDelegateForColumn(1, avatar_delegate)
        name_delegate = WordWrapDelegate(self.processes_tv)
        self.processes_tv.setItemDelegateForColumn(0, name_delegate)
        self.processes_tv.setWordWrap(True)
        self.processes_tv.setUniformRowHeights(False)
        self.processes_tv.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.setContentsMargins(0, 0, 0, 0)
        self.processes_tv.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.processes_tv.header().setSectionResizeMode(1, QHeaderView.Fixed)
        self.processes_tv.header().setSectionResizeMode(2, QHeaderView.Fixed)
        self.processes_tv.header().setSectionResizeMode(3, QHeaderView.Fixed)
        self.processes_tv.setColumnWidth(1, 50)
        self.processes_tv.setColumnWidth(2, 150)
        self.processes_tv.setColumnWidth(3, 160)
        self.processes_tv.header().setStretchLastSection(False)
        self.processes_tv.setEditTriggers(QTreeView.NoEditTriggers)

    def add_item(self, job):
        name_item = QStandardItem()
        # Create QLabel to display a link as a typical html link
        name_link = QLabel("")
        self.update_job_link(name_link, job)
        who_item = QStandardItem()
        who_item.setData(
            [
                {
                    "id": job.user["id"],
                    "name": job.user_name,
                    "avatar": self.avatar_cache.get_avatar_for_user(job.user),
                }
            ],
            Qt.ItemDataRole.UserRole,
        )
        date_item = get_timestamp_as_numeric_item(job.created)
        status_item = QStandardItem()
        status_item.setData(job.status, Qt.ItemDataRole.UserRole)
        # Create the progress bar
        progress_bar = QProgressBar()
        progress_bar.setFixedWidth(160)
        self.update_pb_progress(progress_bar, job)
        progress_bar.setTextVisible(True)
        row = [name_item, who_item, date_item, status_item]
        self.processes_model.insertRow(0, row)
        self.processes_tv.setIndexWidget(status_item.index(), progress_bar)
        for id in self.row_map:
            self.row_map[id] += 1
        self.row_map[job.id] = 0
        self.processes_tv.setIndexWidget(name_item.index(), name_link)
        self.processes_tv.resizeColumnToContents(0)

    @staticmethod
    def update_pb_progress(progress_bar, job):
        progress_bar.setValue(job.progress)
        progress_bar.setMaximum(job.max_progress)
        progress_bar.setFormat(job.progress_str())

    def update_job_link(self, link_label, job):
        if job.process_id:
            job_url = f"{base_url()}/{get_tenant_id()}/projects/{self.project['code']}?tab=2&job={job.id}"
            link_label.setText(f'<a href="{job_url}">{job.name}</a>')
            link_label.setOpenExternalLinks(True)  # This makes the link clickable
            # use default styling
            link_label.setStyleSheet("")
        else:
            link_label.setText(job.name)
            # set style of items without link to match the treeview styling
            link_label.setStyleSheet(
                f"color: {self.processes_tv.palette().text().color().name()}"
            )

    def add_items(self, job_list: list[dict]):
        for job in job_list:
            self.add_item(JobData.from_job_dict(job))

    def update_job_state(self, job_dict: dict):
        job = JobData.from_job_dict(job_dict)
        row = self.row_map.get(job.id, -1)
        if row < 0:
            return
        status_item = self.processes_model.item(row, 3)
        status_item.setData(job.status, Qt.ItemDataRole.UserRole)
        self.update_pb_progress(self.processes_tv.indexWidget(status_item.index()), job)
        name_item = self.processes_model.item(row, 0)
        self.update_job_link(self.processes_tv.indexWidget(name_item.index()), job)
