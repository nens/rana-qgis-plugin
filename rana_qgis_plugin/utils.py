from qgis.core import QgsMessageLog
from .network_manager import NetworkManager

def get_tenant(tenant: str):
    oauth2_id = "n9p1erl"
    tenant_url = f"https://test.ranawaterintelligence.com/v1-alpha/tenants/{tenant}"

    network_manager = NetworkManager(tenant_url, oauth2_id)
    status, error = network_manager.fetch()

    if status:
        tenant = network_manager.content
        return tenant
    else:
        QgsMessageLog.logMessage(f"Error: {error}")
