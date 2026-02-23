from qgis.core import QgsApplication
from qgis.PyQt.QtCore import QSize, Qt, pyqtSignal
from qgis.PyQt.QtGui import (
    QStandardItem,
    QStandardItemModel,
)
from qgis.PyQt.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QSizePolicy,
    QToolButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from rana_qgis_plugin.utils_api import get_tenant_id
from rana_qgis_plugin.utils_settings import base_url
from rana_qgis_plugin.utils_time import (
    convert_to_numeric_timestamp,
    get_timestamp_as_numeric_item,
)
from rana_qgis_plugin.widgets.processes_browser import JobData
from rana_qgis_plugin.widgets.utils_delegates import (
    ContributorAvatarsDelegate,
    WordWrapDelegate,
)


class PublicationsBrowser(QWidget):
    start_monitoring_project_publications = pyqtSignal(str)

    def __init__(self, communication, avatar_cache, parent=None):
        super().__init__(parent)
        self.communication = communication
        self.avatar_cache = avatar_cache
        self.setup_ui()
        self.row_map = {}
        self.project = {}

    def update_project(self, project: dict):
        self.publications_model.removeRows(0, self.publications_model.rowCount())
        self.project = project
        self.row_map.clear()
        self.start_monitoring_project_publications.emit(project["id"])

    def setup_ui(self):
        self.publications_model = QStandardItemModel()
        self.publications_tv = QTreeView()
        self.publications_tv.setModel(self.publications_model)
        self.publications_tv.setEditTriggers(QTreeView.NoEditTriggers)
        layout = QVBoxLayout(self)
        layout.addWidget(self.publications_tv)
        self.setLayout(layout)
        # TODO: make naming consistent
        self.publications_model.setHorizontalHeaderLabels(
            ["Name", "Created by", "Created at", "Last modified"]
        )
        avatar_delegate = ContributorAvatarsDelegate(self.publications_tv)
        self.publications_tv.setItemDelegateForColumn(1, avatar_delegate)
        name_delegate = WordWrapDelegate(self.publications_tv)
        self.publications_tv.setItemDelegateForColumn(0, name_delegate)
        self.publications_tv.setWordWrap(True)
        self.publications_tv.setUniformRowHeights(False)
        self.publications_tv.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def add_item(self, publication):
        name_item = QStandardItem(publication["name"])
        who_item = QStandardItem()
        who_item.setData(
            [
                {
                    "id": publication["creator"]["id"],
                    "name": publication["creator"]["given_name"]
                    + " "
                    + publication["creator"]["family_name"],
                    "avatar": self.avatar_cache.get_avatar_for_user(
                        publication["creator"]
                    ),
                }
            ],
            Qt.ItemDataRole.UserRole,
        )
        created_at_item = get_timestamp_as_numeric_item(publication["created_at"])
        last_modified_item = get_timestamp_as_numeric_item(publication["updated_at"])
        self.publications_model.appendRow(
            [name_item, who_item, created_at_item, last_modified_item]
        )
        self.row_map[publication["id"]] = self.publications_model.rowCount() - 1

    def add_items(self, publication_list: list[dict]):
        for publication in publication_list:
            self.add_item(publication)

    def update_item(self, publication: dict):
        row = self.row_map.get(publication["id"], -1)
        if row < 0:
            return
        updated_item = get_timestamp_as_numeric_item(publication["updated_at"])
        self.publications_model.setItem(row, 2, updated_item)
