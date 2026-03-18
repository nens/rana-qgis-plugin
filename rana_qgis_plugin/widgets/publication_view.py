from dataclasses import dataclass
from enum import Enum
from functools import cached_property
from typing import Optional

from qgis.core import Qgis, QgsMessageLog
from qgis.gui import QgsCollapsibleGroupBox
from qgis.PyQt.QtCore import QAbstractItemModel, QSettings, Qt, QUrl, pyqtSignal
from qgis.PyQt.QtGui import (
    QColor,
    QDesktopServices,
    QFont,
    QIcon,
    QPalette,
    QStandardItem,
    QStandardItemModel,
)
from qgis.PyQt.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTableView,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from rana_qgis_plugin.constant import SUPPORTED_DATA_TYPES
from rana_qgis_plugin.utils import get_file_icon_name
from rana_qgis_plugin.utils_api import (
    get_publication_details,
    get_publication_version_details,
    get_publication_version_files,
    get_publication_version_latest,
    get_tenant_file_descriptor,
    get_tenant_id,
)
from rana_qgis_plugin.utils_settings import base_url
from rana_qgis_plugin.utils_time import format_activity_timestamp_str
from rana_qgis_plugin.widgets.utils_file_action import (
    FileAction,
    get_file_actions_by_data_type,
)
from rana_qgis_plugin.widgets.utils_icons import get_icon_from_theme, get_icon_label
from rana_qgis_plugin.widgets.utils_qviews import update_width_with_wrapping


class MapItemType(Enum):
    LAYER = "layer"
    FOLDER = "folder"


@dataclass
class MapItemData:
    name: str
    parents: list[str]

    @property
    def support_open(self) -> bool:
        return False

    @property
    def support_save(self) -> bool:
        return False


@dataclass
class FolderItemData(MapItemData):
    """Data class to hold data about a folder in the map"""

    sub_items: list[MapItemData]
    _support_save: bool = False
    _support_open: bool = False
    _support_flags_set: bool = False

    def set_support_flags(self):
        """
        Recursively compute or update the support_open and support_save flags
        for this folder and its sub-items.
        """
        if self._support_flags_set:
            return

        for item in self.sub_items:
            if isinstance(item, FolderItemData):
                item.set_support_flags()

        # Compute current folder's flags based on its sub-items
        self._support_open = any(item.support_open for item in self.sub_items)
        self._support_save = any(item.support_save for item in self.sub_items)

        # Mark this folder as computed
        self._support_flags_set = True

    @property
    def support_open(self) -> bool:
        return self._support_open

    @property
    def support_save(self) -> bool:
        return self._support_save


@dataclass
class LayerItemData(MapItemData):
    """Data class to hold data about a layer in the map"""

    data_type: str
    file: dict
    file_descriptor: dict
    type_in_file: Optional[str] = None
    layer_in_file: Optional[dict] = None

    @cached_property
    def supported_actions(self) -> list[FileAction]:
        return get_file_actions_by_data_type(self.type_in_file or self.data_type)

    @property
    def support_open(self) -> bool:
        return (
            FileAction.OPEN_IN_QGIS in self.supported_actions
        ) or self.data_type == "scenario"

    @property
    def support_save(self) -> bool:
        return (
            FileAction.SAVE_RASTER_STYLING in self.supported_actions
            or FileAction.SAVE_VECTOR_STYLING in self.supported_actions
        )


