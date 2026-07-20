from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

from qgis.core import QgsApplication
from qgis.gui import QgsCollapsibleGroupBox
from qgis.PyQt.QtCore import (
    QSettings,
    Qt,
    QUrl,
    pyqtSignal,
)
from qgis.PyQt.QtGui import (
    QColor,
    QDesktopServices,
    QIcon,
    QStandardItem,
    QStandardItemModel,
)
from qgis.PyQt.QtWidgets import (
    QAction,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTableView,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from rana_qgis_plugin.auth_3di import has_3di_authcfg
from rana_qgis_plugin.communication import UICommunication
from rana_qgis_plugin.constant import SUPPORTED_DATA_TYPES
from rana_qgis_plugin.simulation.threedi_calls import ThreediCalls
from rana_qgis_plugin.utils.api import (
    FileDescriptorStatus,
    get_tenant_file_descriptor,
    get_tenant_project_file,
    get_threedi_schematisation,
    get_user,
)
from rana_qgis_plugin.utils.generic import (
    NumericItem,
    display_bytes,
    get_file_icon_name,
    get_threedi_api,
)
from rana_qgis_plugin.utils.local_paths import (
    get_local_dir_structure,
    get_local_file_path,
    get_local_results_dir_from_meta,
    get_local_schematisation_revision_dir,
)
from rana_qgis_plugin.utils.settings import hcc_working_dir
from rana_qgis_plugin.utils.spatial import get_bbox_area_in_m2
from rana_qgis_plugin.utils.time import (
    format_activity_timestamp,
    format_activity_timestamp_str,
    parse_timestamp_str,
)
from rana_qgis_plugin.widgets.utils_file_action import (
    FileAction,
    FileActionSignals,
    get_file_actions,
    retrieve_url,
)
from rana_qgis_plugin.widgets.utils_icons import (
    get_icon_from_theme_as_pixmap,
    get_icon_label,
)


@dataclass
class FieldValue:
    """A field value that knows whether it was successfully resolved.

    Use ``from_dict`` or ``from_call`` to construct instances so that missing
    data is captured as an error rather than raising an exception.
    """

    value: Any = None
    error: bool = False
    error_msg: str = ""

    @staticmethod
    def from_dict(d: Optional[dict], key: str, default: Any = None) -> "FieldValue":
        """Safely extract *key* from *d*.

        Returns an errored ``FieldValue`` when *d* is ``None`` or *key* is absent.
        """
        if d is None:
            return FieldValue(value=default, error=True, error_msg="Source unavailable")
        if key not in d:
            return FieldValue(
                value=default, error=True, error_msg=f"Missing key: {key}"
            )
        return FieldValue(value=d[key])

    @staticmethod
    def from_call(fn: Callable, *args, **kwargs) -> "FieldValue":
        """Call *fn* and wrap the result.

        Returns an errored ``FieldValue`` when *fn* raises or returns ``None``.
        """
        try:
            result = fn(*args, **kwargs)
        except Exception as e:
            return FieldValue(value=None, error=True, error_msg=str(e))
        if result is None:
            return FieldValue(value=None, error=True, error_msg="API returned None")
        return FieldValue(value=result)


def make_label(
    field_value: FieldValue,
    bold: bool = False,
    expanding: bool = False,
    word_wrap: bool = False,
) -> QLabel:
    # TODO: reconsider tooltips
    """Create a QLabel from a FieldValue, with red styling if errored."""
    text = str(field_value.value) if field_value.value is not None else "N/A"
    if bold:
        text = f"<b>{text}</b>"
    label = QLabel(text)
    if field_value.error:
        label.setStyleSheet("color: rgba(255, 0, 0, 255);")
        label.setToolTip("could not retrieve value")
    if expanding:
        label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Ignored)
    if word_wrap:
        label.setWordWrap(True)
    return label


def log_field_errors(
    communication: UICommunication,
    context: str,
    fields: list,
) -> None:
    """Log field resolution errors via UICommunication.

    API failures (FieldValue.from_call) are logged at error level;
    missing dict keys (FieldValue.from_dict) at warning level.
    """
    for name, fv in fields:
        if not fv.error:
            continue
        msg = f"{context}: {name} — {fv.error_msg}"
        communication.log_info(msg)
        if "API" in fv.error_msg or "returned None" in fv.error_msg:
            communication.log_err(msg)
        else:
            communication.log_warn(msg)


