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
from rana_qgis_plugin.utils_api import get_publication_files
from rana_qgis_plugin.utils_time import format_activity_timestamp_str
from rana_qgis_plugin.widgets.utils_icons import get_icon_from_theme, get_icon_label


class PublicationView(QWidget):
    # TODO: monitor / update

    def __init__(self, communication, avatar_cache, parent=None):
        super().__init__(parent)
        self.communication = communication
        self.avatar_cache = avatar_cache
        self.project: Optional[dict] = None
        self.project_id: Optional[int] = None
        self.publication: Optional[dict] = None
        self.setup_ui()

    def setup_ui(self):
        self.general_box = QgsCollapsibleGroupBox("General")
        self.general_box.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum
        )
        self.general_box.setAlignment(Qt.AlignTop)
        self.general_box.setContentsMargins(0, 0, 0, 0)
        # TODO handle column sizing (see PUblicationsBrowser)
        self.maps_box = QgsCollapsibleGroupBox("Maps")
        self.maps_tv = QTreeView()
        self.maps_model = QStandardItemModel()
        self.maps_tv.setModel(self.maps_model)
        self.maps_model.setColumnCount(2)
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
        self.project_id = publication["project_id"]

    def show_details(self, publication: dict):
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
        # TODO: handle very long descriptions
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

    def update_maps_box(self):
        files = get_publication_files(self.communication, self.publication["id"])[
            "items"
        ]
        from qgis.core import Qgis, QgsMessageLog

        QgsMessageLog.logMessage(f"{files=}", "DEBUG", Qgis.Info)
        self.maps_model.clear()
        self.maps_model.setHorizontalHeaderLabels(["Name", "Type", "", ""])
        # TODO: consider layers
        for file in files:
            file_icon = get_icon_from_theme(
                get_file_icon_name(file["file"]["data_type"])
            )
            name_item = QStandardItem(file_icon, file["name"])
            hoover_text = file["file"]["id"]
            name_item.setData(hoover_text, Qt.ToolTipRole)
            data_type_item = QStandardItem(
                SUPPORTED_DATA_TYPES.get(
                    file["file"]["data_type"], file["file"]["data_type"]
                )
            )
            open_btn = self.get_buttom_item("Open in QGIS")
            save_btn = self.get_buttom_item("Save style to Rana")
            self.maps_model.appendRow(
                [name_item, data_type_item, QStandardItem(""), QStandardItem("")]
            )
            # TODO: connect these buttons!!!!!
            self.maps_tv.setIndexWidget(
                self.maps_model.index(self.maps_model.rowCount() - 1, 2), open_btn
            )
            self.maps_tv.setIndexWidget(
                self.maps_model.index(self.maps_model.rowCount() - 1, 3), save_btn
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
