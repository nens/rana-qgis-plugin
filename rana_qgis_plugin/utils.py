import math
import os

import requests
from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer
from qgis.PyQt.QtCore import QSettings, Qt
from qgis.PyQt.QtGui import QFont, QFontMetrics

from .communication import UICommunication
from .constant import TENANT
from .utils_api import finish_file_upload, get_tenant_project_file, start_file_upload
from .utils_qgis import get_schematisation_editor_instance, get_threedi_models_and_simulations_instance


def download_file(communication: UICommunication, url: str, project_name: str, file_path: str, file_name: str):
    local_dir_structure, local_file_path = get_local_file_path(project_name, file_path, file_name)
    os.makedirs(local_dir_structure, exist_ok=True)  # Create the directory structure locally
    try:
        response = requests.get(url)
        response.raise_for_status()
        with open(local_file_path, "wb") as file:
            file.write(response.content)
        return local_file_path
    except requests.exceptions.RequestException as e:
        communication.show_error(f"Failed to download file: {str(e)}")
        return None
    except Exception as e:
        communication.show_error(f"An error occurred: {str(e)}")
        return None


def get_local_file_path(project_name: str, file_path: str, file_name: str):
    base_dir = os.path.join(os.path.expanduser("~"), "Rana")
    local_dir_structure = os.path.join(base_dir, project_name, os.path.dirname(file_path))
    local_file_path = os.path.join(local_dir_structure, file_name)
    return local_dir_structure, local_file_path


def open_file_in_qgis(communication: UICommunication, project: dict, file: dict, supported_data_types: list):
    if file and file["descriptor"] and file["descriptor"]["data_type"]:
        data_type = file["descriptor"]["data_type"]
        if data_type not in supported_data_types:
            communication.show_warn(f"Unsupported data type: {data_type}")
            return
        download_url = file["url"]
        file_path = file["id"]
        file_name = os.path.basename(file_path.rstrip("/"))
        local_file_path = download_file(
            communication=communication,
            url=download_url,
            project_name=project["name"],
            file_path=file_path,
            file_name=file_name,
        )
        if not local_file_path:
            communication.show_error(f"Download failed. Unable to open {data_type} file in QGIS.")
            return

        # Save the last modified date of the downloaded file in QSettings
        last_modified_key = f"{project['name']}/{file_path}/last_modified"
        QSettings().setValue(last_modified_key, file["last_modified"])

        # Add the layer to QGIS
        if data_type == "vector":
            layer = QgsVectorLayer(local_file_path, file_name, "ogr")
        elif data_type == "raster":
            layer = QgsRasterLayer(local_file_path, file_name)
        elif data_type == "threedi_schematisation":
            threedi_models_and_simulations = get_threedi_models_and_simulations_instance()
            threedi_schematisation_editor = get_schematisation_editor_instance()
            if not threedi_models_and_simulations:
                communication.show_error(
                    "Please enable the 3Di Models and Simulations plugin to open this schematisation."
                )
                return
            if not threedi_schematisation_editor:
                communication.show_error(
                    "Please enable the 3Di Schematisation Editor plugin to open this schematisation."
                )
                return
            communication.bar_info("Opening the schematisation in 3Di Models and Simulations plugin ...")
            threedi_models_and_simulations.run()
            threedi_models_and_simulations.dockwidget.test_dockwidget()
            return
        else:
            communication.show_warn(f"Unsupported data type: {data_type}")
            return
        if layer.isValid():
            QgsProject.instance().addMapLayer(layer)
            communication.clear_message_bar()
            communication.bar_info(f"Added {data_type} layer: {local_file_path}")
        else:
            communication.show_error(f"Failed to add {data_type} layer: {local_file_path}")
    else:
        communication.show_warn(f"Unsupported data type: {file['media_type']}")


def save_file_to_rana(communication: UICommunication, project: dict, file: dict):
    if not file or not project["id"]:
        return
    file_name = os.path.basename(file["id"].rstrip("/"))
    file_path = file["id"]
    _, local_file_path = get_local_file_path(project["name"], file_path, file_name)

    # Check if file exists locally before uploading
    if not os.path.exists(local_file_path):
        communication.clear_message_bar()
        communication.bar_error(f"File not found: {local_file_path}")
        return

    # Check if file has been modified since it was last downloaded
    continue_upload = handle_file_conflict(communication, project, file)
    if not continue_upload:
        return

    # Save file to Rana
    try:
        # Step 1: POST request to initiate the upload
        upload_response = start_file_upload(communication, TENANT, project["id"], {"path": file_path})
        if not upload_response:
            communication.show_error("Failed to initiate file upload.")
            return
        upload_url = upload_response["urls"][0]
        # Step 2: Upload the file to the upload_url
        with open(local_file_path, "rb") as file:
            response = requests.put(upload_url, data=file)
            response.raise_for_status()
        # Step 3: Complete the upload
        finish_file_upload(communication, TENANT, project["id"], upload_response)
    except Exception as e:
        communication.show_error(f"Failed to upload file to Rana: {str(e)}")


def handle_file_conflict(communication: UICommunication, project: dict, file: dict):
    file_path = file["id"]
    last_modified_key = f"{project['name']}/{file_path}/last_modified"
    local_last_modified = QSettings().value(last_modified_key)
    server_file = get_tenant_project_file(communication, TENANT, project["id"], {"path": file_path})
    if not server_file:
        communication.show_error("Failed to get file from server. Check if file has been moved or deleted.")
        return False  # Stop with the upload
    last_modified = server_file["last_modified"]
    if last_modified != local_last_modified:
        warn_and_ask_msg = (
            "The file has been modified on the server since it was last downloaded.\n"
            "Do you want to overwrite the server copy with the local copy?"
        )
        do_overwrite = communication.ask(None, "File conflict", warn_and_ask_msg)
        return do_overwrite
    else:
        return True  # Continue with the upload


def display_bytes(bytes: int) -> str:
    sizes = ["Bytes", "KB", "MB", "GB", "TB"]
    if bytes == 0:
        return "0 Byte"
    i = int(math.floor(math.log(bytes, 1024)))
    p = math.pow(1024, i)
    s = round(bytes / p, 2)
    return f"{s} {sizes[i]}"


def elide_text(font: QFont, text: str, max_width: int) -> str:
    # Calculate elided text based on font and max width
    font_metrics = QFontMetrics(font)
    return font_metrics.elidedText(text, Qt.ElideRight, max_width)