class PublicationMapsTreeView(QTreeView):
    def __init__(self, parent=None):
        super().__init__(parent)

    def resize_columns_aware_of_collapsed_items(self):
        """
        Resize columns to fit their contents, including collapsed items.
        """
        # Save current collapsed status
        expanded_states = {}
        for row in range(self.model().rowCount()):
            self._save_expanded_states(self.model().index(row, 0), expanded_states)
        # Temporarily expand all items
        for row in range(self.model().rowCount()):
            self._expand_all_items(self.model().index(row, 0))
        # Resize columns to fit *all items*, including collapsed ones
        for col in range(self.model().columnCount()):
            self.resizeColumnToContents(col)
        # Restore the original collapsed state
        for row in range(self.model().rowCount()):
            self._restore_expanded_states(self.model().index(row, 0), expanded_states)

    def _save_expanded_states(self, index, expanded_states):
        """
        Recursively save the expanded/collapsed state of all items.
        """
        if not index.isValid():
            return
        expanded_states[index] = self.isExpanded(index)
        for row in range(index.model().rowCount(index)):
            self._save_expanded_states(index.child(row, 0), expanded_states)

    def _expand_all_items(self, index):
        """
        Recursively expand all items in the tree view.
        """
        if not index.isValid():
            return
        self.setExpanded(index, True)
        for row in range(index.model().rowCount(index)):
            self._expand_all_items(index.child(row, 0))

    def _restore_expanded_states(self, index, expanded_states):
        """
        Recursively restore the expanded/collapsed state of items.
        """
        if not index.isValid():
            return
        if index in expanded_states:
            self.setExpanded(index, expanded_states[index])
        for row in range(index.model().rowCount(index)):
            self._restore_expanded_states(index.child(row, 0), expanded_states)


