import json

from qgis.core import QgsApplication, QgsAuthMethodConfig
from qgis.PyQt.QtCore import QSettings

from .communication import UICommunication
from .constant import (
    COGNITO_AUTHENTICATION_ENDPOINT,
    COGNITO_CLIENT_ID,
    COGNITO_TOKEN_ENDPOINT,
    RANA_AUTHCFG_ENTRY,
    RANA_SETTINGS_ENTRY,
    RANA_TENANT_ENTRY,
)


def set_tenant_id(tenant: str):
    settings = QSettings()
    settings.setValue(RANA_TENANT_ENTRY, tenant)


def get_tenant_id():
    settings = QSettings()
    tenant = settings.value(RANA_TENANT_ENTRY)
    return tenant


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


def setup_oauth2(communication: UICommunication):
    settings = QSettings()
    auth_manager = QgsApplication.authManager()
    auth_manager.setMasterPassword()

    # Check if the OAuth2 configuration is already stored
    auth_configs = auth_manager.availableAuthMethodConfigs()

    authcfg_id = None
    for config_id, config in auth_configs.items():
        if config.name() == RANA_SETTINGS_ENTRY:
            authcfg_id = config_id
            break

    if authcfg_id:
        settings.setValue(RANA_AUTHCFG_ENTRY, authcfg_id)
        return

    # Create a new QgsAuthMethodConfig instance for OAuth2
    authcfg = QgsAuthMethodConfig()
    authcfg.setMethod("OAuth2")
    authcfg.setName(RANA_SETTINGS_ENTRY)

    # Set the configuration map for OAuth2
    config_map = {
        "clientId": COGNITO_CLIENT_ID,
        "grantFlow": 3,
        "redirectHost": "localhost",
        "redirectPort": 7070,
        "redirectUrl": "rana-callback",
        "refreshTokenUrl": COGNITO_TOKEN_ENDPOINT,
        "requestUrl": COGNITO_AUTHENTICATION_ENDPOINT,
        "tokenUrl": COGNITO_TOKEN_ENDPOINT,
        "persistToken": True,
    }
    config_map_json = json.dumps(config_map)
    authcfg.setConfigMap({"oauth2config": config_map_json})

    # Store the OAuth2 configuration
    auth_manager.storeAuthenticationConfig(authcfg)
    new_authcfg_id = authcfg.id()
    if new_authcfg_id:
        settings.setValue(RANA_AUTHCFG_ENTRY, new_authcfg_id)
    else:
        communication.log_warn("Failed to create OAuth2 configuration")
