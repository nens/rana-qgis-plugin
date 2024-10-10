import os

import requests
from qgis.core import QgsMessageLog, QgsProject, QgsRasterLayer, QgsVectorLayer
from qgis.PyQt import uic
from qgis.PyQt.QtCore import QSettings, Qt
from qgis.PyQt.QtGui import QStandardItem, QStandardItemModel
from qgis.PyQt.QtWidgets import QLabel, QMessageBox, QPushButton, QTableWidgetItem

from rana_qgis_plugin.constant import TENANT
from rana_qgis_plugin.utils import (
    download_file,
    finish_file_upload,
    get_local_file_path,
    get_tenant_project_file,
    get_tenant_project_files,
    get_tenant_projects,
    start_file_upload,
)

base_dir = os.path.dirname(__file__)
uicls, basecls = uic.loadUiType(os.path.join(base_dir, "ui", "rana.ui"))


class RanaMainWidget(uicls, basecls):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.settings = QSettings()
        self.paths = ["Home"]

        # Projects widget
        self.projects_model = QStandardItemModel()
        self.projects_tv.setModel(self.projects_model)
        self.projects = []
        self.project = None
        self.fetch_projects()

        # Files widget
        self.files = []
        self.files_model = QStandardItemModel()
        self.files_tv.setModel(self.files_model)
        self.files_tv.doubleClicked.connect(self.select_file_or_directory)

        # File details widget
        self.file = None
        self.btn_open.clicked.connect(self.open_file_in_qgis)
        self.btn_save.clicked.connect(self.save_file_to_rana)

        # Breadcrumbs
        self.breadcrumbs_layout.setAlignment(Qt.AlignLeft)
        self.update_breadcrumbs()

    def show_files_widget(self):
        self.rana_widget.setCurrentIndex(1)
        self.update_breadcrumbs()

    def update_breadcrumbs(self):
        # Clear existing breadcrumbs
        for i in reversed(range(self.breadcrumbs_layout.count())):
            widget = self.breadcrumbs_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        # Add the breadcrumbs
        for i, path in enumerate(self.paths):
            btn = QPushButton(path)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setDisabled(i == len(self.paths) - 1)
            btn.clicked.connect(lambda _, i=i: self.on_breadcrumb_click(i))
            self.breadcrumbs_layout.addWidget(btn)
            if i != len(self.paths) - 1:
                separator = QLabel(">")
                self.breadcrumbs_layout.addWidget(separator)

    def on_breadcrumb_click(self, index):
        self.paths = self.paths[: index + 1]
        if index == 0:
            self.rana_widget.setCurrentIndex(0)
            self.update_breadcrumbs()
        else:
            only_directory_paths = self.paths[2:]  # Skip the first two paths: Home and Project
            path = "/".join(only_directory_paths) + ("/" if only_directory_paths else "")
            self.fetch_files(path)
            self.show_files_widget()

    def fetch_projects(self):
        self.projects = get_tenant_projects(TENANT)
        self.projects_model.clear()
        header = ["Name"]
        self.projects_model.setHorizontalHeaderLabels(header)
        for project in self.projects:
            name_item = QStandardItem(project["name"])
            name_item.setData(project, role=Qt.UserRole)
            project_items = [name_item]
            self.projects_model.appendRow(project_items)
        for i in range(len(header)):
            self.projects_tv.resizeColumnToContents(i)
        self.projects_tv.doubleClicked.connect(self.select_project)

    def select_project(self, index):
        project_item = self.projects_model.itemFromIndex(index)
        self.project = project_item.data(Qt.UserRole)
        self.paths.append(self.project["name"])
        self.fetch_files()
        self.show_files_widget()

    def fetch_files(self, path: str = None):
        self.files = get_tenant_project_files(TENANT, self.project["id"], {"path": path} if path else None)
        self.files_model.clear()
        header = ["Name"]
        self.files_model.setHorizontalHeaderLabels(header)
        for file in self.files:
            file_name = os.path.basename(file["id"].rstrip("/"))
            display_icon = "📁" if file["type"] == "directory" else "📄"
            display_name = f"{display_icon} {file_name}"
            name_item = QStandardItem(display_name)
            name_item.setData(file, role=Qt.UserRole)
            file_items = [name_item]
            self.files_model.appendRow(file_items)
        for i in range(len(header)):
            self.files_tv.resizeColumnToContents(i)

    def select_file_or_directory(self, index):
        file_item = self.files_model.itemFromIndex(index)
        self.file = file_item.data(Qt.UserRole)
        file_path = self.file["id"]
        if self.file["type"] == "directory":
            directory_name = os.path.basename(file_path.rstrip("/"))
            self.paths.append(directory_name)
            self.fetch_files(file_path)
            self.rana_widget.setCurrentIndex(1)
        else:
            file_name = os.path.basename(file_path.rstrip("/"))
            self.paths.append(file_name)
            self.show_file_details()
            self.rana_widget.setCurrentIndex(2)
        self.update_breadcrumbs()

    def show_file_details(self):
        self.file_table_widget.clearContents()
        file_details = [
            ("Name", os.path.basename(self.file["id"].rstrip("/"))),
            ("Size", f"{self.file['size']} bytes"),
            ("Type", self.file["media_type"]),
        ]
        for i, (label, value) in enumerate(file_details):
            self.file_table_widget.setItem(i, 0, QTableWidgetItem(label))
            self.file_table_widget.setItem(i, 1, QTableWidgetItem(value))
        self.file_table_widget.resizeColumnsToContents()

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
                project_name=self.project["name"],
                file_path=file_path,
                file_name=file_name,
            )
            if not local_file_path:
                QgsMessageLog.logMessage(f"Download failed. Unable to open {data_type} file in QGIS.")
                return

            # Save the last modified date of the downloaded file in QSettings
            last_modified_key = f"{self.project['name']}/{file_path}/last_modified"
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
        if not self.file or not self.project["id"]:
            return
        file_name = os.path.basename(self.file["id"].rstrip("/"))
        file_path = self.file["id"]
        _, local_file_path = get_local_file_path(self.project["name"], file_path, file_name)

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
            upload_response = start_file_upload(TENANT, self.project["id"], {"path": file_path})
            if not upload_response:
                QgsMessageLog.logMessage("Failed to initiate upload.")
                return
            upload_url = upload_response["urls"][0]
            # Step 2: Upload the file to the upload_url
            with open(local_file_path, "rb") as file:
                response = requests.put(upload_url, data=file)
                response.raise_for_status()
            # Step 3: Complete the upload
            finish_file_upload(TENANT, self.project["id"], upload_response)
        except Exception as e:
            QgsMessageLog.logMessage(f"Error uploading file to Rana: {str(e)}")

    def check_for_file_conflict(self):
        file_path = self.file["id"]
        last_modified_key = f"{self.project['name']}/{file_path}/last_modified"
        local_last_modified = self.settings.value(last_modified_key)
        server_file = get_tenant_project_file(TENANT, self.project["id"], {"path": file_path})
        last_modified = server_file["last_modified"]
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
