"""Dialog for managing project visibility in the Rana Browser."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from qgis.PyQt.QtCore import QAbstractTableModel, QModelIndex, QRect, Qt
from qgis.PyQt.QtGui import QPixmap
from qgis.PyQt.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QStyle,
    QToolButton,
    QTreeView,
    QVBoxLayout,
)

from rana_qgis_plugin.api_error_signals import ApiErrorSignals
from rana_qgis_plugin.icons import refresh_icon
from rana_qgis_plugin.network_manager import NetworkUnavailableError
from rana_qgis_plugin.utils.api import (
    RanaFetchError,
    get_tenant_projects,
    get_user_info,
)
from rana_qgis_plugin.utils.settings import (
    base_url,
    get_hidden_projects,
    get_tenant_id,
    set_hidden_projects,
)
from rana_qgis_plugin.utils.time import format_activity_timestamp_str
from rana_qgis_plugin.widgets.filter_bar import (
    ComboFilterConfig,
    FilterBar,
    TextFilterConfig,
)
from rana_qgis_plugin.widgets.utils_avatars import AvatarCache
from rana_qgis_plugin.widgets.utils_delegates import ContributorAvatarsDelegate

if TYPE_CHECKING:
    from rana_qgis_plugin.communication import UICommunication
    from rana_qgis_plugin.loader import Loader

_COL_VISIBLE = 0
_COL_NAME = 1
_COL_CONTRIBUTORS = 2
_COL_LAST_ACTIVITY = 3
_COL_CREATED_AT = 4

_HEADERS = ["", "Project Name", "Contributors", "Last activity", "Created at"]

_SORT_KEYS = {
    _COL_NAME: lambda p: (p["name"] or "").lower(),
    _COL_LAST_ACTIVITY: lambda p: p["last_activity"] or "",
    _COL_CREATED_AT: lambda p: p["created_at"] or "",
}


class ProjectsModel(QAbstractTableModel):
    """Table model for project visibility selection.

    Each row holds a project dict and a visibility bool. Visibility is the
    sole source of truth — the model owns this state and nothing else does.
    Filtering and sorting replace the row list; visibility is keyed by
    project ID so it survives rebuilds.
    """

    def __init__(self, hidden_ids: set, parent=None):
        super().__init__(parent)
        self._rows: list[tuple[dict, bool]] = []
        self._visibility: dict[str, bool] = {}
        self._hidden_ids = hidden_ids

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(_HEADERS)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role=Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
        ):
            return _HEADERS[section]
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:  # type: ignore[override]
        if index.column() == _COL_VISIBLE:
            return (  # type: ignore[return-value]
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsUserCheckable
            )
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable  # type: ignore[return-value]

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        project, visible = self._rows[index.row()]
        col = index.column()

        if col == _COL_VISIBLE:
            if role == Qt.ItemDataRole.CheckStateRole:
                return Qt.CheckState.Checked if visible else Qt.CheckState.Unchecked
            return None

        if role == Qt.ItemDataRole.DisplayRole:
            if col == _COL_NAME:
                return project["name"] or ""
            if col == _COL_LAST_ACTIVITY:
                return format_activity_timestamp_str(project["last_activity"])
            if col == _COL_CREATED_AT:
                return format_activity_timestamp_str(project["created_at"])

        if role == Qt.ItemDataRole.ToolTipRole and col == _COL_NAME:
            return f"{project['name']}<br><b><code>{project.get('code', '')}</code></b>"

        if role == Qt.ItemDataRole.UserRole:
            if col == _COL_CONTRIBUTORS:
                return project.get("_contributors_data")
            if col == _COL_VISIBLE:
                return project["id"]

        return None

    def setData(
        self, index: QModelIndex, value: Any, role=Qt.ItemDataRole.EditRole
    ) -> bool:
        if not index.isValid():
            return False
        if index.column() == _COL_VISIBLE and role == Qt.ItemDataRole.CheckStateRole:
            project, _ = self._rows[index.row()]
            visible = value == Qt.CheckState.Checked
            self._rows[index.row()] = (project, visible)
            self._visibility[project["id"]] = visible
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])
            return True
        return False

    def sort(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder):
        pass  # sorting is managed manually via load_projects

    def load_projects(
        self,
        projects: list[dict],
        sort_column: int,
        sort_order: Qt.SortOrder,
    ):
        """Replace the row list. Visibility is read from the persistent _visibility dict."""
        key_fn = _SORT_KEYS.get(sort_column)
        sorted_projects = (
            sorted(
                projects,
                key=key_fn,
                reverse=(sort_order == Qt.SortOrder.DescendingOrder),
            )
            if key_fn
            else projects
        )

        self.beginResetModel()
        self._rows = [
            (p, self._visibility.get(p["id"], p["id"] not in self._hidden_ids))
            for p in sorted_projects
        ]
        self.endResetModel()

    def set_all_visible(self, visible: bool):
        """Set all currently shown rows to visible or hidden."""
        if not self._rows:
            return
        for i, (project, _) in enumerate(self._rows):
            self._rows[i] = (project, visible)
            self._visibility[project["id"]] = visible
        top_left = self.index(0, _COL_VISIBLE)
        bottom_right = self.index(len(self._rows) - 1, _COL_VISIBLE)
        self.dataChanged.emit(top_left, bottom_right, [Qt.ItemDataRole.CheckStateRole])

    def hidden_ids(self) -> set:
        """Return IDs of all projects with visibility=False (including those not currently displayed)."""
        return {pid for pid, visible in self._visibility.items() if not visible}

    def header_check_state(self) -> Qt.CheckState:
        """Tri-state summary of visible rows: all checked, none checked, or mixed."""
        if not self._rows:
            return Qt.CheckState.Unchecked
        states = {visible for _, visible in self._rows}
        if states == {True}:
            return Qt.CheckState.Checked
        if states == {False}:
            return Qt.CheckState.Unchecked
        return Qt.CheckState.PartiallyChecked


class VisibilityHeader(QHeaderView):
    """Horizontal header that draws a tri-state checkbox in the visibility column.

    Clicking the checkbox checks all visible rows when unchecked or partial,
    and unchecks all when fully checked.
    """

    def __init__(self, model: ProjectsModel, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self._model = model
        self._checkbox = QCheckBox(self)
        self._checkbox.setTristate(True)
        self._checkbox.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._checkbox.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._model.dataChanged.connect(lambda *_: self._sync_checkbox_state())
        self._model.modelReset.connect(self._sync_checkbox_state)
        self.sectionResized.connect(lambda *_: self._position_checkbox())
        self.sectionMoved.connect(lambda *_: self._position_checkbox())
        self.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sync_checkbox_state()

    def _section_rect(self, logical_index: int) -> QRect:
        """Return section geometry in header coordinates."""
        return QRect(
            self.sectionPosition(logical_index) - self.offset(),
            0,
            self.sectionSize(logical_index),
            self.height(),
        )

    def _checkbox_rect(self) -> QRect:
        """Return native checkbox geometry inside the visibility section."""
        section_rect = self._section_rect(_COL_VISIBLE)
        style = self.style()
        hint = self._checkbox.sizeHint()
        margin = style.pixelMetric(QStyle.PixelMetric.PM_FocusFrameHMargin) + 2
        x = section_rect.x() + margin
        y = section_rect.y() + (section_rect.height() - hint.height()) // 2
        return QRect(x, y, hint.width(), hint.height())

    def _position_checkbox(self):
        if self.count() <= _COL_VISIBLE or self.isSectionHidden(_COL_VISIBLE):
            self._checkbox.hide()
            return
        self._checkbox.setGeometry(self._checkbox_rect())
        self._checkbox.show()

    def _sync_checkbox_state(self):
        self._checkbox.blockSignals(True)
        self._checkbox.setCheckState(self._model.header_check_state())
        self._checkbox.blockSignals(False)
        self._position_checkbox()
        self.viewport().update()

    def paintEvent(self, event):
        super().paintEvent(event)
        self._position_checkbox()

    def mousePressEvent(self, event):
        logical = self.logicalIndexAt(event.pos())
        if logical == _COL_VISIBLE and self._checkbox.geometry().contains(event.pos()):
            current = self._model.header_check_state()
            self._model.set_all_visible(current != Qt.CheckState.Checked)
            return
        super().mousePressEvent(event)


class ProjectsSelectionDialog(QDialog):
    """Dialog that shows all tenant projects and lets the user toggle visibility."""

    def __init__(
        self,
        communication: UICommunication,
        loader: Loader,
        error_signals: ApiErrorSignals,
        parent=None,
    ):
        super().__init__(parent)
        self.communication = communication
        self.loader = loader
        self.error_signals = error_signals
        self.avatar_cache: AvatarCache = loader.avatar_cache
        self._sort_column = _COL_LAST_ACTIVITY
        self._sort_order = Qt.SortOrder.DescendingOrder
        self._all_projects: list[dict] = []
        self._hidden_ids: set = get_hidden_projects(base_url(), get_tenant_id())
        self._last_toggled_row: int | None = None
        self._has_fetched = False
        self.loader.avatar_updated.connect(self.on_avatar_updated)
        self.projects_model = ProjectsModel(self._hidden_ids)
        self.setWindowTitle("Select visible projects")
        self.resize(900, 600)
        self.setup_ui()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._has_fetched:
            self._has_fetched = True
            self.fetch_and_populate()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            focused_widget = QApplication.focusWidget()
            if focused_widget is not None and self.filter_bar.isAncestorOf(
                focused_widget
            ):
                event.accept()
                return
        super().keyPressEvent(event)

    def setup_ui(self):
        self.filter_bar = FilterBar(
            filters=[
                TextFilterConfig(key="name", placeholder="Search for project by name"),
                ComboFilterConfig(
                    key="who", placeholder="All contributors", dynamic=True
                ),
            ],
            parent=self,
        )
        self.filter_bar.filters_changed.connect(self.on_filters_changed)

        self.refresh_btn = QToolButton()
        self.refresh_btn.setToolTip("Refresh")
        self.refresh_btn.setIcon(refresh_icon)
        self.refresh_btn.clicked.connect(self.fetch_and_populate)

        self.check_all_btn = None  # replaced by header checkbox
        self.uncheck_all_btn = None

        self.projects_tv = QTreeView()
        self.projects_tv.setRootIsDecorated(False)
        self.projects_tv.setModel(self.projects_model)
        self.projects_tv.setSortingEnabled(True)
        self.projects_tv.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)

        visibility_header = VisibilityHeader(self.projects_model, self.projects_tv)
        self.projects_tv.setHeader(visibility_header)

        header = self.projects_tv.header()
        header.setSortIndicatorShown(True)
        header.setSectionsMovable(False)
        header.sortIndicatorChanged.connect(self.on_sort_changed)

        avatar_delegate = ContributorAvatarsDelegate(self.projects_tv)
        self.projects_tv.setItemDelegateForColumn(_COL_CONTRIBUTORS, avatar_delegate)

        self.projects_tv.clicked.connect(self.on_item_clicked)

        viewport_layout = QVBoxLayout(self.projects_tv.viewport())
        viewport_layout.setContentsMargins(0, 0, 0, 0)
        self.empty_label = QLabel("No projects found")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.hide()
        viewport_layout.addWidget(self.empty_label)

        top_layout = QHBoxLayout()
        top_layout.addWidget(self.filter_bar)
        top_layout.addWidget(self.refresh_btn)

        button_box = QDialogButtonBox()
        button_box.setStandardButtons(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(top_layout)
        layout.addWidget(self.projects_tv)
        layout.addWidget(button_box)
        self.setLayout(layout)

        header.blockSignals(True)
        header.setSortIndicator(_COL_LAST_ACTIVITY, Qt.SortOrder.DescendingOrder)
        header.blockSignals(False)

    def build_filter_params(self) -> dict:
        filters = self.filter_bar.get_filters()
        filter_params = {}
        if filters.get("name"):
            filter_params["search"] = filters["name"]
        if filters.get("who"):
            filter_params["project_user_id"] = filters["who"]
        return filter_params

    def fetch_and_populate(self):
        """Fetch matching projects from the API and load into the model."""
        try:
            response = get_tenant_projects(params=self.build_filter_params())
        except NetworkUnavailableError:
            self.error_signals.connection_lost.emit()
            self.reject()
            return
        except RanaFetchError as e:
            self.error_signals.fetch_error_occurred.emit(str(e), True)
            self.reject()
            return

        self._all_projects = self._with_contributors_data(response.get("items", []))
        self._last_toggled_row = None
        self.projects_model.load_projects(
            self._all_projects, self._sort_column, self._sort_order
        )
        self.empty_label.setVisible(self.projects_model.rowCount() == 0)
        self.resize_columns()
        self.populate_contributors(self._all_projects)
        all_contributors = {
            c["id"]: c for p in self._all_projects for c in p.get("contributors", [])
        }
        self.loader.fetch_avatars(list(all_contributors.values()))

    def on_avatar_updated(self, user_id: str, avatar: QPixmap) -> None:
        """Refresh contributor data in rows and combo when a real avatar arrives."""
        for project in self._all_projects:
            for entry in project.get("_contributors_data", []):
                if entry["id"] == user_id:
                    entry["avatar"] = avatar
        self.filter_bar.update_combo_avatar("who", user_id, avatar)
        if self.projects_model.rowCount() > 0:
            top = self.projects_model.index(0, _COL_CONTRIBUTORS)
            bottom = self.projects_model.index(
                self.projects_model.rowCount() - 1, _COL_CONTRIBUTORS
            )
            self.projects_model.dataChanged.emit(
                top, bottom, [Qt.ItemDataRole.UserRole]
            )

    def _with_contributors_data(self, projects: list[dict]) -> list[dict]:
        """Attach pre-built contributor display data to each project dict."""
        for project in projects:
            contributors_data = []
            for i, contributor in enumerate(project.get("contributors", [])):
                avatar: QPixmap | None = (
                    self.avatar_cache.get_avatar_for_user(contributor)
                    if i < 3
                    else None
                )
                contributors_data.append(
                    {
                        "id": contributor["id"],
                        "name": f"{contributor['given_name']} {contributor['family_name']}",
                        "avatar": avatar,
                    }
                )
            project["_contributors_data"] = contributors_data
        return projects

    def resize_columns(self):
        header = self.projects_tv.header()
        for i in range(header.count()):
            self.projects_tv.resizeColumnToContents(i)
        self.projects_tv.setColumnWidth(_COL_NAME, 300)

    def on_filters_changed(self, _filters: dict):
        self.fetch_and_populate()

    def on_sort_changed(self, column_index: int, order: Qt.SortOrder):
        if column_index in (_COL_VISIBLE, _COL_CONTRIBUTORS):
            return
        self._sort_column = column_index
        self._sort_order = order
        self.projects_model.load_projects(
            self._all_projects, self._sort_column, self._sort_order
        )
        self.resize_columns()

    def on_item_clicked(self, index: QModelIndex):
        """Support Shift+click for range toggling on the checkbox column."""
        if index.column() != _COL_VISIBLE:
            return
        row = index.row()
        modifiers = QApplication.keyboardModifiers()
        if (
            modifiers & Qt.KeyboardModifier.ShiftModifier
            and self._last_toggled_row is not None
        ):
            new_state = self.projects_model.data(index, Qt.ItemDataRole.CheckStateRole)
            start = min(self._last_toggled_row, row)
            end = max(self._last_toggled_row, row)
            for r in range(start, end + 1):
                self.projects_model.setData(
                    self.projects_model.index(r, _COL_VISIBLE),
                    new_state,
                    Qt.ItemDataRole.CheckStateRole,
                )
        self._last_toggled_row = row

    def populate_contributors(self, projects: list):
        all_contributors = {
            contributor["id"]: contributor
            for project in projects
            for contributor in project.get("contributors", [])
        }
        try:
            my_id = get_user_info().get("sub")
            if my_id and my_id in all_contributors:
                my_user = [all_contributors.pop(my_id)]
        except RanaFetchError:
            my_id = None
            my_user = []
        sorted_users = my_user + sorted(
            all_contributors.values(),
            key=lambda x: f"{x['given_name']} {x['family_name']}".lower(),
        )
        combo_items = []
        for user in sorted_users:
            display_name = f"{user['given_name']} {user['family_name']}"
            if user["id"] == my_id:
                display_name += " (You)"
            avatar = self.avatar_cache.get_avatar_for_user(user)
            combo_items.append((display_name, user["id"], avatar))
        self.filter_bar.set_combo_items("who", combo_items)

    def accept(self):
        self.disconnect_avatar_updated()
        shown_ids = {p["id"] for p in self._all_projects}
        preserved = self._hidden_ids - shown_ids
        set_hidden_projects(
            base_url(), get_tenant_id(), self.projects_model.hidden_ids() | preserved
        )
        super().accept()

    def reject(self):
        self.disconnect_avatar_updated()
        super().reject()

    def disconnect_avatar_updated(self):
        try:
            self.loader.avatar_updated.disconnect(self.on_avatar_updated)
        except TypeError:
            pass
