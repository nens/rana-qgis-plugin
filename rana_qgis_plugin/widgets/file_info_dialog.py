"""Dialog and section widgets for viewing Rana file metadata."""

from qgis.gui import QgsCollapsibleGroupBox
from qgis.PyQt.QtCore import Qt, QTimer
from qgis.PyQt.QtGui import QShowEvent, QStandardItem, QStandardItemModel
from qgis.PyQt.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from rana_qgis_plugin.api_error_signals import ApiErrorSignals
from rana_qgis_plugin.network_manager import NetworkUnavailableError
from rana_qgis_plugin.simulation.threedi_calls import ThreediCalls
from rana_qgis_plugin.utils.api import (
    FetchError,
    get_tenant_file_descriptor,
    get_threedi_schematisation,
)
from rana_qgis_plugin.utils.generic import get_file_icon_name, get_threedi_api
from rana_qgis_plugin.utils.log import plugin_log_error
from rana_qgis_plugin.widgets.file_info_models import (
    FieldValue,
    GeneralInfo,
    InfoSection,
    RelatedFile,
    SchematisationFileInfoModel,
    get_file_info_model_class,
)
from rana_qgis_plugin.widgets.utils_avatars import get_avatar
from rana_qgis_plugin.widgets.utils_icons import get_icon_from_theme_as_pixmap


class GeneralInfoWidget(QWidget):
    """Render the distinct General section layout."""

    def __init__(self, communication, parent=None):
        super().__init__(parent)
        self.communication = communication
        self.labels = {}
        self.setLayout(QVBoxLayout(self))
        self.setup_ui()

    def setup_ui(self):
        rows = [
            ["file_icon", "filename", "size"],
            ["user_icon", "user", "msg", "modified"],
        ]
        for row in rows:
            row_layout = QHBoxLayout()
            for i, item in enumerate(row):
                if i == (len(row) - 1):
                    row_layout.addStretch()
                self.labels[item] = QLabel(item)
                row_layout.addWidget(self.labels[item])
            self.layout().addLayout(row_layout)

    def update(self, info: GeneralInfo):
        """Update stable labels from General data."""
        fields = {
            "filename": info.filename,
            "size": info.size,
            "user": info.user,
            "msg": info.message,
            "modified": info.last_modified,
        }
        self.labels["file_icon"].setPixmap(
            get_icon_from_theme_as_pixmap(get_file_icon_name(info.icon_name))
        )
        avatar = get_avatar(
            info.avatar_user, try_remote=True, create_from_initials=True
        )
        if avatar:
            self.labels["user_icon"].setPixmap(avatar)
        for key, field in fields.items():
            update_label(self.labels[key], field)


class MoreInfoWidget(QWidget):
    """Render More Information rows without recreating the widget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.labels = {}
        self.setLayout(QFormLayout(self))

    def update(self, section: InfoSection):
        """Update existing labels and add only previously unseen fields."""
        for row in section.rows:
            if row.key not in self.labels:
                self.labels[row.key] = QLabel()
                self.layout().addRow(row.key, self.labels[row.key])
            update_label(self.labels[row.key], row.value)


class RelatedFilesWidget(QWidget):
    """Render the schematisation related-files table."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.table = QTableView(self)
        self.table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.model = QStandardItemModel(0, 3, self.table)
        self.model.setHorizontalHeaderLabels(["Name", "Type", "Size"])
        self.table.setModel(self.model)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setStretchLastSection(False)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table.setSizeAdjustPolicy(QTableView.SizeAdjustPolicy.AdjustToContents)
        layout = QVBoxLayout(self)
        layout.addWidget(self.table)

    def update(self, related_files: list[RelatedFile]):
        """Replace table rows while keeping the table and model stable."""
        self.model.removeRows(0, self.model.rowCount())
        for related_file in related_files:
            self.model.appendRow(
                [
                    make_item(related_file.name),
                    make_item(related_file.data_type),
                    make_item(related_file.size),
                ]
            )
        self.table.resizeRowsToContents()
        height = self.table.horizontalHeader().height()
        height += sum(self.table.rowHeight(row) for row in range(self.model.rowCount()))
        self.table.setMinimumHeight(height + 10)
        self.table.setMaximumHeight(height + 10)


