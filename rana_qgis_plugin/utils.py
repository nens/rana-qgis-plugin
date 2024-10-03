import os
import requests

from qgis.core import QgsMessageLog

from .network_manager import NetworkManager
from .constant import BASE_URL, OAUTH2_ID

def get_tenant(tenant: str):
    tenant_url = f"{BASE_URL}/tenants/{tenant}"

    network_manager = NetworkManager(tenant_url, OAUTH2_ID)
    status, error = network_manager.fetch()

    if status:
        tenant = network_manager.content
        return tenant
    else:
        QgsMessageLog.logMessage(f"Error: {error}")

def get_tenant_projects(tenant: str):
    url = f"{BASE_URL}/tenants/{tenant}/projects"

    network_manager = NetworkManager(url, OAUTH2_ID)
    status, error = network_manager.fetch()

    if status:
        response = network_manager.content
        items = response["items"]
        return items
    else:
        QgsMessageLog.logMessage(f"Error: {error}")

def get_tenant_project_files(tenant: str, project_id: str, params: dict = None):
    url = f"{BASE_URL}/tenants/{tenant}/projects/{project_id}/files/ls"

    network_manager = NetworkManager(url, OAUTH2_ID)
    status, error = network_manager.fetch(params)

    if status:
        response = network_manager.content
        items = response["items"]
        return items
    else:
        QgsMessageLog.logMessage(f"Error: {error}")

def download_open_raster_file(url, file_name):
    local_file_path = os.path.join("/tests_directory", file_name)
    try:
        response = requests.get(url)
        response.raise_for_status()
        with open(local_file_path, "wb") as file:
            file.write(response.content)
        return local_file_path
    except requests.exceptions.RequestException as e:
        QgsMessageLog.logMessage(f"Failed to download file: {str(e)}")
    except Exception as e:
        QgsMessageLog.logMessage(f"An error occurred: {str(e)}")
