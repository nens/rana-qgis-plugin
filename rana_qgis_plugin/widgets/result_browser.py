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

        self.table = QTableWidget(self)
        results_group.layout().addWidget(self.table)
        self.table.setColumnCount(2)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setHorizontalHeaderLabels(["Type", "File name"])

        for i, result in enumerate([r for r in results if r["attachment_url"]]):
            self.table.insertRow(self.table.rowCount())
            type_item = QTableWidgetItem(result["name"])
            type_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
            type_item.setCheckState(Qt.Unchecked)
            type_item.setData(Qt.UserRole, int(result["id"]))

            file_name = get_filename_from_attachment_url(result["attachment_url"])
            file_name_item = QTableWidgetItem(file_name)
            file_name_item.setFlags(Qt.ItemIsEnabled)
            self.table.setItem(i, 0, type_item)
            self.table.setItem(i, 1, file_name_item)

        self.table.resizeColumnsToContents()
        layout.addWidget(results_group)

        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)
        layout.addWidget(buttonBox)

    def get_selected_results_id(self) -> List[int]:
        return self.selected_results

    def accept(self) -> None:
        self.selected_results = []
        for r in range(self.table.rowCount()):
            name_item = self.table.item(r, 0)
            if name_item.checkState() == Qt.Checked:
                id = int(name_item.data(Qt.UserRole))
                self.selected_results.append(id)

        return super().accept()
