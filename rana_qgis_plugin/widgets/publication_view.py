from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from qgis.gui import QgsCollapsibleGroupBox
from qgis.PyQt.QtCore import (
    QSettings,
    Qt,
    pyqtSignal,
)
from qgis.PyQt.QtGui import (
    QColor,
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
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from rana_qgis_plugin.constant import SUPPORTED_DATA_TYPES
from rana_qgis_plugin.utils import get_file_icon_name
from rana_qgis_plugin.utils_api import (
    get_publication_details,
    get_publication_version_files,
    get_publication_version_latest,
    get_tenant_file_descriptor,
)
from rana_qgis_plugin.utils_time import format_activity_timestamp_str
from rana_qgis_plugin.widgets.utils_icons import get_icon_from_theme, get_icon_label


class MapItemType(Enum):
    LAYER = "layer"
    FOLDER = "folder"


@dataclass(frozen=True)
class MapItemData:
    name: str


@dataclass(frozen=True)
class FolderItemData(MapItemData):
    """Data class to hold data about a folder in the map"""

    sub_items: list[MapItemData]


@dataclass(frozen=True)
class LayerItemData(MapItemData):
    """Data class to hold data about a layer in the map"""

    data_type: str
    file: dict
    file_descriptor: dict
    layer_in_file: Optional[dict] = None


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

    def __init__(self, communication, avatar_cache, parent=None):
        super().__init__(parent)
        self.communication = communication
        self.avatar_cache = avatar_cache
        self.project: Optional[dict] = None
        self.publication: Optional[dict] = None
        self.current_version: Optional[dict] = None
        self.project: Optional[dict] = None
        self.file_map: Optional[dict[str:dict]] = None
        self.root_item: FolderItemData = FolderItemData(name="root", sub_items=[])
        self.setup_ui()

    def setup_ui(self):
        self.general_box = QgsCollapsibleGroupBox("General")
        self.general_box.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding
        )
        self.general_box.setAlignment(Qt.AlignTop)
        self.general_box.setContentsMargins(0, 0, 0, 0)
        self.maps_box = QgsCollapsibleGroupBox("Maps")
        self.maps_box.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding
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
        btn_open.clicked.connect(lambda: self.open_all_maps)
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
        self.update_publication(self.publication["id"])

    def update_publication(self, publication_id: str):
        self.publication = get_publication_details(publication_id)
        if not self.publication:
            self.communication.show_warn("Cannot find loaded publication")
            self.show_failed.emit()
            return
        self.current_version = get_publication_version_latest(self.publication["id"])
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
        self.project = project
        self.update_publication(publication_id)
        if self.publication:
            self.update_general_box()
            self.update_maps_box()
            self.show_success.emit(self.publication["name"])

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

    def open_all_maps(self):
        self.open_maps(self.root_item)

    def open_in_rana(self):
        self.communication.show_info("Open in Rana is not yet implemented.")
        pass

    def open_maps(self, map_item: MapItemData):
        # TODO: recurse through map_item and open stuff
        self.communication.show_info("Opening maps is not yet implemented.")
        pass

    def save_styles(self, map_item: MapItemData):
        # TODO: recurse through map_item and save styles
        self.communication.show_info("Saving styles is not yet implemented.")
        pass

    def get_button_container(self, map_item: MapItemData) -> QWidget:
        open_btn = QPushButton("Open in QGIS")
        open_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        open_btn.clicked.connect(lambda: self.open_maps(map_item))
        save_btn = QPushButton("Save style to Rana")
        save_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        save_btn.clicked.connect(lambda: self.open_maps(map_item))
        btn_container = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(open_btn)
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

    def collect_map_data(self, layers) -> list[MapItemData]:
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
                if file.get("data_type", "") in ["scenario", "vector"]:
                    layers_in_file = (file_descriptor.get("meta") or {}).get(
                        "layers", []
                    )
                    # TODO: make sure slayer_in_file refers to id!!!
                    layer_in_file = next(
                        (
                            layers["id"] == layer["layer_in_file"]
                            for layers in layers_in_file
                        ),
                        None,
                    )
                else:
                    layer_in_file = None
                data_type = file.get("data_type", "")
                if data_type == "vector":
                    data_type = (file_descriptor.get("meta") or {}).get(
                        "type", data_type
                    )
                # Collect data needed for UI and to open and edit the layer
                map_data.append(
                    LayerItemData(
                        name=layer["name"],
                        data_type=data_type,
                        layer_in_file=layer_in_file,
                        file=file,
                        file_descriptor=file_descriptor,
                    )
                )
            elif layer.get("type") == "folder":
                map_data.append(
                    FolderItemData(
                        name=layer["name"],
                        sub_items=self.collect_map_data(layer.get("layers", [])),
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
                if tooltip:
                    layer_item.setToolTip(tooltip)
                parent_item.appendRow(
                    [layer_item, QStandardItem(data_type_str), QStandardItem()]
                )
                # TODO: only add buttons for compatible files!!
                btn_container = self.get_button_container(map_item)
                self.add_buttons_to_row(btn_container, parent_item)
            elif isinstance(map_item, FolderItemData):
                # TODO: add button tooltip to make clear only compatible items are included
                folder_item = QStandardItem(map_item.name)
                parent_item.appendRow([folder_item, QStandardItem(), QStandardItem()])
                btn_container = self.get_button_container(map_item)
                self.add_buttons_to_row(btn_container, parent_item)
                parent_index = self.maps_model.indexFromItem(parent_item)
                folder_index = parent_index.child(parent_item.rowCount() - 1, 0)
                self.maps_tv.expand(folder_index)
                # Recurse for nested layers in the folder
                self.add_map_layers(folder_item, map_item.sub_items)

    def update_maps_box(self):
        # TODO: freeze UI or load on the fly / load on the fly / open before loading
        self.maps_model.clear()
        self.maps_model.setHorizontalHeaderLabels(["Name", "Type", ""])
        all_maps = [
            FolderItemData(
                publication_map["name"],
                self.collect_map_data(publication_map.get("layers", [])),
            )
            for publication_map in self.current_version.get("maps", [])
        ]
        self.root_item = FolderItemData("root", all_maps)
        # for map_item in self.publication_maps:
        for map_item in self.root_item.sub_items:
            name_item = QStandardItem(map_item.name)
            bold_font = QFont()
            bold_font.setBold(True)
            name_item.setFont(bold_font)
            self.maps_model.appendRow([name_item, QStandardItem(), QStandardItem()])
            btn_container = self.get_button_container(
                FolderItemData(name=map_item.name, sub_items=map_item.sub_items)
            )
            self.add_buttons_to_row(btn_container)
            self.add_map_layers(name_item, map_item.sub_items)
            map_index = self.maps_model.indexFromItem(name_item)
            self.maps_tv.expand(map_index)
        self.maps_tv.resize_columns_aware_of_collapsed_items()
