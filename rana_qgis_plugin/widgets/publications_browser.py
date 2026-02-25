from qgis.PyQt.QtCore import QSize, Qt, QUrl, pyqtSignal
from qgis.PyQt.QtGui import QDesktopServices, QStandardItem, QStandardItemModel
from qgis.PyQt.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from rana_qgis_plugin.utils_api import get_tenant_id
from rana_qgis_plugin.utils_settings import base_url
from rana_qgis_plugin.utils_time import (
    get_timestamp_as_numeric_item,
)
from rana_qgis_plugin.widgets.utils_delegates import (
    ContributorAvatarsDelegate,
    WordWrapDelegate,
)


class PublicationsBrowser(QWidget):
    def __init__(self, communication, avatar_cache, parent=None):
        super().__init__(parent)
        self.communication = communication
        self.avatar_cache = avatar_cache
        self.setup_ui()
        self.row_map = {}
        self.project = {}
        # TODO: pagination

    def update_project(self, project: dict):
        self.publications_model.removeRows(0, self.publications_model.rowCount())
        self.project = project
        self.row_map.clear()

    def setup_ui(self):
        self.publications_model = QStandardItemModel()
        self.publications_tv = QTreeView()
        self.publications_tv.setModel(self.publications_model)
        self.publications_tv.setEditTriggers(QTreeView.NoEditTriggers)
        self.publications_model.setHorizontalHeaderLabels(
            ["Name", "Who", "Created at", "Last modified"]
        )
        avatar_delegate = ContributorAvatarsDelegate(self.publications_tv)
        self.publications_tv.setItemDelegateForColumn(1, avatar_delegate)
        name_delegate = WordWrapDelegate(self.publications_tv)
        self.publications_tv.setItemDelegateForColumn(0, name_delegate)
        self.publications_tv.setWordWrap(True)
        self.publications_tv.setUniformRowHeights(False)
        self.publications_tv.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.publications_tv.setSortingEnabled(True)
        header = self.publications_tv.header()
        header.setSectionsMovable(False)
        header.setSectionsClickable(True)
        header.setSortIndicatorShown(True)
        header.setStretchLastSection(False)
        create_publication_btn = QPushButton(
            "Create publication (opens Rana in web browser)"
        )
        create_publication_btn.clicked.connect(self.create_publication_online)
        layout = QVBoxLayout(self)
        layout.addWidget(self.publications_tv)
        layout.addWidget(create_publication_btn)
        self.setLayout(layout)

    def create_publication_online(self):
        link = f"{base_url()}/{get_tenant_id()}/projects/{self.project['slug']}?tab=3&creating=true"
        if link:
            QDesktopServices.openUrl(QUrl(link))

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
        # Let first column stretch and resize the others to contents
        self.publications_tv.header().setSectionResizeMode(0, QHeaderView.Stretch)
        for col in range(1, self.publications_model.columnCount()):
            self.publications_tv.header().setSectionResizeMode(
                col, QHeaderView.ResizeToContents
            )

    def update_item(self, publication: dict):
        row = self.row_map.get(publication["id"], -1)
        if row < 0:
            return
        updated_item = get_timestamp_as_numeric_item(publication["updated_at"])
        self.publications_model.setItem(row, 3, updated_item)
