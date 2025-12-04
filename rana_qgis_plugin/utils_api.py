import math
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


def get_frontend_settings():
    url = f"{api_url()}/frontend-settings"
    network_manager = NetworkManager(url, get_authcfg_id())
    status = network_manager.fetch()

    if status:
        response = network_manager.content
        return response
    else:
        return None


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


def get_tenant_details(communication: UICommunication):
    authcfg_id = get_authcfg_id()
    tenant = get_tenant_id()
    url = f"{api_url()}/tenants/{tenant}"

    network_manager = NetworkManager(url, authcfg_id)
    status, error = network_manager.fetch()

    if status:
        response = network_manager.content
        return response
    else:
        communication.show_error(f"Failed to get tenant details: {error}")
        return {}


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


def delete_tenant_project_file(project_id: str, params: dict):
    authcfg_id = get_authcfg_id()
    tenant = get_tenant_id()
    url = f"{api_url()}/tenants/{tenant}/projects/{project_id}/files/delete"

    network_manager = NetworkManager(url, authcfg_id)
    status, _ = network_manager.delete(params)

    if status:
        return True
    else:
        return False


def create_tenant_project_directory(project_id: str, path: str):
    authcfg_id = get_authcfg_id()
    tenant = get_tenant_id()
    url = f"{api_url()}/tenants/{tenant}/projects/{project_id}/directories/create"

    network_manager = NetworkManager(url, authcfg_id)
    status, _ = network_manager.post(params={"path": path})

    if status:
        return True
    else:
        return False


def delete_tenant_project_directory(project_id: str, params: dict):
    authcfg_id = get_authcfg_id()
    tenant = get_tenant_id()
    url = f"{api_url()}/tenants/{tenant}/projects/{project_id}/directories/delete"

    network_manager = NetworkManager(url, authcfg_id)
    status, _ = network_manager.delete(params)

    if status:
        return True
    else:
        return False


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


def get_tenant_project_file_history(project_id: str, params: dict):
    authcfg_id = get_authcfg_id()
    tenant = get_tenant_id()
    url = f"{api_url()}/tenants/{tenant}/projects/{project_id}/files/history"

    network_manager = NetworkManager(url, authcfg_id)
    status = network_manager.fetch(params)

    if status:
        response = network_manager.content
        return response
    else:
        return None


def get_tenant_file_url(project_id: str, params: dict):
    authcfg_id = get_authcfg_id()
    tenant = get_tenant_id()
    url = f"{api_url()}/tenants/{tenant}/projects/{project_id}/files/download"

    network_manager = NetworkManager(url, authcfg_id)
    status = network_manager.fetch(params)

    if status:
        response = network_manager.content
        return response.get("url")
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


def create_raster_tasks(
    descriptor_id: str,
    raster_id: str,
    spatial_bounds,
    projection: str,
    no_data: int = None,
):
    """
    Create Lizard raster tasks for a raster.
    Reimplemented code from https://github.com/nens/lizard-qgis-plugin
    """
    bboxes, width, height = spatial_bounds
    raster_tasks = []
    for x1, y1, x2, y2 in bboxes:
        bbox = f"{x1},{y1},{x2},{y2}"
        payload = {
            "width": width,
            "height": height,
            "bbox": bbox,
            "projection": projection,
            "format": "geotiff",
            "async": "true",
        }
        if no_data is not None:
            payload["nodata"] = no_data
        r = request_raster_generate(
            descriptor_id=descriptor_id, raster_id=raster_id, payload=payload
        )
        raster_tasks.append(r)

    return raster_tasks


def request_raster_generate(descriptor_id: str, raster_id: str, payload: dict):
    authcfg_id = get_authcfg_id()
    tenant = get_tenant_id()
    url = f"{api_url()}/tenants/{tenant}/file-descriptors/{descriptor_id}/raster/{raster_id}/task"

    network_manager = NetworkManager(url, authcfg_id)
    status, _ = network_manager.post(payload=payload)

    if status:
        response = network_manager.content
        return response
    else:
        raise Exception(network_manager.description())


def get_raster_file_link(descriptor_id: str, task_id: str):
    authcfg_id = get_authcfg_id()
    tenant = get_tenant_id()
    url = (
        f"{api_url()}/tenants/{tenant}/file-descriptors/{descriptor_id}/raster/"
        + "{raster_id}"
        + f"/task/{task_id}"
    )

    network_manager = NetworkManager(url, authcfg_id)
    status, error = network_manager.fetch()
    if status:
        response = network_manager.content
        if response["status"] == "failure":
            split_response = response["detail"].split('"')
            message = split_response[split_response.index("msg") + 2]
            raise Exception(f"Raster generation failed: {message}")
        elif response["status"] == "success":
            return response["result"]
        else:
            return False  # retry after interval
    else:
        raise Exception(f"Failed to retrieve raster: {error}")


def get_tenant_processes(communication: UICommunication):
    authcfg_id = get_authcfg_id()
    tenant = get_tenant_id()
    url = f"{api_url()}/tenants/{tenant}/processes"
    params = {"limit": 1000}

    network_manager = NetworkManager(url, authcfg_id)
    status, error = network_manager.fetch(params)

    if status:
        response = network_manager.content
        items = response["items"]
        return items
    else:
        communication.show_error(f"Failed to get processes: {error}")
        return []


def start_tenant_process(communication: UICommunication, process_id, params: dict):
    authcfg_id = get_authcfg_id()
    tenant = get_tenant_id()
    url = f"{api_url()}/tenants/{tenant}/processes/{process_id}/execution"

    network_manager = NetworkManager(url, authcfg_id)
    status, error = network_manager.post(payload=params)

    if status:
        return network_manager.content
    else:
        communication.show_error(f"Failed to start process {process_id}: {error}")
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


def add_threedi_schematisation(communication: UICommunication, project_id: str, schematisation_id: str, path: str):
    authcfg_id = get_authcfg_id()
    tenant = get_tenant_id()
    url = f"{api_url()}/tenants/{tenant}/projects/{project_id}/threedi-schematisations"

    network_manager = NetworkManager(url, authcfg_id)
    status = network_manager.post(params={"schematisation_id": schematisation_id, "path": path})

    if status:
        response = network_manager.content
        return response
    else:
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


def get_filename_from_attachment_url(attachment_url: str) -> str:
    return attachment_url.rsplit("/", 1)[-1].split("?", 1)[0]


def map_result_to_file_name(result: dict) -> str:
    if result["name"] == "Raw 3Di output":
        return "results_3di.nc"
    elif result["name"] == "Grid administration":
        return "gridadmin.h5"
    else:
        if result["attachment_url"]:
            return get_filename_from_attachment_url(result["attachment_url"])
        else:
            return result["code"]
