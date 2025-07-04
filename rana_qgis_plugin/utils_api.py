from typing import Optional, TypedDict

import requests

from rana_qgis_plugin.auth import get_authcfg_id
from rana_qgis_plugin.communication import UICommunication
from rana_qgis_plugin.constant import COGNITO_USER_INFO_ENDPOINT
from rana_qgis_plugin.network_manager import NetworkManager
from rana_qgis_plugin.utils_settings import api_url, get_tenant_id


class UserInfo(TypedDict):
    sub: str  # user_id
    given_name: str
    family_name: str
    email: str


def get_user_info(communication: UICommunication) -> Optional[UserInfo]:
    authcfg_id = get_authcfg_id()
    url = COGNITO_USER_INFO_ENDPOINT

    network_manager = NetworkManager(url, authcfg_id)
    status, error = network_manager.fetch()

    if status:
        user = network_manager.content
        return user
    else:
        communication.show_error(f"Failed to get user info from cognito: {error}")
        return None


def get_user_tenants(communication: UICommunication, user_id: str):
    authcfg_id = get_authcfg_id()
    url = f"{api_url()}/tenants"
    params = {"user_id": user_id}

    network_manager = NetworkManager(url, authcfg_id)
    status, error = network_manager.fetch(params)

    if status:
        response = network_manager.content
        items = response["items"]
        return items
    else:
        communication.show_error(f"Failed to get tenants: {error}")
        return []


def get_tenant_projects(communication: UICommunication):
    authcfg_id = get_authcfg_id()
    tenant = get_tenant_id()
    url = f"{api_url()}/tenants/{tenant}/projects"
    params = {"limit": 1000}

    network_manager = NetworkManager(url, authcfg_id)
    status, error = network_manager.fetch(params)

    if status:
        response = network_manager.content
        items = response["items"]
        return items
    else:
        communication.show_error(f"Failed to get projects: {error}")
        return []


def get_tenant_project_files(
    communication: UICommunication, project_id: str, params: dict = None
):
    authcfg_id = get_authcfg_id()
    tenant = get_tenant_id()
    url = f"{api_url()}/tenants/{tenant}/projects/{project_id}/files/ls"

    network_manager = NetworkManager(url, authcfg_id)
    status, error = network_manager.fetch(params)

    if status:
        response = network_manager.content
        items = response["items"]
        return items
    else:
        communication.show_error(f"Failed to get files: {error}")
        return []


def get_tenant_project_file(project_id: str, params: dict):
    authcfg_id = get_authcfg_id()
    tenant = get_tenant_id()
    url = f"{api_url()}/tenants/{tenant}/projects/{project_id}/files/stat"

    network_manager = NetworkManager(url, authcfg_id)
    status = network_manager.fetch(params)

    if status:
        response = network_manager.content
        return response
    else:
        return None


def get_tenant_file_descriptor(descriptor_id: str):
    authcfg_id = get_authcfg_id()
    tenant = get_tenant_id()
    url = f"{api_url()}/tenants/{tenant}/file-descriptors/{descriptor_id}"
    network_manager = NetworkManager(url, authcfg_id)
    status = network_manager.fetch()

    if status:
        response = network_manager.content
        return response
    else:
        return None


def get_tenant_file_descriptor_view(descriptor_id: str, view_type: str):
    authcfg_id = get_authcfg_id()
    tenant = get_tenant_id()
    url = f"{api_url()}/tenants/{tenant}/file-descriptors/{descriptor_id}/{view_type}"
    network_manager = NetworkManager(url, authcfg_id)
    status = network_manager.fetch()

    if status:
        response = network_manager.content
        return response
    else:
        return None


def start_file_upload(project_id: str, params: dict):
    authcfg_id = get_authcfg_id()
    tenant = get_tenant_id()
    url = f"{api_url()}/tenants/{tenant}/projects/{project_id}/files/upload"

    network_manager = NetworkManager(url, authcfg_id)
    status = network_manager.post(params=params)

    if status:
        response = network_manager.content
        return response
    else:
        return None


def finish_file_upload(project_id: str, payload: dict):
    authcfg_id = get_authcfg_id()
    tenant = get_tenant_id()
    url = f"{api_url()}/tenants/{tenant}/projects/{project_id}/files/upload"
    network_manager = NetworkManager(url, authcfg_id)
    status = network_manager.put(payload=payload)
    if status:
        response = network_manager.content
        return response
    return None


def get_vector_style_upload_urls(descriptor_id: str):
    authcfg_id = get_authcfg_id()
    tenant = get_tenant_id()
    url = f"{api_url()}/tenants/{tenant}/file-descriptors/{descriptor_id}/vector-style"

    network_manager = NetworkManager(url, authcfg_id)
    status = network_manager.put()

    if status:
        response = network_manager.content
        return response
    else:
        return None


def get_vector_style_file(descriptor_id: str, file_name: str):
    authcfg_id = get_authcfg_id()
    tenant = get_tenant_id()
    url = f"{api_url()}/tenants/{tenant}/file-descriptors/{descriptor_id}/vector-style/{file_name}"

    network_manager = NetworkManager(url, authcfg_id)
    status, redirect_url = network_manager.fetch()

    if status and redirect_url:
        try:
            headers = {"Content-Type": "application/zip"}
            response = requests.get(redirect_url, headers=headers, timeout=10)
            return response.content
        except requests.RequestException as e:
            return None
    else:
        return None


def get_threedi_schematisation(communication: UICommunication, descriptor_id: str):
    authcfg_id = get_authcfg_id()
    tenant = get_tenant_id()
    url = f"{api_url()}/tenants/{tenant}/file-descriptors/{descriptor_id}/threedi-schematisation"
    network_manager = NetworkManager(url, authcfg_id)
    status, error = network_manager.fetch()
    if status:
        response = network_manager.content
        return response
    else:
        communication.show_error(f"Failed to retrieve schematisation: {error}")
        return None


def get_threedi_personal_api_key(
    communication: UICommunication, user_id: str
) -> Optional[str]:
    communication.clear_message_bar()
    communication.bar_info("Getting 3Di personal API key ...")
    authcfg_id = get_authcfg_id()
    tenant = get_tenant_id()
    url = f"{api_url()}/tenants/{tenant}/users/{user_id}/3di-personal-api-keys"

    network_manager = NetworkManager(url, authcfg_id)
    status, error = network_manager.post()

    if status:
        response = network_manager.content
        if "key" in response:
            return response["key"]
        else:
            communication.show_error("Failed to retrieve 3Di personal API key.")
            return None
    else:
        communication.show_error(f"Failed to retrieve 3Di personal api key: {error}")
        return None
