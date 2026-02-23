import json
import re
import unittest

from qgis.core import QgsApplication, QgsAuthMethodConfig
from qgis.PyQt.QtCore import QSettings

from rana_qgis_plugin.communication import UICommunication
from rana_qgis_plugin.constant import (
    COGNITO_AUTHENTICATION_ENDPOINT,
    COGNITO_TOKEN_ENDPOINT,
    RANA_AUTHCFG_ENTRY,
    RANA_SETTINGS_ENTRY,
)
from rana_qgis_plugin.network_manager import NetworkManager
from rana_qgis_plugin.utils_settings import (
    api_url,
    cognito_client_id,
    cognito_client_id_native,
    get_tenant_id,
    set_tenant_id,
)


# Moved from utils_api to prevent circular import
def get_tenant_identity_providers(communication, tenant_id: str):
    url = f"{api_url()}/tenants/{tenant_id}/identity-providers"
    communication.log_info(str(url))
    network_manager = NetworkManager(url)
    status, _ = network_manager.fetch()

    if status:
        response = network_manager.content
        items = response["items"]
        return items
    else:
        return []


def get_authcfg_id():
    settings = QSettings()
    authcfg_id = settings.value(RANA_AUTHCFG_ENTRY)
    return authcfg_id


def remove_authcfg():
    settings = QSettings()
    authcfg_id = settings.value(RANA_AUTHCFG_ENTRY)
    auth_manager = QgsApplication.authManager()
    auth_manager.removeAuthenticationConfig(authcfg_id)
    settings.remove(RANA_AUTHCFG_ENTRY)


def setup_oauth2(communication: UICommunication, start_tenant_id) -> bool:
    settings = QSettings()
    auth_manager = QgsApplication.authManager()
    if not auth_manager.setMasterPassword():
        communication.show_error(
            "Failed to set master password for authentication manager"
        )
        return False

    # Check if the OAuth2 configuration is already stored
    auth_configs = auth_manager.availableAuthMethodConfigs()

    authcfg_id = None
    for config_id, config in auth_configs.items():
        if config.name() == RANA_SETTINGS_ENTRY:
            authcfg_id = config_id
            break

    if authcfg_id:
        communication.log_info("Authentication already configured")
        settings.setValue(RANA_AUTHCFG_ENTRY, authcfg_id)
        return True

    tenant_id = get_tenant_id() if not start_tenant_id else start_tenant_id
    if not tenant_id:
        tenant_id, okPressed = UICommunication.input_ask(
            None, "Authentication", "Please provide your tenant code."
        )
        if not tenant_id or not okPressed:
            return False

    # Retrieve the identity provider for this tenant
    ident_providers = get_tenant_identity_providers(communication, tenant_id)
    if not ident_providers:
        communication.show_error(
            f"Unable to retrieve identity providers for tenant {tenant_id}"
        )
        return False

    # Escape the standard button mnemonic character
    sso_str = "Sign in with your SSO"
    ident_providers_options = [
        f"{sso_str} ({prov['name']})".replace("&", "&&")
        for prov in ident_providers
        if prov["type"] != "rana"
    ]
    ident_providers_options.append("Sign in with your username and password")
    ident_providers_options.append("Cancel")

    sign_in_method = communication.custom_ask(
        None,
        "Authentication",
        "How would you like to sign in?",
        *ident_providers_options,
    )

    if not sign_in_method:
        return False

    # Restore escaped character
    sign_in_method = sign_in_method.replace("&&", "&")
    if sign_in_method.startswith(sso_str):
        m = re.search(r"\(([^)]*)\)", sign_in_method)
        ident_provider_id = next(
            (d["id"] for d in ident_providers if d.get("name") == m.group(1)), None
        )
        assert ident_provider_id
        communication.log_info(f"Setting identity provider to {ident_provider_id}")
        queryPairs = {"identity_provider": ident_provider_id}
        client_id = cognito_client_id()
    elif sign_in_method == "Cancel":
        return False
    else:
        queryPairs = {"identity_provider": ""}
        client_id = cognito_client_id_native()

    # Create a new QgsAuthMethodConfig instance for OAuth2
    authcfg = QgsAuthMethodConfig()
    authcfg.setMethod("OAuth2")
    authcfg.setName(RANA_SETTINGS_ENTRY)

    # Set the configuration map for OAuth2
    config_map = {
        "clientId": client_id,
        "grantFlow": 3,
        "redirectHost": "localhost",
        "redirectPort": 7070,
        "redirectUrl": "rana-callback",
        "refreshTokenUrl": COGNITO_TOKEN_ENDPOINT,
        "requestUrl": COGNITO_AUTHENTICATION_ENDPOINT,
        "tokenUrl": COGNITO_TOKEN_ENDPOINT,
        "persistToken": True,
        # This is how you pass extra query parameters to the /authorize endpoint
        "queryPairs": queryPairs,
    }

    config_map_json = json.dumps(config_map)
    authcfg.setConfigMap({"oauth2config": config_map_json})

    # Store the OAuth2 configuration
    res, auth_reult = auth_manager.storeAuthenticationConfig(authcfg)
    if not res:
        communication.show_error("Failed to create OAuth2 configuration")
        return False

    new_authcfg_id = authcfg.id()
    if new_authcfg_id:
        settings.setValue(RANA_AUTHCFG_ENTRY, new_authcfg_id)
    else:
        communication.show_error("Failed to create OAuth2 configuration")
        return False

    set_tenant_id(tenant_id)

    return True
