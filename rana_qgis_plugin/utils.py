import math
import os
from datetime import datetime, timezone

import requests
from dateutil import parser
from dateutil.relativedelta import relativedelta
from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer
from qgis.PyQt.QtCore import QSettings, Qt
from qgis.PyQt.QtGui import QFont, QFontMetrics, QStandardItem

from .communication import UICommunication
from .constant import TENANT
from .utils_api import finish_file_upload, get_tenant_project_file, start_file_upload
from .utils_qgis import get_threedi_models_and_simulations_instance


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


def open_file_in_qgis(
    communication: UICommunication,
    project: dict,
    file: dict,
    schematisation_instance: dict,
    supported_data_types: list,
):
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
        elif data_type == "threedi_schematisation" and schematisation_instance:
            threedi_models_and_simulations = get_threedi_models_and_simulations_instance()
            if not threedi_models_and_simulations:
                communication.show_error(
                    "Please enable the 3Di Models and Simulations plugin to open this schematisation."
                )
                return
            schematisation = schematisation_instance["schematisation"]
            revision = schematisation_instance["latest_revision"]
            if not revision:
                communication.show_warn("Cannot open a schematisation without a revision.")
                return
            communication.clear_message_bar()
            communication.bar_info(f"Opening the schematisation in the 3Di Models and Simulations plugin...")
            threedi_models_and_simulations.run()
            threedi_models_and_simulations.dockwidget.build_options.load_remote_schematisation(schematisation, revision)
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


def convert_to_timestamp(timestamp: str):
    dt = datetime.fromisoformat(timestamp)
    return dt.timestamp()


def convert_to_local_time(timestamp: str):
    time = parser.isoparse(timestamp)
    return time.astimezone().strftime("%d-%m-%Y %H:%M")


def convert_to_relative_time(timestamp: str):
    """Convert a timestamp into a relative time string."""
    now = datetime.now(timezone.utc)
    past = parser.isoparse(timestamp)
    delta = relativedelta(now, past)

    if delta.years > 0:
        return f"{delta.years} year{'s' if delta.years > 1 else ''} ago"
    elif delta.months > 0:
        return f"{delta.months} month{'s' if delta.months > 1 else ''} ago"
    elif delta.days > 0:
        return f"{delta.days} day{'s' if delta.days > 1 else ''} ago"
    elif delta.hours > 0:
        return f"{delta.hours} hour{'s' if delta.hours > 1 else ''} ago"
    elif delta.minutes > 0:
        return f"{delta.minutes} minute{'s' if delta.minutes > 1 else ''} ago"
    else:
        return "Just now"


class NumericItem(QStandardItem):
    def __lt__(self, other):
        return self.data(Qt.UserRole) < other.data(Qt.UserRole)
