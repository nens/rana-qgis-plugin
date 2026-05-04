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
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from rana_qgis_plugin.utils.api import get_tenant_projects, get_user_info
from rana_qgis_plugin.utils.generic import (
    NumericItem,
)
from rana_qgis_plugin.utils.settings import base_url, get_tenant_id
from rana_qgis_plugin.utils.time import (
    convert_to_numeric_timestamp,
    get_timestamp_as_numeric_item,
)
from rana_qgis_plugin.widgets.filter_bar import ComboFilterConfig, FilterBar, TextFilterConfig
from rana_qgis_plugin.widgets.utils_delegates import ContributorAvatarsDelegate


class ProjectsBrowser(QWidget):
    projects_refreshed = pyqtSignal()
    project_selected = pyqtSignal(dict)
    busy = pyqtSignal()
    ready = pyqtSignal()
    users_refreshed = pyqtSignal(list)

    def __init__(self, communication, avatar_cache, parent=None):
        super().__init__(parent)
        self.communication = communication
        self.tenant_projects = []
        self.users = []
        self.filtered_projects = []
        self.current_page = 1
        self.items_per_page = 100
        self.project = None
        self.avatar_cache = avatar_cache
        # collect data
        self.fetch_projects()
        self.update_users()
        self.setup_ui()
        self.populate_contributors()
        self.sort_projects(2, Qt.SortOrder.AscendingOrder, populate=False)
        self.populate_projects()

    def set_project_from_id(self, project_id: str):
        for project in self.tenant_projects:
            if project["id"] == project_id:
                self.project = project
                return

    def setup_ui(self):
        # Create filter bar
        self.filter_bar = FilterBar(
            filters=[
                TextFilterConfig(key="name", placeholder="🔍 Search for project by name"),
                ComboFilterConfig(key="who", placeholder="All contributors", dynamic=True),
                ComboFilterConfig(
                    key="status",
                    placeholder="All statuses",
                    dynamic=False,
                    items=[("Active", "active"), ("Archived", "archived")],
                ),
            ],
            refresh_callback=self.refresh,
            parent=self,
        )
        self.filter_bar.filters_changed.connect(self._apply_filters)
        # Create tree view with project files and model
        self.projects_model = QStandardItemModel()
        self.projects_tv = QTreeView()
        self.projects_tv.setModel(self.projects_model)
        self.projects_tv.setSortingEnabled(True)
        self.projects_tv.header().setSortIndicatorShown(True)
        self.projects_tv.header().setSectionsMovable(False)
        self.projects_tv.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.projects_tv.customContextMenuRequested.connect(self.show_context_menu)
        self.projects_tv.header().sortIndicatorChanged.connect(self.sort_projects)
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
        # Organize widgets in layouts
        pagination_layout = QHBoxLayout()
        pagination_layout.addWidget(self.btn_previous)
        pagination_layout.addWidget(
            self.label_page_number, alignment=Qt.AlignmentFlag.AlignCenter
        )
        pagination_layout.addWidget(self.btn_next)
        layout = QVBoxLayout(self)
        layout.addWidget(self.filter_bar)
        layout.addWidget(self.projects_tv)
        layout.addLayout(pagination_layout)
        self.setLayout(layout)

    def get_empty_placeholder(self) -> QLabel:
        # Create placeholder for when no projects are available
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

    def fetch_projects(self):
        self.tenant_projects = get_tenant_projects(self.communication)

    def update_users(self):
        self.users = list(
            {
                contributor["id"]: contributor
                for project in self.tenant_projects
                for contributor in project["contributors"]
            }.values()
        )
        self.users_refreshed.emit(self.users)

    def refresh(self):
        self.current_page = 1
        self.fetch_projects()
        self.update_users()
        self.sort_projects(2, Qt.SortOrder.AscendingOrder, populate=False)
        self._apply_filters(self.filter_bar.get_filters())
        self.populate_contributors()
        self.projects_refreshed.emit()

    @property
    def filter_active(self):
        f = self.filter_bar.get_filters()
        return bool(f.get("name") or f.get("who") or f.get("status"))

    def _apply_filters(self, filters: dict):
        name = filters.get("name", "").lower()
        who = filters.get("who", [])
        status = filters.get("status", [])
        if not self.filter_active:
            self.filtered_projects = self.tenant_projects
        else:
            self.filtered_projects = [
                p
                for p in self.tenant_projects
                if (not name or name in p["name"].lower())
                and (not who or any(c["id"] in who for c in p.get("contributors", [])))
                and (not status or p.get("status") in status)
            ]
        self.current_page = 1
        self.populate_projects()

    def filter_projects(self):
        self._apply_filters(self.filter_bar.get_filters())

    def sort_projects(self, column_index: int, order: Qt.SortOrder, populate=True):
        # Ensure indicator is set also on direct call
        self.projects_tv.header().blockSignals(True)
        self.projects_tv.header().setSortIndicator(column_index, order)
        self.projects_tv.header().blockSignals(False)
        self.current_page = 1
        key_funcs = [
            lambda project: project["name"].lower(),
            None,
            lambda project: -convert_to_numeric_timestamp(project["last_activity"]),
            lambda project: -convert_to_numeric_timestamp(project["created_at"]),
        ]
        key_func = key_funcs[column_index]
        if key_func:
            self.tenant_projects.sort(
                key=key_func, reverse=(order == Qt.SortOrder.DescendingOrder)
            )
        if populate:
            if self.filter_active:
                self.filter_projects()
            else:
                self.populate_projects()

    def show_context_menu(self, position):
        # Get the index under the cursor
        index = self.projects_tv.indexAt(position)

        # Check if we clicked on a valid item and it's in column 0
        if not index.isValid() or index.column() != 0:
            return

        # Get the project data
        project_item = self.projects_model.itemFromIndex(index)
        project = project_item.data(Qt.ItemDataRole.UserRole)

        # Create context menu
        menu = QMenu(self)

        # Add menu actions
        open_in_qgis = menu.addAction("Open project in QGIS")
        open_in_web = menu.addAction("Open project in Rana Web")

        # Show the menu and get the selected action
        action = menu.exec(self.projects_tv.viewport().mapToGlobal(position))

        # Handle the selected action
        if action == open_in_qgis:
            self.select_project(index)
        elif action == open_in_web:
            link = f"{base_url()}/{get_tenant_id()}/projects/{project['code']}"
            QDesktopServices.openUrl(QUrl(link))

    def process_project_item(
        self, project: dict
    ) -> list[QStandardItem, QStandardItem, NumericItem]:
        project_name = project["name"]
        # Process project name into item
        name_item = QStandardItem(project_name)
        formatted_project_tooltip = (
            f"{project_name}<br><b><code>{project['code']}</code></b>"
        )
        name_item.setToolTip(formatted_project_tooltip)
        name_item.setData(project, role=Qt.ItemDataRole.UserRole)
        # Process last activity time into item
        last_activity_item = get_timestamp_as_numeric_item(project["last_activity"])
        created_at_item = get_timestamp_as_numeric_item(project["created_at"])
        # process list of contributors into items
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

    def populate_projects(self):
        # clean table
        self.projects_model.removeRows(0, self.projects_model.rowCount())
        if not self.tenant_projects:
            self.empty_label.show()
            return
        self.empty_label.hide()
        # Paginate projects
        projects = (
            self.filtered_projects if self.filter_active else self.tenant_projects
        )
        start_index = (self.current_page - 1) * self.items_per_page
        end_index = start_index + self.items_per_page
        paginated_projects = projects[start_index:end_index]
        # Prepare data for adding
        processed_rows = [
            self.process_project_item(project) for project in paginated_projects
        ]
        # Populate model with new data
        for row in processed_rows:
            self.projects_model.invisibleRootItem().appendRow(row)
        for i in range(self.projects_tv.header().count()):
            self.projects_tv.resizeColumnToContents(i)
        self.projects_tv.setColumnWidth(0, 300)
        self.update_pagination(projects)

    def update_avatar(self, user_id: str):
        avatar = self.avatar_cache.get_avatar_from_cache(user_id)
        # Update who filter combo
        self.filter_bar.update_combo_avatar("who", user_id, avatar)
        # Update projects model
        root = self.projects_model.invisibleRootItem()
        for row in range(root.rowCount()):
            contributors_item = root.child(row, 1)
            contributors_data = contributors_item.data(Qt.ItemDataRole.UserRole)
            match = next(
                (c for c in contributors_data if c["id"] == user_id),
                None,
            )
            if match and match["avatar"]:
                match["avatar"] = avatar
                contributors_item.setData(contributors_data, Qt.ItemDataRole.UserRole)
        # Update projects model
        root = self.projects_model.invisibleRootItem()
        for row in range(root.rowCount()):
            contributors_item = root.child(row, 1)
            contributors_data = contributors_item.data(Qt.ItemDataRole.UserRole)
            # Check if any contributors in the data match the updated one
            match = next(
                (
                    contributor
                    for contributor in contributors_data
                    if contributor["id"] == user_id
                ),
                None,
            )
            if match and match["avatar"]:
                match["avatar"] = avatar
                contributors_item.setData(contributors_data, Qt.ItemDataRole.UserRole)

    def populate_contributors(self):
        # Collect all unique contributors to the projects
        all_contributors = {
            contributor["id"]: contributor
            for project in self.tenant_projects
            for contributor in project["contributors"]
        }
        # Sort users by name, starting with the current user
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

    def update_pagination(self, projects: list):
        total_items = len(projects)
        total_pages = (
            math.ceil(total_items / self.items_per_page) if total_items > 0 else 1
        )
        self.label_page_number.setText(f"Page {self.current_page}/{total_pages}")
        self.btn_previous.setDisabled(self.current_page == 1)
        self.btn_next.setDisabled(self.current_page == total_pages)

    def change_page(self, increment: int):
        self.current_page += increment
        self.populate_projects()

    def to_previous_page(self):
        self.change_page(-1)

    def to_next_page(self):
        self.change_page(1)

    def select_project(self, index: QModelIndex):
        self.setEnabled(False)
        self.busy.emit()
        self.communication.progress_bar("Loading project...", clear_msg_bar=True)
        try:
            # Only allow selection of the first column (project name)
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