class PublicationView(QWidget):
    show_failed = pyqtSignal()
    show_success = pyqtSignal(str)
    open_in_qgis = pyqtSignal(dict, list, str)

    def __init__(self, communication, avatar_cache, parent=None):
        super().__init__(parent)
        self.no_refresh = False
        self.communication = communication
        self.avatar_cache = avatar_cache
        self.project: Optional[dict] = None
        self.publication: Optional[dict] = None
        self.current_version: Optional[dict] = None
        self.project: Optional[dict] = None
        self.file_map: Optional[dict[str:dict]] = None
        self.root_item: FolderItemData = FolderItemData(
            name="root", sub_items=[], parents=[]
        )
        self.setup_ui()

    def setup_ui(self):
        self.general_box = QgsCollapsibleGroupBox("General")
        self.general_box.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum
        )
        self.general_box.setAlignment(Qt.AlignTop)
        self.general_box.setContentsMargins(0, 0, 0, 0)
        self.general_box.setMaximumHeight(0)

        self.maps_box = QgsCollapsibleGroupBox("Maps")
        self.maps_box.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
        )
        self.maps_model = QStandardItemModel()
        self.maps_tv = PublicationMapsTreeView()
        self.maps_tv.setEditTriggers(QTreeView.NoEditTriggers)
        self.maps_tv.setModel(self.maps_model)
        self.maps_tv.setUniformRowHeights(True)
        self.maps_tv.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.maps_tv.setSortingEnabled(False)
        self.maps_tv.header().setSectionResizeMode(QHeaderView.Interactive)
        self.maps_tv.header().setSectionsMovable(False)
        self.maps_tv.header().setStretchLastSection(False)
        self.maps_model.setColumnCount(3)
        self.maps_model.setHorizontalHeaderLabels(["Name", "Type", ""])
        maps_layout = QVBoxLayout()
        maps_layout.addWidget(self.maps_tv)
        self.maps_box.setLayout(maps_layout)
        # put all collabpsibles in a container, this seems to help with correct spacing
        collapsible_container = QWidget()
        collapsible_layout = QVBoxLayout(collapsible_container)
        collapsible_layout.setContentsMargins(0, 0, 0, 0)
        collapsible_layout.setSpacing(0)
        collapsible_layout.addWidget(self.general_box)
        collapsible_layout.addWidget(self.maps_box)
        # make container scrollable
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(collapsible_container)

        button_layout = QHBoxLayout()
        btn_open = QPushButton("Open all maps in QGIS")
        btn_open.clicked.connect(lambda _: self.open_maps(self.root_item))
        btn_rana = QPushButton("Open publication in Rana (web)")
        btn_rana.clicked.connect(lambda: self.open_in_rana())
        button_layout.addWidget(btn_open)
        button_layout.addWidget(btn_rana)

        # Put scroll area in layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll_area)
        layout.addLayout(button_layout)
        self.setLayout(layout)

    def refresh(self):
        self.show_details(self.project, self.publication["id"])

    def update_publication(self, publication_id: str):
        self.publication = get_publication_details(publication_id)
        if not self.publication:
            self.communication.show_warn("Cannot find loaded publication")
            self.show_failed.emit()
            return
        latest_publication = get_publication_version_latest(self.publication["id"])
        if latest_publication:
            self.current_version = get_publication_version_details(
                self.publication["id"], latest_publication["version"]
            )
        if self.current_version:
            self.file_map = {
                item["file"]["id"]: item["file"]
                for item in get_publication_version_files(
                    self.publication["id"], self.current_version["version"]
                )["items"]
            }
        else:
            self.current_version = {}
            self.file_map = {}

    def show_details(self, project: dict, publication_id: str):
        if self.no_refresh:
            return
        self.no_refresh = True
        self.current_version = None
        self.project = project
        self.update_publication(publication_id)
        if self.publication:
            self.update_general_box()
            self.update_maps_box()
            self.show_success.emit(self.publication["name"])
        else:
            self.communication.show_warn("Cannot find selected publication")
            self.show_failed.emit()
        self.no_refresh = False

    def update_general_box(self):
        # collect all contents as a list of layouts
        contents = []
        # name; created: date
        layout = QVBoxLayout()
        name_label = QLabel(self.publication["name"])
        name_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(name_label)
        name_label.setWordWrap(True)
        layout.addWidget(
            QLabel(
                f"Created: {format_activity_timestamp_str(self.publication['created_at'])}"
            )
        )
        contents.append(layout)
        # description
        layout = QVBoxLayout()
        if self.publication.get("description"):
            description_label = QLabel(self.publication["description"])
        else:
            description_label = QLabel("No description available")
            description_label.setStyleSheet("font-style: italic;")
        description_label.setWordWrap(True)
        layout.addWidget(description_label)
        contents.append(layout)
        # user: avatar - username - last edit
        layout = QHBoxLayout()
        user_icon_label = get_icon_label(
            self.avatar_cache.get_avatar_for_user(self.publication["creator"])
        )
        user_name_label = QLabel(
            self.publication["creator"]["given_name"]
            + " "
            + self.publication["creator"]["family_name"]
        )
        layout.addWidget(user_icon_label)
        layout.addWidget(user_name_label)
        layout.addWidget(
            QLabel(format_activity_timestamp_str(self.publication["updated_at"]))
        )
        contents.append(layout)

        # Collect all contents in a frame with horizontal seperators
        container = QWidget(self.general_box)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        frame = QFrame()
        frame.setFrameStyle(QFrame.NoFrame)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(0)
        layout.addWidget(frame)
        for framed_layout in contents:
            section_widget = QWidget()  # Wrap each framed layout in a widget
            section_widget.setLayout(framed_layout)
            frame_layout.addWidget(section_widget)
            frame_layout.setContentsMargins(0, 0, 0, 0)
            frame_layout.setSpacing(0)
            if framed_layout != contents[-1]:
                line = QFrame()
                line.setFrameStyle(QFrame.HLine | QFrame.Sunken)
                frame_layout.addWidget(line)
        # assign existing layout to temporary widget
        # this will be deleted once the scope of this method is over
        if self.general_box.layout():
            QWidget().setLayout(self.general_box.layout())
        self.general_box.setLayout(layout)
        self.general_box.setCollapsed(False)

    def open_in_rana(self):
        link = f"{base_url()}/{get_tenant_id()}/projects/{self.project['slug']}?tab=3&publication={self.publication['id']}"
        QDesktopServices.openUrl(QUrl(link))

    def open_map(self, map_item: LayerItemData):
        if map_item.data_type == "raster":
            self.open_in_qgis.emit(
                map_item.file, map_item.parents + [map_item.name], ""
            )
        elif map_item.data_type == "vector" and map_item.layer_in_file:
            self.open_in_qgis.emit(
                map_item.file,
                map_item.parents + [map_item.name],
                map_item.layer_in_file,
            )
        QgsMessageLog.logMessage(
            f"Found layer: {map_item.name} of type {map_item.data_type} which is not supported yet",
            "DEBUG",
            Qgis.Info,
        )

    def open_maps(self, map_item: MapItemData):
        # TODO: consider batch download and open
        # - single file: open -> move to open_map
        # - multiple files: download first, than open
        self.communication.show_info("Opening multiple map is not yet supported")
        # if isinstance(map_item, LayerItemData):
        #     self.open_map(map_item)
        # elif isinstance(map_item, FolderItemData):
        #     for sub_item in map_item.sub_items:
        #         self.open_maps(sub_item)

    def save_styles(self, map_item: MapItemData):
        # TODO: recurse through map_item and save styles
        self.communication.show_info("Saving styles is not yet implemented.")
        pass

    def get_button_container(
        self,
        map_item: MapItemData,
    ) -> QWidget:
        btn_container = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        if map_item.support_open:
            open_btn = QPushButton("Open in QGIS")
            open_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Minimum)
            if isinstance(map_item, FolderItemData):
                open_btn.clicked.connect(lambda: self.open_maps(map_item))
            else:
                open_btn.clicked.connect(lambda: self.open_map(map_item))
            layout.addWidget(open_btn)
        layout.addStretch()
        if map_item.support_save:
            save_btn = QPushButton("Save style to Rana")
            save_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Minimum)
            save_btn.clicked.connect(lambda: self.save_styles(map_item))
            layout.addWidget(save_btn)
        btn_container.setLayout(layout)
        return btn_container

    def add_buttons_to_row(
        self, btn_container: QWidget, parent_item: Optional[QStandardItem] = None
    ):
        if parent_item:
            # find last row in parent object
            child_row_index = parent_item.index().child(
                parent_item.rowCount() - 1,  # Child row is the last added
                0,  # Always reference the first column
            )
            child_model_index = child_row_index.sibling(child_row_index.row(), 2)
        else:
            # assume parent is root object and just add to last row
            child_model_index = self.maps_model.index(self.maps_model.rowCount() - 1, 2)
        self.maps_tv.setIndexWidget(child_model_index, btn_container)

    def collect_map_data(self, layers, parents: list[str]) -> list[MapItemData]:
        """
        Recursively collect data from API needed to populate the maps table
        """
        map_data = []
        for layer in layers:
            if layer.get("type") == "layer":
                file = self.file_map.get(layer.get("file_path"))
                if not file:
                    continue
                file_descriptor = get_tenant_file_descriptor(file["descriptor_id"])
                if not file_descriptor:
                    continue
                # For scenario and vector files the layer is extracted from the file
                layer_in_file = None
                type_in_file = None
                data_type = file.get("data_type", "")
                if data_type in ["scenario", "vector"]:
                    layers_in_file = (file_descriptor.get("meta") or {}).get(
                        "layers", []
                    )
                    layer_in_file = next(
                        (
                            layer_in_file["name"]
                            for layer_in_file in layers_in_file
                            if layer_in_file["id"] == layer["layer_in_file"]
                        ),
                        None,
                    )
                    type_in_file = (file_descriptor.get("meta") or {}).get(
                        "type", data_type
                    )
                    if not layer_in_file:
                        # When the layer cannot be matched, something went really wrong in the backend
                        continue
                # Collect data needed for UI and to open and edit the layer
                map_data.append(
                    LayerItemData(
                        name=layer["name"],
                        data_type=data_type,
                        type_in_file=type_in_file,
                        layer_in_file=layer_in_file,
                        file=file,
                        file_descriptor=file_descriptor,
                        parents=parents,
                    )
                )
            elif layer.get("type") == "folder":
                map_data.append(
                    FolderItemData(
                        name=layer["name"],
                        sub_items=self.collect_map_data(
                            layers=layer.get("layers", []),
                            parents=parents + [layer["name"]],
                        ),
                        parents=parents,
                    )
                )

        return map_data

    def add_map_layers(self, parent_item, map_data: list[MapItemData]):
        """
        Recursively add map layers to the maps table
        """
        for map_item in map_data:
            if isinstance(map_item, LayerItemData):
                tooltip = None
                data_type = map_item.data_type
                data_type_str = SUPPORTED_DATA_TYPES.get(data_type, data_type)
                # Create icon - vector layer_icon is set after retrieving layer
                if data_type in ["raster", "scenario"]:
                    layer_icon = get_icon_from_theme(get_file_icon_name("raster"))
                else:
                    layer_icon = get_icon_from_theme(get_file_icon_name(data_type))
                # For scenario and vector files the layer is extracted from the file
                if data_type in ["scenario", "vector"]:
                    tooltip = map_item.file["id"]
                layer_item = QStandardItem(layer_icon, map_item.name)
                layer_item.setData(map_item, Qt.UserRole)
                if tooltip:
                    layer_item.setToolTip(tooltip)
                parent_item.appendRow(
                    [layer_item, QStandardItem(data_type_str), QStandardItem()]
                )
                btn_container = self.get_button_container(map_item)
                self.add_buttons_to_row(btn_container, parent_item)
            elif isinstance(map_item, FolderItemData):
                folder_item = QStandardItem(map_item.name)
                folder_item.setData(map_item, Qt.UserRole)
                parent_item.appendRow([folder_item, QStandardItem(), QStandardItem()])
                btn_container = self.get_button_container(map_item)
                self.add_buttons_to_row(btn_container, parent_item)
                parent_index = self.maps_model.indexFromItem(parent_item)
                folder_index = parent_index.child(parent_item.rowCount() - 1, 0)
                self.maps_tv.expand(folder_index)
                # Recurse for nested layers in the folder
                self.add_map_layers(folder_item, map_item.sub_items)

    def update_maps_box(self):
        self.communication.progress_bar("Loading maps...", clear_msg_bar=True)
        self.maps_model.clear()
        self.maps_model.setHorizontalHeaderLabels(["Name", "Type", ""])
        all_maps = [
            FolderItemData(
                name=publication_map["name"],
                sub_items=self.collect_map_data(
                    layers=publication_map.get("layers"),
                    parents=[self.publication["name"], publication_map["name"]],
                ),
                parents=[self.publication["name"]],
            )
            for publication_map in self.current_version.get("maps", [])
        ]
        self.root_item = FolderItemData(
            name="root", sub_items=all_maps, parents=[self.publication["name"]]
        )
        self.root_item.set_support_flags()
        for map_item in self.root_item.sub_items:
            name_item = QStandardItem(map_item.name)
            bold_font = QFont()
            bold_font.setBold(True)
            name_item.setFont(bold_font)
            self.maps_model.appendRow([name_item, QStandardItem(), QStandardItem()])
            name_item.setData(map_item, Qt.UserRole)
            btn_container = self.get_button_container(map_item)
            self.add_buttons_to_row(btn_container)
            self.add_map_layers(name_item, map_item.sub_items)
            map_index = self.maps_model.indexFromItem(name_item)
            self.maps_tv.expand(map_index)
        self.maps_tv.resize_columns_aware_of_collapsed_items()
        self.communication.clear_message_bar()
        self.update_width()

    def update_width(self):
        update_width_with_wrapping(self.maps_tv, self.maps_model, wrap_column=0)

    def showEvent(self, event):
        super().showEvent(event)
        self.update_width()

    def resizeEvent(self, event):
        """
        Dynamically adjusts the first column's width when the widget is resized.
        """
        super().resizeEvent(event)
        self.update_width()  # Recalculate the widths for dynamic resizing
