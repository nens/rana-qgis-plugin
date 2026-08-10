"""Dialog and section widgets for viewing Rana file metadata."""

from qgis.gui import QgsCollapsibleGroupBox
from qgis.PyQt.QtGui import QStandardItem, QStandardItemModel
from qgis.PyQt.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from rana_qgis_plugin.api_error_signals import ApiErrorSignals
from rana_qgis_plugin.network_manager import NetworkUnavailableError
from rana_qgis_plugin.utils.api import FetchError, get_tenant_file_descriptor
from rana_qgis_plugin.utils.generic import get_file_icon_name
from rana_qgis_plugin.widgets.file_info_models import (
    FieldValue,
    FileInfoModel,
    GeneralInfo,
    InfoSection,
    RelatedFile,
    get_file_info_model_class,
    make_more_info_model,
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


class FileInfoDialog(QDialog):
    """Display read-only metadata for one Rana file."""

    def __init__(self, file_data: dict, error_signals: ApiErrorSignals, parent=None):
        super().__init__(parent)
        self.file_data = file_data
        self.error_signals = error_signals
        self.model_cls: type[FileInfoModel] = get_file_info_model_class(
            file_data["data_type"]
        )
        # TODO: do we need self.model?
        self.model: FileInfoModel | None = None
        self.setWindowTitle(f"File information - {file_data.get('id', '')}")
        self.resize(650, 600)
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

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        for box in (self.general_box, self.more_box, self.files_box):
            container_layout.addWidget(box)
        container_layout.addStretch()
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(container)

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh)
        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: red;")
        self.error_label.hide()
        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(self.refresh_button)
        layout = QVBoxLayout(self)
        layout.addWidget(scroll_area)
        layout.addWidget(self.error_label)
        layout.addLayout(buttons)
        self.refresh()

    def refresh(self):
        """Fetch the descriptor and update all section widgets."""
        self.refresh_button.setEnabled(False)
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
        self.model = make_more_info_model(
            self.file_data.get("data_type", ""), descriptor, self.file_data
        )
        model = self.model
        self.general_widget.update(model.get_general_info())
        self.more_widget.update(model.get_more_section())
        related_files = model.get_related_files()
        self.files_widget.update(related_files)
        self.files_box.setVisible(bool(related_files))
        self.refresh_button.setEnabled(True)

    def show_error(self, message: str):
        """Display an error while keeping refresh available."""
        self.error_label.setText(message)
        self.error_label.show()
        self.refresh_button.setEnabled(True)


def update_label(label: QLabel, field: FieldValue):
    """Update a label from a safe model field."""
    label.setText("N/A" if field.value is None else str(field.value))
    label.setStyleSheet("color: red;" if field.error else "")
    label.setToolTip(field.error_msg if field.error else "")


def make_item(field: FieldValue) -> QStandardItem:
    """Create a table item from a safe model field."""
    return QStandardItem("N/A" if field.value is None else str(field.value))
