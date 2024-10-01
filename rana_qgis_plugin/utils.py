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
    tenant_url = f"{BASE_URL}/tenants/{tenant}/projects"

    network_manager = NetworkManager(tenant_url, OAUTH2_ID)
    status, error = network_manager.fetch()

    if status:
        projects = network_manager.content
        return projects
    else:
        QgsMessageLog.logMessage(f"Error: {error}")
