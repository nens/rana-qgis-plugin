import os

from qgis.core import QgsMessageLog, QgsRasterLayer, QgsProject
from qgis.PyQt.QtWidgets import QTableWidget, QTableWidgetItem, QPushButton, QVBoxLayout

from rana_qgis_plugin.utils import download_open_raster_file

class RanaFileDetails:
    def __init__(self, table_widget: QTableWidget):
        self.table_widget = table_widget
        self.table_widget.horizontalHeader().hide()
        self.table_widget.hide()

        # File and file open button
        self.file = None
        self.btn_open = QPushButton("Open in QGIS")
        self.layout = QVBoxLayout(self.table_widget)
        self.layout.addWidget(self.btn_open)
        self.btn_open.clicked.connect(self.open_file_in_qgis)

    def hide_file_details(self):
        self.table_widget.hide()

    def show_file_details(self, file):
        self.file = file
        self.table_widget.clearContents()
        self.table_widget.setRowCount(3)
        self.table_widget.setColumnCount(2)

        # Define labels and values
        labels = ["Filename", "Size", "Type"]
        values = [
            os.path.basename(file["id"].rstrip("/")),
            f"{file["size"]} bytes",
            file["type"]
        ]

        # Populate the table
        for i, (label, value) in enumerate(zip(labels, values)):
            self.table_widget.setItem(i, 0, QTableWidgetItem(label))
            self.table_widget.setItem(i, 1, QTableWidgetItem(value))

        # Resize the columns
        self.table_widget.resizeColumnsToContents()
        self.table_widget.show()

    def open_file_in_qgis(self):
        if self.file and self.file["descriptor"] and self.file["descriptor"]["data_type"] == "raster":
            download_url = self.file["url"]
            file_name = os.path.basename(self.file["id"].rstrip("/"))
            local_file_path = download_open_raster_file(download_url, file_name)
            layer = QgsRasterLayer(local_file_path, file_name)
            if layer.isValid():
                QgsProject.instance().addMapLayer(layer)
                QgsMessageLog.logMessage(f"Added raster layer: {local_file_path}")
            else:
                QgsMessageLog.logMessage(f"Error adding raster layer: {local_file_path}")
