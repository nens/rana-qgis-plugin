from typing import List

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from rana_qgis_plugin.constant import PLUGIN_NAME
from rana_qgis_plugin.utils import get_filename_from_attachment_url


class ResultBrowser(QDialog):
    def __init__(self, parent, results):
        super().__init__(parent)
        self.setWindowTitle(PLUGIN_NAME)
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)
        self.setLayout(layout)

        self.selected_results = []

        results_group = QGroupBox("Results", self)
        results_group.setLayout(QGridLayout())

        postprocessed_rasters_group = QGroupBox(
            "Postprocess raster results (slow)", self
        )
        postprocessed_rasters_group.setLayout(QGridLayout())

        self.results_table = QTableWidget(self)
        results_group.layout().addWidget(self.results_table)
        self.results_table.setColumnCount(2)
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.horizontalHeader().setStretchLastSection(True)
        self.results_table.setHorizontalHeaderLabels(["Type", "File name"])

        self.postprocessed_rasters_table = QTableWidget(self)
        postprocessed_rasters_group.layout().addWidget(self.postprocessed_rasters_table)
        self.postprocessed_rasters_table.setColumnCount(2)
        self.postprocessed_rasters_table.verticalHeader().setVisible(False)
        self.postprocessed_rasters_table.horizontalHeader().setStretchLastSection(True)
        self.postprocessed_rasters_table.setHorizontalHeaderLabels(
            ["Type", "File name"]
        )

        for i, result in enumerate([r for r in results if r["attachment_url"]]):
            self.results_table.insertRow(self.results_table.rowCount())
            type_item = QTableWidgetItem(result["name"])
            type_item.setFlags(
                Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable
            )
            type_item.setCheckState(Qt.CheckState.Unchecked)
            type_item.setData(Qt.ItemDataRole.UserRole, int(result["id"]))

            file_name = get_filename_from_attachment_url(result["attachment_url"])

            file_name_item = QTableWidgetItem(file_name)
            file_name_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.results_table.setItem(i, 0, type_item)
            self.results_table.setItem(i, 1, file_name_item)

        # timeseries rasters
        excluded_rasters = ["depth-dtri", "rain-quad", "s1-dtri"]

        for i, result in enumerate(
            [r for r in results if r["raster_id"] and r["code"] not in excluded_rasters]
        ):
            self.postprocessed_rasters_table.insertRow(
                self.postprocessed_rasters_table.rowCount()
            )
            type_item = QTableWidgetItem(result["name"])
            type_item.setFlags(
                Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable
            )
            type_item.setCheckState(Qt.CheckState.Unchecked)
            type_item.setData(Qt.ItemDataRole.UserRole, int(result["id"]))

            file_name = result["code"]
            file_name_item = QTableWidgetItem(file_name)
            file_name_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.postprocessed_rasters_table.setItem(i, 0, type_item)
            self.postprocessed_rasters_table.setItem(i, 1, file_name_item)

        self.results_table.resizeColumnsToContents()
        layout.addWidget(results_group)

        self.postprocessed_rasters_table.resizeColumnsToContents()
        layout.addWidget(postprocessed_rasters_group)

        buttonBox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)
        layout.addWidget(buttonBox)

    def get_selected_results_id(self) -> List[int]:
        return self.selected_results

    def accept(self) -> None:
        self.selected_results = []
        for r in range(self.results_table.rowCount()):
            name_item = self.results_table.item(r, 0)
            if name_item.checkState() == Qt.CheckState.Checked:
                id = int(name_item.data(Qt.ItemDataRole.UserRole))
                self.selected_results.append(id)

        for r in range(self.postprocessed_rasters_table.rowCount()):
            name_item = self.postprocessed_rasters_table.item(r, 0)
            if name_item.checkState() == Qt.CheckState.Checked:
                id = int(name_item.data(Qt.ItemDataRole.UserRole))
                self.selected_results.append(id)

        return super().accept()
