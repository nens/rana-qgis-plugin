import math

from qgis.PyQt.QtCore import (
    QModelIndex,
    Qt,
    QUrl,
    pyqtSignal,
)
from qgis.PyQt.QtGui import (
    QDesktopServices,
    QStandardItem,
    QStandardItemModel,
)
from qgis.PyQt.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QToolButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from rana_qgis_plugin.icons import refresh_icon
from rana_qgis_plugin.utils.api import get_tenant_projects, get_user_info
from rana_qgis_plugin.utils.generic import (
    NumericItem,
)
from rana_qgis_plugin.utils.settings import base_url, get_tenant_id
from rana_qgis_plugin.utils.time import (
    get_timestamp_as_numeric_item,
)
from rana_qgis_plugin.widgets.filter_bar import (
    ComboFilterConfig,
    FilterBar,
    TextFilterConfig,
)
from rana_qgis_plugin.widgets.utils_delegates import ContributorAvatarsDelegate

# Maps column index to the project dict key used for client-side sorting
_SORT_KEYS = {
    0: lambda p: (p["name"] or "").lower(),
    2: lambda p: p["last_activity"] or "",
    3: lambda p: p["created_at"] or "",
}


class _ManuallyOrderedModel(QStandardItemModel):
    """QStandardItemModel whose sort() is a no-op.

    Row order is managed manually (client-side sort + repopulate), so Qt must
    never reorder rows. The sort indicator on the header still updates visually
    because QHeaderView manages it independently of the model's sort() method.
    """

    def sort(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder):
        pass  # row order is managed by _sort_and_display


