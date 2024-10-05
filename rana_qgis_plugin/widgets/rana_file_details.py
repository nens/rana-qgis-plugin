import os
import requests

from qgis.core import QgsMessageLog, QgsRasterLayer, QgsProject, QgsVectorLayer
from qgis.PyQt.QtWidgets import QTableWidget, QTableWidgetItem, QPushButton, QVBoxLayout

from rana_qgis_plugin.utils import download_file, start_file_upload, finish_file_upload
from rana_qgis_plugin.constant import TENANT

class RanaFileDetails:
    def __init__(self, table_widget: QTableWidget):
        self.table_widget = table_widget
        self.table_widget.horizontalHeader().hide()
        self.table_widget.hide()
        self.project_id = None
        self.project_name = None
        self.file = None

        # File open button
        self.btn_open = QPushButton("Open in QGIS")
        self.layout = QVBoxLayout(self.table_widget)
        self.layout.addWidget(self.btn_open)
        self.btn_open.clicked.connect(self.open_file_in_qgis)

        # File save button
        self.btn_save = QPushButton("Save to Rana")
        self.layout.addWidget(self.btn_save)
        self.btn_save.clicked.connect(self.save_file_to_rana)

    def hide_file_details(self):
        self.table_widget.hide()

    def show_file_details(self, file, project):
        self.project_id = project["id"]
        self.project_name = project["name"]
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
        if self.file and self.file["descriptor"] and self.file["descriptor"]["data_type"]:
            data_type = self.file["descriptor"]["data_type"]
            download_url = self.file["url"]
            file_path = self.file["id"]
            file_name = os.path.basename(file_path.rstrip("/"))
            local_file_path = download_file(
                url=download_url,
                project_name=self.project_name,
                file_path=file_path,
                file_name=file_name
            )
            if not local_file_path:
                QgsMessageLog.logMessage(f"Download failed. Unable to open {data_type} file in QGIS.")
                return
            if data_type == "vector":
                layer = QgsVectorLayer(local_file_path, file_name, "ogr")
            elif data_type == "raster":
                layer = QgsRasterLayer(local_file_path, file_name)
            else:
                QgsMessageLog.logMessage(f"Unsupported data type: {data_type}")
                return
            if layer.isValid():
                QgsProject.instance().addMapLayer(layer)
                QgsMessageLog.logMessage(f"Added {data_type} layer: {local_file_path}")
            else:
                QgsMessageLog.logMessage(f"Error adding {data_type} layer: {local_file_path}")

    def save_file_to_rana(self):
        if not self.file or not self.project_id:
            return
        file_name = os.path.basename(self.file["id"].rstrip("/"))
        rana_file_path = self.file["id"]
        local_file_path = os.path.join("/tests_directory", file_name)

        # Check if the file exists locally before uploading
        if not os.path.exists(local_file_path):
            QgsMessageLog.logMessage(f"File not found: {local_file_path}")
            return

        # Save the file to Rana
        try:
            # Step 1: POST request to initiate the upload
            upload_response = start_file_upload(TENANT, self.project_id, { "path": rana_file_path })
            if not upload_response:
                QgsMessageLog.logMessage("Failed to initiate upload.")
                return
            upload_url = upload_response["urls"][0]
            # Step 2: Upload the file to the upload_url
            with open(local_file_path, "rb") as file:
                response = requests.put(upload_url, data=file)
                response.raise_for_status()
            # Step 3: Complete the upload
            finish_file_upload(TENANT, self.project_id, upload_response)
        except Exception as e:
            QgsMessageLog.logMessage(f"Error uploading file to Rana: {str(e)}")
