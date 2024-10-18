from .auth import get_authcfg_id
from .communication import UICommunication
from .constant import BASE_URL
from .network_manager import NetworkManager


def get_tenant(communication: UICommunication, tenant: str):
    authcfg_id = get_authcfg_id()
    tenant_url = f"{BASE_URL}/tenants/{tenant}"

    network_manager = NetworkManager(tenant_url, authcfg_id)
    status, error = network_manager.fetch()

    if status:
        tenant = network_manager.content
        return tenant
    else:
        communication.show_error(f"Failed to get tenant: {error}")
        return None


def get_tenant_projects(communication: UICommunication, tenant: str):
    authcfg_id = get_authcfg_id()
    url = f"{BASE_URL}/tenants/{tenant}/projects"

    network_manager = NetworkManager(url, authcfg_id)
    status, error = network_manager.fetch()

    if status:
        response = network_manager.content
        items = response["items"]
        return items
    else:
        communication.show_error(f"Failed to get projects: {error}")
        return []


def get_tenant_project_files(communication: UICommunication, tenant: str, project_id: str, params: dict = None):
    authcfg_id = get_authcfg_id()
    url = f"{BASE_URL}/tenants/{tenant}/projects/{project_id}/files/ls"

    network_manager = NetworkManager(url, authcfg_id)
    status, error = network_manager.fetch(params)

    if status:
        response = network_manager.content
        items = response["items"]
        return items
    else:
        communication.show_error(f"Failed to get files: {error}")
        return []


def get_tenant_project_file(communication: UICommunication, tenant: str, project_id: str, params: dict):
    authcfg_id = get_authcfg_id()
    url = f"{BASE_URL}/tenants/{tenant}/projects/{project_id}/files/stat"

    network_manager = NetworkManager(url, authcfg_id)
    status, error = network_manager.fetch(params)

    if status:
        response = network_manager.content
        return response
    else:
        communication.show_error(f"Failed to get file: {error}")
        return None


def start_file_upload(communication: UICommunication, tenant: str, project_id: str, params: dict):
    communication.clear_message_bar()
    communication.bar_info("Initiating file upload ...")
    authcfg_id = get_authcfg_id()
    url = f"{BASE_URL}/tenants/{tenant}/projects/{project_id}/files/upload"

    network_manager = NetworkManager(url, authcfg_id)
    status, error = network_manager.post(params=params)

    if status:
        response = network_manager.content
        return response
    else:
        communication.show_error(f"Failed to initiate file upload: {error}")
        return None


def finish_file_upload(communication: UICommunication, tenant: str, project_id: str, payload: dict):
    authcfg_id = get_authcfg_id()
    url = f"{BASE_URL}/tenants/{tenant}/projects/{project_id}/files/upload"
    network_manager = NetworkManager(url, authcfg_id)
    status, error = network_manager.put(payload=payload)
    if status:
        communication.clear_message_bar()
        communication.bar_info("File uploaded to Rana successfully.")
        communication.show_info("File uploaded to Rana successfully.")
    else:
        communication.show_error(f"Failed to upload file: {error}")
    return None


def get_threedi_schematisation(communication: UICommunication, tenant: str, descriptor_id: str):
    authcfg_id = get_authcfg_id()
    url = f"{BASE_URL}/tenants/{tenant}/file-descriptors/{descriptor_id}/threedi-schematisation"
    network_manager = NetworkManager(url, authcfg_id)
    status, error = network_manager.fetch()
    if status:
        response = network_manager.content
        return response
    else:
        communication.show_error(f"Failed to retrieve schematisation: {error}")
        return None
