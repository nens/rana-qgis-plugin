import os

import requests
from qgis.core import QgsMessageLog, QgsProject, QgsRasterLayer, QgsVectorLayer
from qgis.PyQt.QtCore import QSettings
from qgis.PyQt.QtWidgets import QMessageBox

from .auth import get_authcfg_id
from .constant import BASE_URL, TENANT
from .network_manager import NetworkManager


def get_tenant(tenant: str):
    authcfg_id = get_authcfg_id()
    tenant_url = f"{BASE_URL}/tenants/{tenant}"

    network_manager = NetworkManager(tenant_url, authcfg_id)
    status, error = network_manager.fetch()

    if status:
        tenant = network_manager.content
        return tenant
    else:
        QgsMessageLog.logMessage(f"Error: {error}")
        return None


def get_tenant_projects(tenant: str):
    authcfg_id = get_authcfg_id()
    url = f"{BASE_URL}/tenants/{tenant}/projects"

    network_manager = NetworkManager(url, authcfg_id)
    status, error = network_manager.fetch()

    if status:
        response = network_manager.content
        items = response["items"]
        return items
    else:
        QgsMessageLog.logMessage(f"Error: {error}")
        return None


def get_tenant_project_files(tenant: str, project_id: str, params: dict = None):
    authcfg_id = get_authcfg_id()
    url = f"{BASE_URL}/tenants/{tenant}/projects/{project_id}/files/ls"

    network_manager = NetworkManager(url, authcfg_id)
    status, error = network_manager.fetch(params)

    if status:
        response = network_manager.content
        items = response["items"]
        return items
    else:
        QgsMessageLog.logMessage(f"Error: {error}")
        return None


def get_tenant_project_file(tenant: str, project_id: str, params: dict):
    authcfg_id = get_authcfg_id()
    url = f"{BASE_URL}/tenants/{tenant}/projects/{project_id}/files/stat"

    network_manager = NetworkManager(url, authcfg_id)
    status, error = network_manager.fetch(params)

    if status:
        response = network_manager.content
        return response
    else:
        QgsMessageLog.logMessage(f"Error: {error}")
        return None


def start_file_upload(tenant: str, project_id: str, params: dict):
    authcfg_id = get_authcfg_id()
    url = f"{BASE_URL}/tenants/{tenant}/projects/{project_id}/files/upload"

    network_manager = NetworkManager(url, authcfg_id)
    status, error = network_manager.post(params=params)

    if status:
        response = network_manager.content
        return response
    else:
        QgsMessageLog.logMessage(f"Error: {error}")
        return None


def finish_file_upload(tenant: str, project_id: str, payload: dict):
    authcfg_id = get_authcfg_id()
    url = f"{BASE_URL}/tenants/{tenant}/projects/{project_id}/files/upload"
    network_manager = NetworkManager(url, authcfg_id)
    status, error = network_manager.put(payload=payload)
    if status:
        QgsMessageLog.logMessage("File successfully uploaded to Rana.")
    else:
        QgsMessageLog.logMessage(f"Error completing file upload: {error}")
    return None


def download_file(url: str, project_name: str, file_path: str, file_name: str):
    local_dir_structure, local_file_path = get_local_file_path(project_name, file_path, file_name)
    os.makedirs(local_dir_structure, exist_ok=True)  # Create the directory structure locally
    try:
        response = requests.get(url)
        response.raise_for_status()
        with open(local_file_path, "wb") as file:
            file.write(response.content)
        return local_file_path
    except requests.exceptions.RequestException as e:
        QgsMessageLog.logMessage(f"Failed to download file: {str(e)}")
        return None
    except Exception as e:
        QgsMessageLog.logMessage(f"An error occurred: {str(e)}")
        return None


def get_local_file_path(project_name: str, file_path: str, file_name: str):
    base_dir = os.path.join(os.path.expanduser("~"), "Rana")
    local_dir_structure = os.path.join(base_dir, project_name, os.path.dirname(file_path))
    local_file_path = os.path.join(local_dir_structure, file_name)
    return local_dir_structure, local_file_path


def open_file_in_qgis(project, file):
    if file and file["descriptor"] and file["descriptor"]["data_type"]:
        data_type = file["descriptor"]["data_type"]
        if data_type not in ["vector", "raster"]:
            QgsMessageLog.logMessage(f"Unsupported data type: {data_type}")
            return
        download_url = file["url"]
        file_path = file["id"]
        file_name = os.path.basename(file_path.rstrip("/"))
        local_file_path = download_file(
            url=download_url,
            project_name=project["name"],
            file_path=file_path,
            file_name=file_name,
        )
        if not local_file_path:
            QgsMessageLog.logMessage(f"Download failed. Unable to open {data_type} file in QGIS.")
            return

        # Save the last modified date of the downloaded file in QSettings
        last_modified_key = f"{project['name']}/{file_path}/last_modified"
        QSettings().setValue(last_modified_key, file["last_modified"])

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
        QgsMessageLog.logMessage(f"Unsupported data type: {file['media_type']}")


def save_file_to_rana(project, file):
    if not file or not project["id"]:
        return
    file_name = os.path.basename(file["id"].rstrip("/"))
    file_path = file["id"]
    _, local_file_path = get_local_file_path(project["name"], file_path, file_name)

    # Check if file exists locally before uploading
    if not os.path.exists(local_file_path):
        QgsMessageLog.logMessage(f"File not found: {local_file_path}")
        return

    # Check if file has been modified since it was last downloaded
    has_file_conflict = check_for_file_conflict(project, file)
    if has_file_conflict:
        return

    # Save file to Rana
    try:
        # Step 1: POST request to initiate the upload
        upload_response = start_file_upload(TENANT, project["id"], {"path": file_path})
        if not upload_response:
            QgsMessageLog.logMessage("Failed to initiate upload.")
            return
        upload_url = upload_response["urls"][0]
        # Step 2: Upload the file to the upload_url
        with open(local_file_path, "rb") as file:
            response = requests.put(upload_url, data=file)
            response.raise_for_status()
        # Step 3: Complete the upload
        finish_file_upload(TENANT, project["id"], upload_response)
    except Exception as e:
        QgsMessageLog.logMessage(f"Error uploading file to Rana: {str(e)}")


def check_for_file_conflict(project, file):
    file_path = file["id"]
    last_modified_key = f"{project['name']}/{file_path}/last_modified"
    local_last_modified = QSettings().value(last_modified_key)
    server_file = get_tenant_project_file(TENANT, project["id"], {"path": file_path})
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
