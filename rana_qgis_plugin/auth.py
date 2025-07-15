import json

from qgis.core import QgsApplication, QgsAuthMethodConfig
from qgis.PyQt.QtCore import QSettings

from rana_qgis_plugin.communication import UICommunication
from rana_qgis_plugin.constant import (
    COGNITO_AUTHENTICATION_ENDPOINT,
    COGNITO_NENS_IDENTITY_PROVIDER,
    COGNITO_TOKEN_ENDPOINT,
    RANA_AUTHCFG_ENTRY,
    RANA_SETTINGS_ENTRY,
)
from rana_qgis_plugin.utils_settings import cognito_client_id, cognito_client_id_native


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


def setup_oauth2(communication: UICommunication) -> bool:
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
        communication.log_info("Authentication already configured")
        settings.setValue(RANA_AUTHCFG_ENTRY, authcfg_id)
        return True

    sign_in_method = communication.custom_ask(
        None,
        "Authentication",
        "How would you like to sign in?",
        "Sign in with your SSO (Nelen && Schuurmans)",
        "Sign in with your username and password",
        "Cancel",
    )

    if sign_in_method.startswith("Sign in with your SSO"):
        communication.log_info(
            f"Setting identity provider to {COGNITO_NENS_IDENTITY_PROVIDER}"
        )
        queryPairs = {"identity_provider": COGNITO_NENS_IDENTITY_PROVIDER}
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
    auth_manager.storeAuthenticationConfig(authcfg)
    new_authcfg_id = authcfg.id()
    if new_authcfg_id:
        settings.setValue(RANA_AUTHCFG_ENTRY, new_authcfg_id)
    else:
        communication.log_warn("Failed to create OAuth2 configuration")
        return False

    return True
