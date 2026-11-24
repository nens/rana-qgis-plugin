from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from rana_qgis_plugin.constant import PLUGIN_NAME
from rana_qgis_plugin.utils.api import get_filename_from_attachment_url


class ResultBrowser(QDialog):
    def __init__(self, parent, results: list):
        super().__init__(parent)
        self.setWindowTitle(PLUGIN_NAME)
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)
        self.setLayout(layout)

        self.selected_results: list[int] = []

        self.download_raw_data_bx = QCheckBox("Download simulation results", self)
        self.download_raw_data_bx.setChecked(True)
        layout.addWidget(self.download_raw_data_bx)

        results_group = QGroupBox("Download post-processing results", self)
        results_group.setLayout(QGridLayout())

        self.results_table = QTableWidget(self)
        results_group.layout().addWidget(self.results_table)
        self.results_table.setColumnCount(2)
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.horizontalHeader().setStretchLastSection(True)
        self.results_table.setHorizontalHeaderLabels(["Type", "File name"])

        always_checked = ["max water depth (file)"]
        excluded_results = ["raw 3di output", "grid administration", "3di bathymetry"]
        for result in [r for r in results if r.get("attachment_url")]:
            if result["name"].lower() in excluded_results:
                continue
            self.results_table.insertRow(self.results_table.rowCount())
            type_item = QTableWidgetItem(result["name"])
            type_item.setFlags(
                Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable
            )
            check_state = (
                Qt.CheckState.Checked
                if result["name"].lower() in always_checked
                else Qt.CheckState.Unchecked
            )
            type_item.setCheckState(check_state)
            type_item.setData(Qt.ItemDataRole.UserRole, int(result["id"]))

            file_name = get_filename_from_attachment_url(result["attachment_url"])

            file_name_item = QTableWidgetItem(file_name)
            file_name_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.results_table.setItem(self.results_table.rowCount() - 1, 0, type_item)
            self.results_table.setItem(
                self.results_table.rowCount() - 1, 1, file_name_item
            )

        if len(results) == 0:
            icon_label = QLabel()
            icon_label.setPixmap(
                QIcon(":/images/themes/default/mIconWarning.svg").pixmap(16, 16)
            )
            icon_label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
            warning_label = QLabel(
                "Post-processing results are not available because they are still being processed."
            )
            warning_label.setTextFormat(Qt.TextFormat.RichText)
            warning_layout = QHBoxLayout()
            warning_layout.addWidget(icon_label)
            warning_layout.addWidget(warning_label)
            warning_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
            layout.addLayout(warning_layout)

        self.results_table.resizeColumnsToContents()
        layout.addWidget(results_group)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_selected_results(self) -> list[int]:
        return self.selected_results

    def get_download_raw_result(self) -> bool:
        return self.download_raw_data_bx.isChecked()

    def accept(self) -> None:
        self.selected_results = []
        for row in range(self.results_table.rowCount()):
            name_item = self.results_table.item(row, 0)
            if name_item.checkState() == Qt.CheckState.Checked:
                result_id = int(name_item.data(Qt.ItemDataRole.UserRole))
                self.selected_results.append(result_id)

        super().accept()