@dataclass
class InfoRow:
    key: str
    value: Any
    key_tooltip: Optional[str] = None
    value_tooltip: Optional[str] = None
    color: Optional[QColor] = None

    @staticmethod
    def get_label_widget(
        value: str, tooltip: Optional[str], color: Optional[QColor], parent
    ) -> QLabel:
        label = QLabel(value, parent=parent)
        # ensure correct size hints for the labels
        label.setMinimumHeight(label.fontMetrics().height() + 4)
        if tooltip:
            label.setToolTip(tooltip)
        if color:
            label.setStyleSheet(
                f"color: rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()});"
            )

        return label

    def get_key_widget(self, parent) -> QLabel:
        return self.get_label_widget(self.key, self.key_tooltip, self.color, parent)

    def get_value_widget(self, parent) -> QLabel:
        if isinstance(self.value, FieldValue):
            str_value = str(self.value.value) if self.value.value is not None else "N/A"
            color = self.color or (QColor(255, 0, 0) if self.value.error else None)
            tooltip = self.value_tooltip or (
                self.value.error_msg if self.value.error else None
            )
            return self.get_label_widget(str_value, tooltip, color, parent)
        if isinstance(self.value, datetime):
            str_value = format_activity_timestamp(self.value)
        elif self.value is None:
            str_value = "N/A"
        elif isinstance(self.value, bool):
            str_value = "Yes" if self.value else "No"
        else:
            str_value = str(self.value)

        return self.get_label_widget(str_value, self.value_tooltip, self.color, parent)


class EditLabel(QLineEdit):
    def __init__(self, text, parent=None, start_editable=False):
        super().__init__(text, parent)
        if start_editable:
            self.make_editable()
        else:
            self.make_readonly()

    def make_editable(self):
        self.setReadOnly(False)
        self.setStyleSheet("")
        self.setFrame(True)

    def make_readonly(self):
        self.setReadOnly(True)
        self.setStyleSheet("""
            QLineEdit {
                background: transparent;
                border: none;
                padding: 0px;
            }
        """)
        self.setFrame(False)


