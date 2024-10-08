import os

import requests
from qgis.core import QgsMessageLog, QgsProject, QgsRasterLayer, QgsVectorLayer
from qgis.PyQt import uic
from qgis.PyQt.QtCore import QSettings
from qgis.PyQt.QtWidgets import QMessageBox, QTableWidgetItem

from rana_qgis_plugin.constant import TENANT
from rana_qgis_plugin.utils import (
    download_file,
    finish_file_upload,
    get_local_file_path,
    start_file_upload,
)

base_dir = os.path.dirname(__file__)
uicls, basecls = uic.loadUiType(os.path.join(base_dir, "ui", "file.ui"))


class RanaFileDetails(uicls, basecls):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.parent = parent
        self.project_id = None
        self.project_name = None
        self.file = None
        self.settings = QSettings()
        self.btn_open.clicked.connect(self.open_file_in_qgis)
        self.btn_save.clicked.connect(self.save_file_to_rana)

    def show_file_details(self, file, project):
        self.project_id = project["id"]
        self.project_name = project["name"]
        self.file = file
        self.table_widget.clearContents()
        file_details = [
            ("Filename", os.path.basename(file["id"].rstrip("/"))),
            ("Size", f"{file['size']} bytes"),
            ("Type", file["media_type"]),
        ]

        # Populate the table
        for i, (label, value) in enumerate(file_details):
            self.table_widget.setItem(i, 0, QTableWidgetItem(label))
            self.table_widget.setItem(i, 1, QTableWidgetItem(value))

        # Resize the columns
        self.table_widget.resizeColumnsToContents()

    def open_file_in_qgis(self):
        if self.file and self.file["descriptor"] and self.file["descriptor"]["data_type"]:
            data_type = self.file["descriptor"]["data_type"]
            if data_type not in ["vector", "raster"]:
                QgsMessageLog.logMessage(f"Unsupported data type: {data_type}")
                return
            download_url = self.file["url"]
            file_path = self.file["id"]
            file_name = os.path.basename(file_path.rstrip("/"))
            local_file_path = download_file(
                url=download_url,
                project_name=self.project_name,
                file_path=file_path,
                file_name=file_name,
            )
            if not local_file_path:
                QgsMessageLog.logMessage(f"Download failed. Unable to open {data_type} file in QGIS.")
                return

            # Save the last modified date of the downloaded file in QSettings
            last_modified_key = f"{self.project_name}/{file_path}/last_modified"
            self.settings.setValue(last_modified_key, self.file["last_modified"])

            # Add the layer to QGIS
            if data_type == "vector":
                layer = QgsVectorLayer(local_file_path, file_name, "ogr")
            else:
                layer = QgsRasterLayer(local_file_path, file_name)
            if layer.isValid():
                QgsProject.instance().addMapLayer(layer)
                QgsMessageLog.logMessage(f"Added {data_type} layer: {local_file_path}")
            else:
                QgsMessageLog.logMessage(f"Error adding {data_type} layer: {local_file_path}")
        else:
            QgsMessageLog.logMessage(f"Unsupported data type: {self.file['media_type']}")

    def save_file_to_rana(self):
        if not self.file or not self.project_id:
            return
        file_name = os.path.basename(self.file["id"].rstrip("/"))
        rana_file_path = self.file["id"]
        _, local_file_path = get_local_file_path(self.project_name, rana_file_path, file_name)

        # Check if file exists locally before uploading
        if not os.path.exists(local_file_path):
            QgsMessageLog.logMessage(f"File not found: {local_file_path}")
            return

        # Check if file has been modified since it was last downloaded
        has_file_conflict = self.check_for_file_conflict()
        if has_file_conflict:
            return

        # Save file to Rana
        try:
            # Step 1: POST request to initiate the upload
            upload_response = start_file_upload(TENANT, self.project_id, {"path": rana_file_path})
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

    def check_for_file_conflict(self):
        file_path = self.file["id"]
        last_modified_key = f"{self.project_name}/{file_path}/last_modified"
        local_last_modified = self.settings.value(last_modified_key)
        last_modified = self.file["last_modified"]
        if last_modified != local_last_modified:
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setWindowTitle("File Conflict Detected")
            msg_box.setText("The file has been modified on the server since it was last downloaded.")
            msg_box.setInformativeText("Do you want to overwrite the server copy with the local copy?")
            overwrite_btn = msg_box.addButton(QMessageBox.Yes)
            cancel_btn = msg_box.addButton(QMessageBox.No)
            msg_box.exec_()
            if msg_box.clickedButton() == cancel_btn:
                QgsMessageLog.logMessage("File upload cancelled.")
                return True
            elif msg_box.clickedButton() == overwrite_btn:
                QgsMessageLog.logMessage("Overwriting the server copy with the local copy.")
                return False
        else:
            return False
