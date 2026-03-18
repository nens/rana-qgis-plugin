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
from rana_qgis_plugin.widgets.utils_qviews import update_width_with_wrapping


class PublicationsBrowser(QWidget):
    publication_selected = pyqtSignal(str)

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
        self.publications_model.setSortRole(Qt.ItemDataRole.UserRole)
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
        header.setSortIndicator(3, Qt.SortOrder.DescendingOrder)
        header.setSectionResizeMode(QHeaderView.Interactive)
        self.publications_tv.sortByColumn(3, Qt.SortOrder.DescendingOrder)
        create_publication_btn = QPushButton(
            "Create publication (opens Rana in web browser)"
        )
        create_publication_btn.clicked.connect(self.create_publication_online)
        layout = QVBoxLayout(self)
        layout.addWidget(self.publications_tv)
        layout.addWidget(create_publication_btn)
        self.setLayout(layout)
        self.publications_tv.doubleClicked.connect(self.on_publication_clicked)

    def on_publication_clicked(self, index):
        # publication data is stored in the first column
        # TODO: maybe this is a bit dirty, reconsider
        name_index = index.sibling(index.row(), 0)
        item = self.publications_model.itemFromIndex(name_index)
        if item:
            publication_id = item.data(Qt.ItemDataRole.UserRole + 1)
            from qgis.core import Qgis, QgsMessageLog

            QgsMessageLog.logMessage(
                f"Selected publication {publication_id}", "DEBUG", Qgis.Info
            )
            if publication_id:
                self.publication_selected.emit(publication_id)

    def create_publication_online(self):
        link = f"{base_url()}/{get_tenant_id()}/projects/{self.project['slug']}?tab=3&creating=true"
        if link:
            QDesktopServices.openUrl(QUrl(link))

    def make_items(self, publication) -> list[QStandardItem]:
        name_item = QStandardItem(publication["name"])
        name_item.setData(publication["name"].lower(), role=Qt.ItemDataRole.UserRole)
        name_item.setData(publication["id"], role=Qt.ItemDataRole.UserRole + 1)
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
        return [name_item, who_item, created_at_item, last_modified_item]

    def add_items(self, publication_list: list[dict]):
        for publication in publication_list:
            self.publications_model.appendRow(self.make_items(publication))
            self.row_map[publication["id"]] = self.publications_model.rowCount() - 1
        # Let first column stretch and resize the others to contents
        self.apply_current_sort()
        self.update_width()

    def find_row_by_publication_id(self, publication_id: str):
        for row in range(self.publications_model.rowCount()):
            publication_id_item = self.publications_model.item(row, 0).data(
                Qt.ItemDataRole.UserRole + 1
            )
            if publication_id_item == publication_id:
                return row

    def update_item(self, publication: dict):
        row = self.find_row_by_publication_id(publication["id"])
        if not row:
            return
        # Just update all items
        new_items = self.make_items(publication)
        for i, updated_item in enumerate(new_items):
            self.publications_model.setItem(row, i, updated_item)
        self.apply_current_sort()
        self.update_width()

    def apply_current_sort(self):
        header = self.publications_tv.header()
        sorted_column = header.sortIndicatorSection()
        sort_order = header.sortIndicatorOrder()
        self.publications_tv.sortByColumn(sorted_column, sort_order)

    def showEvent(self, event):
        super().showEvent(event)
        self.update_width()

    def resizeEvent(self, event):
        """
        Dynamically adjusts the first column's width when the widget is resized.
        """
        super().resizeEvent(event)
        self.update_width()  # Recalculate the widths for dynamic resizing

    def update_width(self):
        update_width_with_wrapping(self.publications_tv, self.publications_model, 0)
