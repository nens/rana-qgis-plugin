from typing import Optional, TypedDict

from time import sleep

import requests
import math

from rana_qgis_plugin.auth import get_authcfg_id
from rana_qgis_plugin.communication import UICommunication
from rana_qgis_plugin.constant import COGNITO_USER_INFO_ENDPOINT
from rana_qgis_plugin.network_manager import NetworkManager
from rana_qgis_plugin.utils import get_filename_from_attachment_url
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


def split_scenario_extent(
    grid, resolution=None, max_pixel_count=1 * 10**8
):
    """
    Split raster task spatial bounds to fit in to maximum pixel count limit.
    Reimplemented code from https://github.com/nens/threedi-scenario-downloader
    """
    x1 = grid["x"]["origin"]
    y1 = grid["y"]["origin"]
    size_x = grid["x"]["size"]
    size_y = grid["y"]["size"]
    x2 = x1 + size_x
    y2 = y1 + size_y
    if resolution is None:
        pixelsize_x = grid["x"]["cell_size"]
        pixelsize_y = grid["y"]["cell_size"]
    else:
        pixelsize_x = resolution
        pixelsize_y = resolution
    pixelcount_x = abs(size_x / pixelsize_x)
    pixelcount_y = abs(size_y / pixelsize_y)
    if not pixelcount_x.is_integer():
        pixelcount_x = math.ceil(pixelcount_x)
        x2 = (pixelcount_x * pixelsize_x) + x1
    if not pixelcount_y.is_integer():
        pixelcount_y = math.ceil(pixelcount_y)
        y2 = (pixelcount_y * pixelsize_y) + y1
    raster_pixel_count = pixelcount_x * pixelcount_y
    if raster_pixel_count > max_pixel_count:
        max_pixel_per_axis = int(math.sqrt(max_pixel_count))
        columns_count = math.ceil(pixelcount_x / max_pixel_per_axis)
        rows_count = math.ceil(pixelcount_y / max_pixel_per_axis)
        sub_pixelcount_x = max_pixel_per_axis * pixelsize_x
        sub_pixelcount_y = max_pixel_per_axis * pixelsize_y
        bboxes = []
        for column_idx in range(columns_count):
            sub_x1 = x1 + (column_idx * sub_pixelcount_x)
            sub_x2 = sub_x1 + sub_pixelcount_x
            for row_idx in range(rows_count):
                sub_y1 = y1 + (row_idx * sub_pixelcount_y)
                sub_y2 = sub_y1 + sub_pixelcount_y
                sub_bbox = (sub_x1, sub_y1, sub_x2, sub_y2)
                bboxes.append(sub_bbox)
        spatial_bounds = (bboxes, sub_pixelcount_x, sub_pixelcount_y)
    else:
        bboxes = [(x1, y1, x2, y2)]
        spatial_bounds = (bboxes, pixelcount_x, pixelcount_y)
    return spatial_bounds


def test(scenario_instance, resolution, max_pixel_count):
    spatial_bounds = split_scenario_extent(scenario_instance, resolution, max_pixel_count)
    raster_tasks = create_raster_tasks(descriptor_id, raster_id, spatial_bounds, projection, no_data)
    chunked_raster_tasks = False
    if len(raster_tasks) > 1:
        chunked_raster_tasks = True


def create_raster_tasks(descriptor_id: str, raster_id: str, spatial_bounds, projection: str, no_data: int = None):
    """
    Create Lizard raster tasks for a raster.
    Reimplemented code from https://github.com/nens/lizard-qgis-plugin
    """
    authcfg_id = get_authcfg_id()
    tenant = get_tenant_id()

    url = f"{api_url()}/tenants/{tenant}/file-descriptors/{descriptor_id}/raster/{raster_id}/task"
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
        r = request_raster_generate(descriptor_id=descriptor_id, raster_id=raster_id, payload=payload)
        raster_tasks.append(r)

    return raster_tasks

def request_raster_generate(descriptor_id: str, raster_id: str, payload: dict):
    authcfg_id = get_authcfg_id()
    tenant = get_tenant_id()
    url = f"{api_url()}/tenants/{tenant}/file-descriptors/{descriptor_id}/raster/{raster_id}/task"

    network_manager = NetworkManager(url, authcfg_id)
    status = network_manager.post(payload=payload)

    if status:
        response = network_manager.content
        return response
    else:
        raise Exception(network_manager.description())


def get_raster_file_link(descriptor_id: str, task_id: str):
    #TODO handle failed tasks better
    authcfg_id = get_authcfg_id()
    tenant = get_tenant_id()
    url = f"{api_url()}/tenants/{tenant}/file-descriptors/{descriptor_id}/raster/"+"{raster_id}"+f"/task/{task_id}"

    network_manager = NetworkManager(url, authcfg_id)
    job_complete = False
    while not job_complete:
        status, error = network_manager.fetch()
        if status:
            response = network_manager.content
            if response["status"] == "failure":
                job_complete == True
                raise Exception("Raster generation failed")
            elif response["status"] == "success":
                job_complete == True
                return response["result"]
            else:
                # wait 5 seconds before polling raster generate task again
                sleep(5)
        else:
            job_complete = True
            raise Exception(f"Failed to retrieve raster: {error}")


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


def map_result_to_file_name(result: dict) -> str:
    if result["name"] == "Raw 3Di output":
        return "results_3di.nc"
    elif result["name"] == "Grid administration":
        return "gridadmin.h5"
    else:
        return get_filename_from_attachment_url(result["attachment_url"])
