from typing import Optional

from qgis.gui import QgsCollapsibleGroupBox
from qgis.PyQt.QtCore import (
    QSettings,
    Qt,
    pyqtSignal,
)
from qgis.PyQt.QtGui import QColor, QIcon, QPalette, QStandardItem, QStandardItemModel
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
    get_project_file_details,
    get_publication_version_files,
    get_publication_version_latest,
    get_tenant_file_descriptor,
)
from rana_qgis_plugin.utils_time import format_activity_timestamp_str
from rana_qgis_plugin.widgets.utils_icons import get_icon_from_theme, get_icon_label


class PublicationView(QWidget):
    # TODO: monitor / update
    # TODO: breadcurmbs

    def __init__(self, communication, avatar_cache, parent=None):
        super().__init__(parent)
        self.communication = communication
        self.avatar_cache = avatar_cache
        self.project: Optional[dict] = None
        self.publication: Optional[dict] = None
        self.current_version: Optional[dict] = None
        self.project: Optional[dict] = None
        self.file_map: Optional[dict[str:dict]] = None
        self.setup_ui()

    def setup_ui(self):
        self.general_box = QgsCollapsibleGroupBox("General")
        self.general_box.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding
        )
        self.general_box.setAlignment(Qt.AlignTop)
        self.general_box.setContentsMargins(0, 0, 0, 0)
        self.maps_box = QgsCollapsibleGroupBox("Maps")
        self.maps_model = QStandardItemModel()
        self.maps_tv = QTreeView()
        self.maps_tv.setEditTriggers(QTreeView.NoEditTriggers)
        self.maps_tv.setModel(self.maps_model)
        self.maps_tv.setUniformRowHeights(False)
        self.maps_tv.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.maps_tv.setSortingEnabled(False)
        self.maps_tv.header().setSectionsMovable(False)
        self.maps_tv.header().setStretchLastSection(False)
        self.maps_model.setColumnCount(4)
        self.maps_model.setHorizontalHeaderLabels(["Name", "Type", "", ""])
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
        collapsible_layout.addStretch()
        # make container scrollable
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(collapsible_container)

        button_layout = QHBoxLayout()
        btn_open = QPushButton("Open all maps in QGIS")
        btn_rana = QPushButton("Open publication in Rana (web)")
        button_layout.addWidget(btn_open)
        button_layout.addWidget(btn_rana)

        # Put scroll area in layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll_area)
        layout.addLayout(button_layout)
        self.setLayout(layout)

    def update_publication(self, publication: dict):
        self.publication = publication
        self.current_version = get_publication_version_latest(self.publication["id"])
        self.file_map = {
            item["file"]["id"]: item["file"]
            for item in get_publication_version_files(
                self.publication["id"], self.current_version["version"]
            )["items"]
        }

    def show_details(self, project: dict, publication: dict):
        self.project = project
        self.update_publication(publication)
        self.update_general_box()
        self.update_maps_box()

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
        if self.publication["description"]:
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
        layout.addStretch()
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

    def add_buttons_to_row(self, parent_item):
        open_btn = self.get_buttom_item("Open in QGIS")
        save_btn = self.get_buttom_item("Save style to Rana")
        child_row_index = parent_item.index().child(
            parent_item.rowCount() - 1,  # Child row is the last added
            0,  # Always reference the first column
        )
        # TODO: connect!!
        self.maps_tv.setIndexWidget(
            child_row_index.sibling(child_row_index.row(), 2), open_btn
        )
        self.maps_tv.setIndexWidget(
            child_row_index.sibling(child_row_index.row(), 3), save_btn
        )

    def add_map_layers(self, parent_item, layers):
        """
        Recursive function to process layers and groups,
        and add them to the parent item.
        """
        # TODO: seperate collecting data and populating model
        for layer in layers:
            if layer.get("type") == "layer":
                file = self.file_map.get(layer["layer_in_file"])
                if not file:
                    continue
                data_type = file.get("data_type", "")
                file_icon = get_icon_from_theme(get_file_icon_name(data_type))
                file_item = QStandardItem(file_icon, layer["name"])
                file_item.setToolTip(file["id"])
                parent_item.appendRow(
                    [
                        file_item,
                        QStandardItem(SUPPORTED_DATA_TYPES.get(data_type, data_type)),
                        QStandardItem(),
                        QStandardItem(),
                    ]
                )
                self.add_buttons_to_row(parent_item)
                file_descriptor = get_tenant_file_descriptor(file["descriptor_id"])
                if not file_descriptor:
                    continue
                for file_layer in file_descriptor.get("meta", {}).get("layers", []):
                    # TODO: support more types
                    # Geometry types: "Point", "LineString", "Polygon", "MultiPoint", "MultiLineString", "MultiPolygon", "GeometryCollection".
                    layer_icon = get_icon_from_theme(
                        get_file_icon_name(file_layer.get("type", ""))
                    )
                    layer_item = QStandardItem(layer_icon, file_layer["name"])
                    file_item.appendRow(
                        [
                            layer_item,
                            QStandardItem(file_layer.get("type", "")),
                            QStandardItem(),
                            QStandardItem(),
                        ]
                    )
                    self.add_buttons_to_row(file_item)
            elif layer.get("type") == "group":
                group_item = QStandardItem(layer["name"])
                parent_item.appendRow(
                    [
                        group_item,
                        QStandardItem(),
                        QStandardItem(),
                        QStandardItem(),
                    ]
                )
                parent_index = self.maps_model.indexFromItem(parent_item)
                group_index = parent_index.child(parent_item.rowCount() - 1, 0)
                self.maps_tv.expand(group_index)
                # Recurse for nested layers in the group
                self.add_map_layers(group_item, layer.get("layers", []))

    def update_maps_box(self):
        maps = self.current_version.get("maps", [])
        self.maps_model.clear()
        self.maps_model.setHorizontalHeaderLabels(["Name", "Type", "", ""])
        for map in maps:
            # TODO: make bold
            name_item = QStandardItem(map["name"])
            self.maps_model.appendRow(
                [name_item, QStandardItem(), QStandardItem(), QStandardItem()]
            )
            map_index = self.maps_model.indexFromItem(name_item)
            self.maps_tv.expand(map_index)
            self.add_map_layers(name_item, map.get("layers", []))
        self.maps_tv.header().setSectionResizeMode(0, QHeaderView.Stretch)
        for col in range(1, self.maps_model.columnCount()):
            self.maps_tv.header().setSectionResizeMode(
                col, QHeaderView.ResizeToContents
            )

    @staticmethod
    def get_buttom_item(label: str, func=None, tooltip: str = None) -> QWidget:
        btn = QPushButton(label)
        btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        if func:
            btn.clicked.connect(func)
        if tooltip:
            btn.setToolTip(tooltip)
        container = QWidget()
        container.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(btn)
        container.adjustSize()
        return container