class FileView(QWidget):
    show_revisions_clicked = pyqtSignal(dict, dict)

    def __init__(
        self, communication, file_signals: FileActionSignals, avatar_cache, parent=None
    ):
        super().__init__(parent)
        self.communication = communication
        self.selected_file = None
        self.avatar_cache = avatar_cache
        self.project = None
        self.file_signals = file_signals
        self._active_actions = []
        self.setup_ui()
        self.no_refresh = False
        self.threedi_objects = {}

    @property
    def schematisation(self) -> dict:
        # TODO: elf.threedi_objects["schematisation"] is not cleared properly!
        if self.selected_file["data_type"] == "threedi_schematisation":
            if not "schematisation" in self.threedi_objects:
                self.threedi_objects["schematisation"] = get_threedi_schematisation(
                    self.communication, self.selected_file["descriptor_id"]
                )
            return self.threedi_objects["schematisation"]
        return {}

    @property
    def latest_revision_model(self) -> Optional[Any]:
        if (
            self.selected_file["data_type"] != "threedi_schematisation"
        ) or not has_3di_authcfg():
            return None
        if self.schematisation is None:
            return None
        if "model" not in self.threedi_objects:
            revision = self.schematisation.get("latest_revision")
            if not revision:
                return None
            valid_revision = revision.get("has_threedimodel")
            if not valid_revision:
                return None
            tc = ThreediCalls(get_threedi_api())
            threedi_models = tc.fetch_schematisation_revision_3di_models(
                self.schematisation["schematisation"]["id"], revision["id"]
            )
            self.threedi_objects["model"] = next(
                (
                    model
                    for model in threedi_models
                    if model.is_valid and not model.disabled
                ),
                None,
            )
        return self.threedi_objects["model"]

    def update_project(self, project: dict):
        self.project = project

    def setup_ui(self):
        self.general_box = QgsCollapsibleGroupBox("General")
        self.general_box.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum
        )
        self.general_box.setAlignment(Qt.AlignTop)
        self.general_box.setContentsMargins(0, 0, 0, 0)
        # Set filename_edit, this will be replaced on updating the contents of self.general_box
        self.filename_edit = EditLabel("")
        self.more_box = QgsCollapsibleGroupBox("More information")
        self.files_box = QgsCollapsibleGroupBox("Related files")
        self.files_table = QTableView()
        self.files_table.setSortingEnabled(False)
        self.files_table.verticalHeader().hide()
        self.files_table.setEditTriggers(QTableView.NoEditTriggers)
        self.files_model = QStandardItemModel()
        self.files_table.setModel(self.files_model)
        self.files_model.setColumnCount(3)
        self.files_model.setHorizontalHeaderLabels(["Name", "Type", "Size"])
        self.files_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        files_layout = QVBoxLayout()
        files_layout.addWidget(self.files_table)
        self.files_box.setLayout(files_layout)

        # put all collabpsibles in a container, this seems to help with correct spacing
        collapsible_container = QWidget()
        collapsible_layout = QVBoxLayout(collapsible_container)
        collapsible_layout.setContentsMargins(0, 0, 0, 0)
        collapsible_layout.setSpacing(0)
        collapsible_layout.addWidget(self.general_box)
        collapsible_layout.addWidget(self.more_box)
        collapsible_layout.addWidget(self.files_box)
        collapsible_layout.addStretch()
        # make container scrollable
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(collapsible_container)

        button_layout = QHBoxLayout()
        self.btn_start_simulation = QPushButton("Start Simulation")
        self.btn_create_model = QPushButton("Create Rana Model")
        self.btn_stack = QStackedWidget()
        self.btn_stack.setFixedHeight(self.btn_start_simulation.sizeHint().height())
        self.btn_stack.addWidget(self.btn_start_simulation)
        self.btn_stack.addWidget(self.btn_create_model)
        btn_show_revisions = QPushButton(FileAction.VIEW_REVISIONS.value)
        btn_show_revisions.setIcon(FileAction.VIEW_REVISIONS.icon)
        btn_show_revisions.setToolTip(FileAction.VIEW_REVISIONS.get_tooltip())
        btn_show_revisions.clicked.connect(
            lambda _: self.file_signals.view_all_revisions_requested.emit(
                self.project, self.selected_file
            )
        )
        self.btn_show_revisions = btn_show_revisions
        self.btn_show_revisions.setMinimumSize(self.btn_show_revisions.sizeHint())
        self.btn_show_revisions.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn_show_revisions.hide()
        self.btn_stack.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        button_layout.addWidget(self.btn_stack)
        self.file_action_btn_dict = self.get_file_action_buttons()
        file_action_btn_layout = QHBoxLayout()
        for btn in self.file_action_btn_dict.values():
            file_action_btn_layout.addWidget(btn)
        file_action_btn_layout.addWidget(self.btn_show_revisions)
        self.btn_ellipsis = self._create_ellipsis_button()
        # Match height of the other action buttons, keep width fixed
        reference_btn = next(iter(self.file_action_btn_dict.values()))
        self.btn_ellipsis.setFixedHeight(reference_btn.sizeHint().height())
        self.btn_ellipsis.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        file_action_btn_layout.addWidget(self.btn_ellipsis)

        # Put scroll area in layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll_area)
        layout.addLayout(file_action_btn_layout)
        layout.addLayout(button_layout)
        self.setLayout(layout)

    def toggle_interactions(self, enabled: bool):
        buttons = self.findChildren(QPushButton)
        for button in buttons:
            button.setEnabled(enabled)

    def get_file_action_buttons(self) -> dict[FileAction, QPushButton]:
        top_row_actions = sorted(
            [
                FileAction.OPEN_IN_QGIS,
                FileAction.OPEN_WMS,
                FileAction.DOWNLOAD_RESULTS,
                FileAction.SAVE_REVISION,
                FileAction.SAVE_STYLING,
                FileAction.UPLOAD_FILE,
            ]
        )
        btn_dict = {}
        for action in sorted(top_row_actions):
            btn = QPushButton(action.value)
            btn.setIcon(action.icon)
            btn.setMinimumSize(btn.sizeHint())
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            action_signal = self.file_signals.get_signal(action)
            btn.clicked.connect(
                lambda _, signal=action_signal: signal.emit(self.selected_file)
            )
            # hide buttons by default to prevent big width in size hint
            # update_file_action_buttons ensures buttons are correctly shown on display
            btn.hide()
            btn_dict[action] = btn
        return btn_dict

    def _create_ellipsis_button(self):
        """Create the ellipsis button with a dynamically populated menu."""
        btn = QToolButton()
        btn.setIcon(QgsApplication.getThemeIcon("/mIconHamburgerMenu.svg"))
        btn.setToolTip("More actions")
        btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        btn.setStyleSheet("QToolButton::menu-indicator { image: none; }")
        menu = QMenu()
        btn.setMenu(menu)
        menu.aboutToShow.connect(self._build_ellipsis_menu)
        btn.hide()
        return btn

    def _build_ellipsis_menu(self):
        """Populate the ellipsis menu based on the currently selected file."""
        menu = self.btn_ellipsis.menu()
        menu.clear()
        menu.setToolTipsVisible(True)
        if not self.selected_file:
            return
        data_type = self.selected_file.get("data_type")
        is_schematisation = data_type == "threedi_schematisation"

        # Determine which actions to show in the ellipsis menu
        ellipsis_actions = set()
        ellipsis_actions.add(FileAction.RENAME)
        if not is_schematisation:
            ellipsis_actions.add(FileAction.HISTORY)
            ellipsis_actions.add(FileAction.DELETE)
        if is_schematisation:
            ellipsis_actions.add(FileAction.REMOVE_FROM_PROJECT)
        # Actions that depend on the descriptor / active actions
        for action in (
            FileAction.OPEN_IN_FILE_BROWSER,
            FileAction.OPEN_IN_BROWSER,
            FileAction.EXPORT_GPKG,
        ):
            if action in self._active_actions:
                ellipsis_actions.add(action)

        # Add actions in FileAction enum order
        data_type = self.selected_file.get("data_type") if self.selected_file else None
        for action in sorted(ellipsis_actions):
            menu_action = QAction(action.icon, action.value, menu)
            menu_action.setToolTip(action.get_tooltip(data_type))
            if action == FileAction.RENAME:
                menu_action.triggered.connect(
                    lambda _: self.edit_file_name(self.selected_file)
                )
            elif action in (FileAction.DELETE, FileAction.REMOVE_FROM_PROJECT):
                menu_action.triggered.connect(
                    lambda _: self.file_signals.file_deletion_requested.emit(
                        self.selected_file
                    )
                )
            elif action in (FileAction.HISTORY, FileAction.VIEW_REVISIONS):
                menu_action.triggered.connect(
                    lambda _: self.file_signals.view_all_revisions_requested.emit(
                        self.project, self.selected_file
                    )
                )
            elif action == FileAction.OPEN_IN_FILE_BROWSER:
                menu_action.triggered.connect(lambda _: self.open_in_file_browser())
            elif action == FileAction.OPEN_IN_BROWSER:
                menu_action.triggered.connect(lambda _: self.open_in_browser())
            elif action == FileAction.EXPORT_GPKG:
                menu_action.triggered.connect(
                    lambda _: self.file_signals.export_gpkg_requested.emit(
                        self.selected_file
                    )
                )
            # Add separator before delete/remove
            if action in (FileAction.DELETE, FileAction.REMOVE_FROM_PROJECT):
                menu.addSeparator()
            menu.addAction(menu_action)

    def edit_file_name(self, selected_item: dict):
        current_name = self.filename_edit.text()
        self.no_refresh = True

        def finish_editing():
            self.filename_edit.editingFinished.disconnect(finish_editing)
            self.filename_edit.make_readonly()
            if current_name != self.filename_edit.text():
                self.file_signals.get_signal(FileAction.RENAME).emit(
                    selected_item, self.filename_edit.text()
                )
                self.selected_file["id"] = self.filename_edit.text()
            self.toggle_interactions(True)
            self.no_refresh = False

        self.toggle_interactions(False)
        self.filename_edit.make_editable()

        # Set up single-shot connection
        self.filename_edit.editingFinished.connect(finish_editing)

        # Set focus to the edit field
        self.filename_edit.setFocus()
        self.filename_edit.selectAll()

    def update_file_action_buttons(self, selected_file: dict):
        # For scenarios, fetch the descriptor once and reuse it
        descriptor = None
        if selected_file.get("data_type") == "scenario":
            descriptor = get_tenant_file_descriptor(selected_file["descriptor_id"])
        active_actions = get_file_actions(selected_file, descriptor=descriptor)
        # Resolve local path on demand; exclude action if not available locally
        local_path = self._resolve_local_path(selected_file, descriptor=descriptor)
        if not local_path:
            active_actions = [
                a for a in active_actions if a != FileAction.OPEN_IN_FILE_BROWSER
            ]
        self._active_actions = active_actions
        data_type = selected_file.get("data_type")
        for action in FileAction:
            btn = self.file_action_btn_dict.get(action)
            if not btn:
                continue
            if action in active_actions:
                btn.setToolTip(action.get_tooltip(data_type))
                btn.show()
            else:
                btn.hide()
        self.btn_ellipsis.show()

    def update_selected_file(self, selected_file: dict):
        if self.selected_file != selected_file:
            self.selected_file = selected_file
            self.threedi_objects = {}

    @staticmethod
    def _get_dem_raster_file(revision):
        if "rasters" in revision:
            return next(
                (
                    raster
                    for raster in revision["rasters"]
                    if raster["type"] == "dem_file"
                ),
                None,
            )

    @staticmethod
    def _get_crs_str(data_type, meta, revision) -> Optional[str]:
        if data_type == "scenario" and meta:
            return meta.get("grid", {}).get("crs")
        elif data_type == "threedi_schematisation" and revision:
            dem = FileView._get_dem_raster_file(revision)
            if dem:
                return f"EPSG:{dem['epsg_code']}"
        elif meta and meta.get("extent"):
            return meta["extent"].get("crs")
        elif meta and meta.get("grid"):
            return meta["grid"].get("crs")
        return None

    @staticmethod
    def _get_area_str(data_type, meta, revision):
        """Return bounding box as [x1, y1, x2, y2]"""
        area = None
        if data_type == "scenario" and meta:
            # use grid['x'] and grid['y'] which is always in meters
            grid = meta.get("grid")
            if grid:
                area = (
                    grid["x"]["cell_size"]
                    * grid["x"]["size"]
                    * grid["y"]["size"]
                    * grid["y"]["cell_size"]
                )
        else:
            if data_type == "threedi_schematisation" and revision:
                # compute area based on DEM for 2D models and skip for models without dem
                dem = FileView._get_dem_raster_file(revision)
                if dem:
                    coord = dem["extent"]["coordinates"]
                    # re-organize bbox coordinates to match return format
                    # extent in threedi-api has a fixed crs
                    area = get_bbox_area_in_m2([*coord[0], *coord[1]], "EPSG:4326")
            elif meta.get("extent"):
                area = get_bbox_area_in_m2(
                    meta["extent"].get("bbox"),
                    FileView._get_crs_str(data_type, meta, revision),
                )
        if area:
            return f"{area / 1e6:.2f} km²"
        return ""

    def update_general_box(self, selected_file: dict):
        rows = []
        # line 1: icon - filename - size
        file_icon = get_icon_from_theme_as_pixmap(
            get_file_icon_name(selected_file["data_type"])
        )
        file_icon_label = get_icon_label(file_icon)
        filename = Path(selected_file["id"]).name
        size_str = (
            display_bytes(selected_file["size"])
            if selected_file["data_type"] != "threedi_schematisation"
            else ""
        )
        self.filename_edit.setText(filename)
        self.filename_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.filename_edit.adjustSize()

        rows.append([file_icon_label, self.filename_edit, QLabel(size_str)])
        # line 2: user icon - user name - commit msg - time
        # Note that the avatar is not automatically refreshed!

        field_errors = []
        if selected_file["data_type"] == "threedi_schematisation" and (
            self.schematisation is not None
        ):
            last_rev = self.schematisation.get("latest_revision") or {}
            commit_user_fv = FieldValue.from_dict(last_rev, "commit_user")
            rana_user = (
                get_user({"search": commit_user_fv.value})
                if not commit_user_fv.error
                else None
            )
            if not rana_user:
                given_fv = FieldValue.from_dict(
                    last_rev, "commit_first_name", default=""
                )
                family_fv = FieldValue.from_dict(
                    last_rev, "commit_last_name", default=""
                )
                rana_user = {
                    "id": f"{given_fv.value}_{family_fv.value}",
                    "given_name": given_fv.value,
                    "family_name": family_fv.value,
                }
                field_errors += [
                    ("commit_first_name", given_fv),
                    ("commit_last_name", family_fv),
                ]
            msg_fv = FieldValue.from_dict(last_rev, "commit_message", default="")
            last_modified_fv = FieldValue.from_dict(last_rev, "commit_date", default="")
            field_errors += [
                ("commit_message", msg_fv),
                ("commit_date", last_modified_fv),
            ]
            last_modified = (
                format_activity_timestamp_str(last_modified_fv.value)
                if not last_modified_fv.error
                else ""
            )
        else:
            rana_user = selected_file["user"]
            descriptor_fv = FieldValue.from_call(
                get_tenant_file_descriptor, selected_file["descriptor_id"]
            )
            msg_fv = FieldValue.from_dict(
                descriptor_fv.value, "description", default=""
            )
            field_errors += [("descriptor", descriptor_fv), ("description", msg_fv)]
            last_modified = format_activity_timestamp_str(
                selected_file["last_modified"]
            )

        log_field_errors(self.communication, "FileView general", field_errors)

        given_fv = FieldValue.from_dict(rana_user, "given_name", default="")
        family_fv = FieldValue.from_dict(rana_user, "family_name", default="")
        username_fv = FieldValue(
            value=f"{given_fv.value} {family_fv.value}".strip() or None,
            error=given_fv.error or family_fv.error,
            error_msg=given_fv.error_msg or family_fv.error_msg,
        )
        user_icon_label = get_icon_label(
            self.avatar_cache.get_avatar_for_user(rana_user)
        )
        msg_label = make_label(msg_fv, expanding=True, word_wrap=True)
        rows.append(
            [
                user_icon_label,
                make_label(username_fv, bold=True),
                msg_label,
                QLabel(last_modified),
            ]
        )
        # Refresh contents of general box
        container = QWidget(self.general_box)
        layout = QVBoxLayout(container)
        for row in rows:
            row_layout = QHBoxLayout()
            for item in row[:-1]:
                item.setParent(container)
                row_layout.addWidget(item)
            row_layout.addStretch()
            row[-1].setParent(container)
            row_layout.addWidget(row[-1])
            layout.addLayout(row_layout)
        # assign existing layout to temporary widget
        # this will be deleted once the scope of this method is over
        if self.general_box.layout():
            QWidget().setLayout(self.general_box.layout())
        self.general_box.setLayout(layout)

    def update_more_box(self, selected_file):
        self.communication.log_info("update more box")
        descriptor_fv = FieldValue.from_call(
            get_tenant_file_descriptor, selected_file["descriptor_id"]
        )
        descriptor = descriptor_fv.value
        self.communication.log_info(f"{descriptor=}")
        meta = descriptor.get("meta") if descriptor else None
        data_type = selected_file.get("data_type")

        field_errors = [("descriptor", descriptor_fv)]

        status = descriptor.get("status", {}) if descriptor else {}
        message_i18n = status.get("message_i18n", {})
        status_msg = message_i18n.get("msg") if message_i18n else None
        revision = (
            self.schematisation.get("latest_revision", {})
            if self.schematisation
            else {}
        )
        crs_str = self._get_crs_str(data_type, meta, revision)
        status_enum = FileDescriptorStatus.from_fd_response(descriptor)
        details = [
            # InfoRow("Area", self._get_area_str(data_type, meta, revision)),
            InfoRow("Projection", crs_str),
            InfoRow("Type", SUPPORTED_DATA_TYPES.get(data_type, data_type)),
            InfoRow(
                "Status",
                status.get("id", "") + ("" if not status_msg else f": {status_msg}"),
                color=QColor(255, 0, 0)
                if status_enum == FileDescriptorStatus.failed
                else None,
            ),
        ]
        if data_type != "threedi_schematisation":
            details.append(InfoRow("Storage", display_bytes(selected_file["size"])))
        if data_type == "scenario" and meta:
            simulation_fv = FieldValue.from_dict(meta, "simulation")
            schematisation_fv = FieldValue.from_dict(meta, "schematisation")
            simulation = simulation_fv.value or {}
            schematisation = schematisation_fv.value or {}
            field_errors += [
                ("simulation", simulation_fv),
                ("schematisation", schematisation_fv),
            ]

            interval = simulation.get("interval")
            if interval:
                start = parse_timestamp_str(interval[0])
                end = parse_timestamp_str(interval[1])
            else:
                start = None
                end = None

            software_fv = FieldValue.from_dict(simulation, "software")
            software = software_fv.value or {}
            field_errors.append(("software", software_fv))

            details += [
                InfoRow("Simulation name", FieldValue.from_dict(simulation, "name")),
                InfoRow("Simulation ID", FieldValue.from_dict(simulation, "id")),
                InfoRow(
                    "Schematisation name", FieldValue.from_dict(schematisation, "name")
                ),
                InfoRow(
                    "Schematisation ID", FieldValue.from_dict(schematisation, "id")
                ),
                InfoRow(
                    "Schematisation version",
                    FieldValue.from_dict(schematisation, "version"),
                ),
                InfoRow(
                    "Revision ID", FieldValue.from_dict(schematisation, "revision_id")
                ),
                InfoRow("Model ID", FieldValue.from_dict(schematisation, "model_id")),
                InfoRow("Model software", FieldValue.from_dict(software, "id")),
                InfoRow("Software version", FieldValue.from_dict(software, "version")),
                InfoRow("Start", start),
                InfoRow("End", end),
            ]
        if data_type == "threedi_schematisation":
            self.communication.log_info(f"schematisation data")
            schematisation = (
                self.schematisation.get("schematisation", {})
                if self.schematisation
                else {}
            )
            given_fv = FieldValue.from_dict(
                schematisation, "created_by_first_name", default=""
            )
            family_fv = FieldValue.from_dict(
                schematisation, "created_by_last_name", default=""
            )
            created_by = f"{given_fv.value} {family_fv.value}".strip() or None
            created_by_fv = FieldValue(
                value=created_by,
                error=given_fv.error or family_fv.error,
                error_msg=given_fv.error_msg or family_fv.error_msg,
            )
            field_errors += [
                ("created_by_first_name", given_fv),
                ("created_by_last_name", family_fv),
            ]
            schematisation_meta = schematisation.get("meta") or {}
            schematisation_timestamp_fv = FieldValue.from_dict(
                schematisation, "created"
            )
            if not schematisation_timestamp_fv.error:
                schematisation_timestamp_fv.value = parse_timestamp_str(
                    schematisation_timestamp_fv.value
                )
            details += [
                InfoRow(
                    "Schematisation name", FieldValue.from_dict(schematisation, "name")
                ),
                InfoRow(
                    "Schematisation ID", FieldValue.from_dict(schematisation, "id")
                ),
                InfoRow(
                    "Schematisation description",
                    FieldValue.from_dict(schematisation_meta, "description"),
                ),
                InfoRow("Schematisation created by", created_by_fv),
                InfoRow("Schematisation created on", schematisation_timestamp_fv),
                InfoRow(
                    "Schematisation tags",
                    FieldValue(value="; ".join(schematisation["tags"]) or None)
                    if "tags" in schematisation
                    else FieldValue.from_dict(schematisation, "tags"),
                ),
                InfoRow("Latest revision ID", FieldValue.from_dict(revision, "id")),
                InfoRow(
                    "Latest revision number", FieldValue.from_dict(revision, "number")
                ),
                InfoRow(
                    "Latest revision valid", FieldValue.from_dict(revision, "is_valid")
                ),
                InfoRow(
                    "Latest revision is simulation ready",
                    FieldValue.from_dict(revision, "is_simulation_ready"),
                    # self.latest_revision_model is not None,
                ),
                InfoRow(
                    "Node count",
                    FieldValue(
                        value=self.latest_revision_model.nodes_count,
                    )
                    if self.latest_revision_model
                    else FieldValue(
                        error=True, error_msg="No revision model available"
                    ),
                ),
                InfoRow(
                    "Line count",
                    FieldValue(
                        value=self.latest_revision_model.lines_count,
                    )
                    if self.latest_revision_model
                    else FieldValue(
                        error=True, error_msg="No revision model available"
                    ),
                ),
            ]

        log_field_errors(self.communication, "FileView more", field_errors)

        # Refresh contents of general box
        container = QWidget(self.more_box)
        layout = QGridLayout(container)
        for row_idx, info_row in enumerate(details):
            layout.addWidget(info_row.get_key_widget(parent=container), row_idx, 0)
            layout.addWidget(info_row.get_value_widget(parent=container), row_idx, 1)

        layout.setColumnStretch(1, 1)
        # assign existing layout to temporary widget
        # this will be deleted once the scope of this method is over
        if self.more_box.layout():
            QWidget().setLayout(self.more_box.layout())
        self.more_box.setLayout(layout)

    def update_files_box(self, selected_file):
        # only show files for schematisation with revision
        if selected_file["data_type"] != "threedi_schematisation":
            self.files_box.hide()
            return
        if not self.schematisation:
            self.files_box.hide()
            return
        rows = []
        revision = self.schematisation["latest_revision"]
        sqlite_file = revision.get("sqlite", {}).get("file")
        if sqlite_file:
            rows.append(
                [
                    sqlite_file.get("filename"),
                    sqlite_file.get("type"),
                    sqlite_file.get("size"),
                ]
            )
        rasters = revision.get("rasters", [])
        for raster in rasters:
            raster_file = raster.get("file")
            if raster_file:
                rows.append(
                    [
                        raster_file.get("filename"),
                        raster.get("type"),
                        raster_file.get("size"),
                    ]
                )
        if self.latest_revision_model:
            rows += [
                ["gridadmin.h5", "gridadmin", 0],
                ["gridadmin.gpkg", "gridadmin", 0],
            ]
        self.files_model.clear()
        self.files_model.setHorizontalHeaderLabels(["Name", "Type", "Size"])
        for file_name, data_type, file_size in rows:
            file_type_icon = get_icon_from_theme_as_pixmap(
                get_file_icon_name(data_type)
            )
            name_item = QStandardItem(file_name)
            name_item.setIcon(QIcon(file_type_icon))
            data_type_item = QStandardItem(
                SUPPORTED_DATA_TYPES.get(data_type, data_type)
            )
            if file_size > 0:
                size_item = NumericItem(display_bytes(file_size))
            else:
                size_item = NumericItem("")
            size_item.setData(file_size, role=Qt.ItemDataRole.UserRole)
            self.files_model.appendRow([name_item, data_type_item, size_item])
        self.files_box.show()

    def show_selected_file_details(self, selected_file):
        self.update_selected_file(selected_file)
        self.update_general_box(selected_file)
        self.update_more_box(selected_file)
        self.update_files_box(selected_file)
        if selected_file.get("data_type") == "threedi_schematisation" and (
            has_3di_authcfg()
        ):
            schematisation = self.schematisation
            if schematisation:
                revision = schematisation["latest_revision"]
                self.btn_stack.show()
                if revision and revision.get("has_threedimodel"):
                    self.btn_stack.setCurrentIndex(0)
                else:
                    self.btn_stack.setCurrentIndex(1)
                self.btn_show_revisions.show()
            else:
                self.btn_stack.hide()
                self.btn_show_revisions.hide()
        else:
            self.btn_stack.hide()
            self.btn_show_revisions.hide()
        self.update_file_action_buttons(selected_file)

    def open_in_browser(self):
        url = retrieve_url(self.selected_file, self.project, self.communication)
        if url:
            QDesktopServices.openUrl(url)

    def open_in_file_browser(self):
        """Open the local path of the selected file in the OS file explorer."""
        if not self.selected_file:
            return
        local_path = self._resolve_local_path(self.selected_file)
        if not local_path:
            return
        path = Path(local_path)
        if path.is_file():
            path = path.parent
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _resolve_local_path(
        self, selected_file: dict, descriptor: dict = None
    ) -> Optional[str]:
        """Resolve the local path for a file, or return None if not present."""
        data_type = selected_file.get("data_type")
        if data_type == "threedi_schematisation":
            return self._resolve_schematisation_local_path(selected_file)
        elif data_type == "scenario":
            return self._resolve_scenario_local_path(
                selected_file, descriptor=descriptor
            )
        else:
            local_path = get_local_file_path(self.project["slug"], selected_file["id"])
            return local_path if Path(local_path).exists() else None

    def _resolve_schematisation_local_path(self, selected_file: dict) -> Optional[str]:
        """Resolve the local revision directory for a schematisation."""
        working_dir = hcc_working_dir()
        if not working_dir:
            return None
        schematisation = self.schematisation
        if not schematisation:
            return None
        latest_revision = schematisation.get("latest_revision")
        if not latest_revision:
            return None
        revision_dir = get_local_schematisation_revision_dir(
            working_dir,
            schematisation["schematisation"]["id"],
            schematisation["schematisation"]["name"],
            latest_revision["number"],
            create=False,
        )
        if revision_dir and revision_dir.exists():
            return str(revision_dir)
        return None

    def _resolve_scenario_local_path(
        self, selected_file: dict, descriptor: dict = None
    ) -> Optional[str]:
        """Resolve the local results directory for a scenario."""
        if descriptor is None:
            descriptor = get_tenant_file_descriptor(selected_file["descriptor_id"])
        if not descriptor:
            return None
        meta = descriptor.get("meta")
        if not meta or "id" not in meta:
            return None
        working_dir = hcc_working_dir()
        if working_dir:
            results_dir = get_local_results_dir_from_meta(meta, working_dir)
            if results_dir and Path(results_dir).exists():
                return results_dir
        local_dir = get_local_dir_structure(self.project["slug"], selected_file["id"])
        return local_dir if Path(local_dir).exists() else None

    def refresh(self):
        # Skip refresh because user is interacting with state of the file
        if self.no_refresh:
            return
        # Get fresh object to retrieve correct last_modified
        updated_file = get_tenant_project_file(
            self.project["id"], {"path": self.selected_file["id"]}
        )
        # Only update if new file is still there
        if updated_file:
            self.update_selected_file(updated_file)
            last_modified_key = (
                f"{self.project['name']}/{self.selected_file['id']}/last_modified"
            )
            QSettings().setValue(last_modified_key, self.selected_file["last_modified"])
            self.show_selected_file_details(self.selected_file)
