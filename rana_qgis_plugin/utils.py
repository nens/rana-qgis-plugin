import urllib.parse

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
    encodedParams = urllib.parse.urlencode(params) if params else ""
    url = f"{BASE_URL}/tenants/{tenant}/projects/{project_id}/files/ls?{encodedParams}"

    network_manager = NetworkManager(url, OAUTH2_ID)
    status, error = network_manager.fetch()

    if status:
        response = network_manager.content
        items = response["items"]
        return items
    else:
        QgsMessageLog.logMessage(f"Error: {error}")