class FileInfoDialog(QDialog):
    """Display read-only metadata for one Rana file."""

    def __init__(self, file_data: dict, error_signals: ApiErrorSignals, parent=None):
        super().__init__(parent)
        self.file_data = file_data
        self.error_signals = error_signals
        self.setWindowTitle(f"File information - {file_data.get('id', '')}")
        self.setup_ui()

    def setup_ui(self):
        """Create section widgets and the dialog controls."""
        self.general_box = QgsCollapsibleGroupBox("General")
        self.general_widget = GeneralInfoWidget(self.general_box)
        QVBoxLayout(self.general_box).addWidget(self.general_widget)
        self.more_box = QgsCollapsibleGroupBox("More information")
        self.more_widget = MoreInfoWidget(self.more_box)
        QVBoxLayout(self.more_box).addWidget(self.more_widget)
        self.files_box = QgsCollapsibleGroupBox("Related files")
        self.files_widget = RelatedFilesWidget(self.files_box)
        QVBoxLayout(self.files_box).addWidget(self.files_widget)
        self._container = QWidget()
        container_layout = QVBoxLayout(self._container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        for box in (self.general_box, self.more_box, self.files_box):
            container_layout.addWidget(box)
        container_layout.addStretch()
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setWidget(self._container)

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh)
        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: red;")
        self.error_label.hide()
        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(self.refresh_button)
        layout = QVBoxLayout(self)
        layout.addWidget(self._scroll_area)
        layout.addWidget(self.error_label)
        layout.addLayout(buttons)
        self.refresh()

    def _fetch_descriptor(self):
        """Fetch the descriptor and update all section widgets."""
        self.error_label.hide()
        try:
            descriptor = get_tenant_file_descriptor(self.file_data["descriptor_id"])
        except NetworkUnavailableError:
            self.error_signals.connection_lost.emit()
            self.show_error("No connection to Rana")
            return
        except FetchError as error:
            self.error_signals.fetch_error_occurred.emit(str(error))
            self.show_error(f"Failed to load file information: {error}")
            return
        return descriptor

    def _populate_widgets(self, model):
        self.general_widget.update(model.get_general_info())
        self.more_widget.update(model.get_more_section())
        related_files = model.get_related_files()
        self.files_widget.update(related_files)
        self.files_box.setVisible(bool(related_files))

    def refresh(self):
        """Fetch the descriptor and update all section widgets."""
        self.refresh_button.setEnabled(False)
        descriptor = self._fetch_descriptor()
        if descriptor is None:
            return
        model_class = get_file_info_model_class(self.file_data.get("data_type", ""))
        self._populate_widgets(model_class(descriptor, self.file_data))
        self.refresh_button.setEnabled(True)
        if self.isVisible():
            QTimer.singleShot(0, self._fit_to_content)

    def _fit_to_content(self):
        """Resize the dialog to show all content without scrolling.

        Uses the vertical scrollbar's overflow (how many pixels are hidden)
        to determine the extra height needed, and the container's natural
        sizeHint for the preferred width (before setWidgetResizable squeezes it).
        """
        vbar = self._scroll_area.verticalScrollBar()
        overflow_h = vbar.maximum()

        margins = self.layout().contentsMargins()
        natural_w = (
            self._container.sizeHint().width() + margins.left() + margins.right() + 4
        )
        target_h = self.height() + overflow_h
        target_w = max(self.width(), natural_w)

        if screen := self.screen():
            avail = screen.availableGeometry()
            target_w = min(target_w, int(avail.width() * 0.85))
            target_h = min(target_h, int(avail.height() * 0.85))

        self.resize(target_w, target_h)

    def show_error(self, message: str):
        """Display an error while keeping refresh available."""
        self.error_label.setText(message)
        self.error_label.show()
        self.refresh_button.setEnabled(True)

    def showEvent(self, event: QShowEvent):
        """Resize to content after the first layout pass completes."""
        super().showEvent(event)
        QTimer.singleShot(0, self._fit_to_content)


class SchematisationFileInfoDialog(FileInfoDialog):
    """Display schematisation metadata with its additional API resources."""

    def refresh(self):
        """Fetch descriptor, schematisation, and model independently."""
        self.refresh_button.setEnabled(False)
        descriptor = self._fetch_descriptor()
        if descriptor is None:
            return
        schematisation = None
        try:
            schematisation = get_threedi_schematisation(self.file_data["descriptor_id"])
        except NetworkUnavailableError:
            self.error_signals.connection_lost.emit()
            self.show_error("No connection to Rana while loading schematisation")
        except FetchError as error:
            plugin_log_error(f"Failed to load schematisation: {error}")
            self.show_error("Failed to load schematisation details")
        threedi_model = None
        revision = (schematisation or {}).get("latest_revision") or {}
        api = get_threedi_api()
        if api is not None and revision.get("has_threedimodel"):
            try:
                assert schematisation is not None
                models = ThreediCalls(api).fetch_schematisation_revision_3di_models(
                    schematisation["schematisation"]["id"], revision["id"]
                )
                threedi_model = next(
                    (
                        model
                        for model in models
                        if model.is_valid and not model.disabled
                    ),
                    None,
                )
            except Exception as error:
                plugin_log_error(f"Failed to load 3Di revision model: {error}")
                self.show_error("Failed to load 3Di model details")

        model = SchematisationFileInfoModel(
            descriptor,
            file_data=self.file_data,
            schematisation_data=schematisation,
            threedi_model_data=threedi_model,
        )
        self._populate_widgets(model)
        self.refresh_button.setEnabled(True)
        if self.isVisible():
            QTimer.singleShot(0, self._fit_to_content)


def update_label(label: QLabel, field: FieldValue):
    """Update a label from a safe model field."""
    label.setText("N/A" if field.value is None else str(field.value))
    label.setStyleSheet("color: red;" if field.error else "")
    label.setToolTip(field.error_msg if field.error else "")


def make_item(field: FieldValue) -> QStandardItem:
    """Create a table item from a safe model field."""
    return QStandardItem("N/A" if field.value is None else str(field.value))