class ProjectsBrowser(QWidget):
    projects_refreshed = pyqtSignal()
    project_selected = pyqtSignal(dict)
    busy = pyqtSignal()
    ready = pyqtSignal()
    users_refreshed = pyqtSignal(list)

    def __init__(self, communication, avatar_cache, parent=None):
        super().__init__(parent)
        self.communication = communication
        self.project = None
        self.avatar_cache = avatar_cache
        self.current_page = 1
        self.items_per_page = 20
        self._total_projects = 0
        self._sort_column = 2  # default: last activity
        self._sort_order = Qt.SortOrder.DescendingOrder
        self._all_projects: list = []
        self.setup_ui()
        self._fetch_and_populate()

    def set_project_from_id(self, project_id: str):
        root = self.projects_model.invisibleRootItem()
        for row in range(root.rowCount()):
            project = root.child(row, 0).data(Qt.ItemDataRole.UserRole)
            if project and project["id"] == project_id:
                self.project = project
                return

    def setup_ui(self):
        # Create filter bar
        self.filter_bar = FilterBar(
            filters=[
                TextFilterConfig(key="name", placeholder="Search for project by name"),
                ComboFilterConfig(
                    key="who", placeholder="All contributors", dynamic=True
                ),
            ],
            parent=self,
        )
        self.filter_bar.filters_changed.connect(self._on_filters_changed)
        # Create tree view with project files and model
        self.projects_model = _ManuallyOrderedModel()
        self.projects_tv = QTreeView()
        self.projects_tv.setRootIsDecorated(False)
        self.projects_tv.setModel(self.projects_model)
        self.projects_tv.setSortingEnabled(True)
        self.projects_tv.header().setSortIndicatorShown(True)
        self.projects_tv.header().setSectionsMovable(False)
        self.projects_tv.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.projects_tv.customContextMenuRequested.connect(self.show_context_menu)
        self.projects_tv.header().sortIndicatorChanged.connect(self._on_sort_changed)
        self.projects_model.setHorizontalHeaderLabels(
            ["Project Name", "Contributors", "Last activity", "Created at"]
        )
        avatar_delegate = ContributorAvatarsDelegate(self.projects_tv)
        self.projects_tv.setItemDelegateForColumn(1, avatar_delegate)
        self.projects_tv.doubleClicked.connect(self.select_project)
        viewport_layout = QVBoxLayout(self.projects_tv.viewport())
        viewport_layout.setContentsMargins(0, 0, 0, 0)
        # Create placeholder for cases with no projects
        self.empty_label = self.get_empty_placeholder()
        viewport_layout.addWidget(self.empty_label)
        # Create navigation buttons
        self.btn_previous = QPushButton("<")
        self.label_page_number = QLabel("Page 1/1")
        self.btn_next = QPushButton(">")
        self.btn_previous.clicked.connect(self.to_previous_page)
        self.btn_next.clicked.connect(self.to_next_page)
        self.refresh_btn = QToolButton()
        self.refresh_btn.setToolTip("Refresh")
        self.refresh_btn.setIcon(refresh_icon)
        # Organize widgets in layouts
        top_layout = QHBoxLayout()
        top_layout.addWidget(self.filter_bar)
        top_layout.addWidget(self.refresh_btn)
        pagination_layout = QHBoxLayout()
        pagination_layout.addWidget(self.btn_previous)
        pagination_layout.addWidget(
            self.label_page_number, alignment=Qt.AlignmentFlag.AlignCenter
        )
        pagination_layout.addWidget(self.btn_next)
        layout = QVBoxLayout(self)
        layout.addLayout(top_layout)
        layout.addWidget(self.projects_tv)
        layout.addLayout(pagination_layout)
        self.setLayout(layout)
        # Set initial sort indicator to match default ordering (last activity, descending)
        self.projects_tv.header().blockSignals(True)
        self.projects_tv.header().setSortIndicator(2, Qt.SortOrder.DescendingOrder)
        self.projects_tv.header().blockSignals(False)

    def get_empty_placeholder(self) -> QLabel:
        new_project_url = f"{base_url()}/{get_tenant_id()}/projects-new"
        empty_label = QLabel(
            f"""
                <div style="text-align:center;">
                    <h2 style="font-weight:600; margin-bottom:12px;">
                        No projects found
                    </h2>
                    <br><br> 
                    <a href="{new_project_url}" style="display:inline-block; margin-top:4px;">
                        Create a project
                    </a>
                </div>
            """,
            self.projects_tv.viewport(),
        )
        empty_label.setOpenExternalLinks(True)
        empty_label.setAlignment(Qt.AlignCenter)
        empty_label.hide()
        return empty_label

    def _build_filter_params(self) -> dict:
        """Build API filter params (no sort/pagination — those are client-side)."""
        filters = self.filter_bar.get_filters()
        params = {}
        if filters.get("name"):
            params["search"] = filters["name"]
        if filters.get("who"):
            params["project_user_id"] = filters["who"]
        return params

    def _fetch_and_populate(self):
        """Fetch all matching projects from the API, then sort and display."""
        response = get_tenant_projects(
            self.communication, params=self._build_filter_params()
        )
        self._all_projects = response.get("items", [])
        self.current_page = 1
        self._sort_and_display()

    def _sort_and_display(self):
        """Sort the in-memory project list and display the current page slice."""
        key_fn = _SORT_KEYS.get(self._sort_column)
        if key_fn:
            descending = self._sort_order == Qt.SortOrder.DescendingOrder
            sorted_projects = sorted(self._all_projects, key=key_fn, reverse=descending)
        else:
            sorted_projects = self._all_projects

        self._total_projects = len(sorted_projects)
        start = (self.current_page - 1) * self.items_per_page
        page_projects = sorted_projects[start : start + self.items_per_page]

        self.projects_model.removeRows(0, self.projects_model.rowCount())
        if not page_projects:
            self.empty_label.show()
            self.update_pagination()
            return
        self.empty_label.hide()
        for project in page_projects:
            self.projects_model.invisibleRootItem().appendRow(
                self.process_project_item(project)
            )
        # Update sort indicator without re-triggering the signal
        header = self.projects_tv.header()
        header.blockSignals(True)
        header.setSortIndicator(self._sort_column, self._sort_order)
        header.blockSignals(False)
        for i in range(header.count()):
            self.projects_tv.resizeColumnToContents(i)
        self.projects_tv.setColumnWidth(0, 300)
        self.populate_contributors(self._all_projects)
        self.update_pagination()
        self.projects_refreshed.emit()
        all_users = [
            contributor
            for project in page_projects
            for contributor in project.get("contributors", [])
        ]
        self.users_refreshed.emit(all_users)

    def _on_filters_changed(self, _filters: dict):
        self._fetch_and_populate()

    def _on_sort_changed(self, column_index: int, order: Qt.SortOrder):
        if column_index not in _SORT_KEYS:
            return  # contributors column not sortable
        self._sort_column = column_index
        self._sort_order = order
        self.current_page = 1
        self._sort_and_display()

    def refresh(self):
        self._fetch_and_populate()

    def show_context_menu(self, position):
        index = self.projects_tv.indexAt(position)
        if not index.isValid() or index.column() != 0:
            return
        project_item = self.projects_model.itemFromIndex(index)
        project = project_item.data(Qt.ItemDataRole.UserRole)
        menu = QMenu(self)
        open_in_qgis = menu.addAction("Open project in QGIS")
        open_in_web = menu.addAction("Open project in Rana Web")
        action = menu.exec(self.projects_tv.viewport().mapToGlobal(position))
        if action == open_in_qgis:
            self.select_project(index)
        elif action == open_in_web:
            link = f"{base_url()}/{get_tenant_id()}/projects/{project['code']}"
            QDesktopServices.openUrl(QUrl(link))

    def process_project_item(
        self, project: dict
    ) -> list[QStandardItem, QStandardItem, NumericItem]:
        project_name = project["name"]
        name_item = QStandardItem(project_name)
        formatted_project_tooltip = (
            f"{project_name}<br><b><code>{project['code']}</code></b>"
        )
        name_item.setToolTip(formatted_project_tooltip)
        name_item.setData(project, role=Qt.ItemDataRole.UserRole)
        last_activity_item = get_timestamp_as_numeric_item(project["last_activity"])
        created_at_item = get_timestamp_as_numeric_item(project["created_at"])
        contributors_item = QStandardItem()
        contributors_data = []
        for i, contributor in enumerate(project.get("contributors", [])):
            avatar = (
                self.avatar_cache.get_avatar_for_user(contributor) if i < 3 else None
            )
            contributors_data.append(
                {
                    "id": contributor["id"],
                    "name": contributor["given_name"]
                    + " "
                    + contributor["family_name"],
                    "avatar": avatar,
                }
            )
        contributors_item.setData(contributors_data, Qt.ItemDataRole.UserRole)
        contributors_item.setData(-1, Qt.ItemDataRole.InitialSortOrderRole)
        return [name_item, contributors_item, last_activity_item, created_at_item]

    def update_avatar(self, user_id: str):
        avatar = self.avatar_cache.get_avatar_from_cache(user_id)
        self.filter_bar.update_combo_avatar("who", user_id, avatar)
        root = self.projects_model.invisibleRootItem()
        for row in range(root.rowCount()):
            contributors_item = root.child(row, 1)
            contributors_data = contributors_item.data(Qt.ItemDataRole.UserRole)
            match = next(
                (c for c in contributors_data if c["id"] == user_id),
                None,
            )
            if match:
                match["avatar"] = avatar
                contributors_item.setData(contributors_data, Qt.ItemDataRole.UserRole)

    def populate_contributors(self, projects: list):
        """Populate the who combo from the current page's projects."""
        all_contributors = {
            contributor["id"]: contributor
            for project in projects
            for contributor in project["contributors"]
        }
        my_info = get_user_info(self.communication)
        if my_info and my_info.get("sub") in all_contributors:
            my_id = my_info["sub"]
            my_user = [all_contributors.pop(my_id)]
        else:
            my_id = None
            my_user = []
        sorted_users = my_user + sorted(
            all_contributors.values(),
            key=lambda x: f"{x['given_name']} {x['family_name']}".lower(),
        )
        items = []
        for user in sorted_users:
            display_name = f"{user['given_name']} {user['family_name']}"
            if user["id"] == my_id:
                display_name += " (You)"
            avatar = self.avatar_cache.get_avatar_for_user(user)
            items.append((display_name, user["id"], avatar))
        self.filter_bar.set_combo_items("who", items)

    def update_pagination(self):
        total_pages = (
            math.ceil(self._total_projects / self.items_per_page)
            if self._total_projects > 0
            else 1
        )
        self.label_page_number.setText(f"Page {self.current_page}/{total_pages}")
        self.btn_previous.setDisabled(self.current_page == 1)
        self.btn_next.setDisabled(self.current_page == total_pages)

    def change_page(self, increment: int):
        self.current_page += increment
        self._sort_and_display()

    def to_previous_page(self):
        self.change_page(-1)

    def to_next_page(self):
        self.change_page(1)

    def select_project(self, index: QModelIndex):
        self.setEnabled(False)
        self.busy.emit()
        self.communication.progress_bar("Loading project...", clear_msg_bar=True)
        try:
            if index.column() != 0:
                return
            project_item = self.projects_model.itemFromIndex(index)
            new_project = project_item.data(Qt.ItemDataRole.UserRole)
            self.project = new_project
            self.project_selected.emit(self.project)
        finally:
            self.communication.clear_message_bar()
            self.ready.emit()
            self.setEnabled(True)
