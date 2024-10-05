import os

import requests
from qgis.core import QgsMessageLog

from .auth import get_authcfg_id
from .constant import BASE_URL
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
    base_dir = os.getcwd()  # Get the current working directory
    local_dir_structure = os.path.join(base_dir, project_name, os.path.dirname(file_path))
    local_file_path = os.path.join(local_dir_structure, file_name)
    return local_dir_structure, local_file_path
