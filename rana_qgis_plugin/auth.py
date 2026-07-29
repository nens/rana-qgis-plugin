"""Auth functions for the Rana Browser datasource entrypoint."""

import json
from typing import Optional

from qgis.core import QgsApplication, QgsAuthMethodConfig, QgsMessageLog, QgsSettings

from rana_qgis_plugin.constant import (
    COGNITO_AUTHENTICATION_ENDPOINT,
    COGNITO_TOKEN_ENDPOINT,
    RANA_AUTHCFG_ENTRY,
    RANA_SETTINGS_ENTRY,
)
from rana_qgis_plugin.network_manager import NetworkManager
from rana_qgis_plugin.utils.settings import (
    api_url,
    cognito_client_id,
    cognito_client_id_native,
    set_base_url,
    set_cognito_client_id,
    set_cognito_client_id_native,
)

# TODO: find way to use communication class here instead of directly writing to QgsMessageLog


def is_authenticated() -> bool:
    """Return True iff the user has a valid active session.

    Conditions (all must hold):
    1. A backend URL is set in settings (Rana/base_url).
    2. An authcfg ID is stored in settings (Rana/authcfg).
    3. That authcfg ID resolves in QgsAuthManager.

    If the authcfg ID is stored but does not resolve (stale pointer),
    the stored ID is cleaned up automatically.
    """
    settings = QgsSettings()

    base_url = settings.value(f"{RANA_SETTINGS_ENTRY}/base_url")
    if not base_url:
        return False

    authcfg_id = settings.value(RANA_AUTHCFG_ENTRY)
    if not authcfg_id:
        return False

    auth_manager = QgsApplication.authManager()
    if auth_manager is None:
        return False
    if authcfg_id not in auth_manager.availableAuthMethodConfigs():
        settings.remove(RANA_AUTHCFG_ENTRY)
        return False

    return True


def active_tenant() -> Optional[str]:
    """Return the currently active tenant ID from settings, or None."""
    return QgsSettings().value(f"{RANA_SETTINGS_ENTRY}/tenant")


def clear_credentials(delete_config: bool = True) -> None:
    """Remove the stored authcfg and transition to logged-out state.

    If no authcfg is stored this is a no-op. Pass delete_config=False to
    clear only the settings reference without removing the authcfg from
    QgsAuthManager (e.g. when a temporary logout is followed by rollback).
    """
    settings = QgsSettings()
    authcfg_id = settings.value(RANA_AUTHCFG_ENTRY)
    if not authcfg_id:
        return

    if delete_config:
        auth_manager = QgsApplication.authManager()
        if auth_manager is not None:
            auth_manager.removeAuthenticationConfig(authcfg_id)

    settings.remove(RANA_AUTHCFG_ENTRY)
    QgsMessageLog.logMessage("Logged out from Rana.", "Rana")


def update_auth_settings(new_url: str) -> bool:
    """Store new backend URL and fetch matching Cognito client IDs from that backend.

    Returns True on success, False if the backend is unreachable or returns
    unexpected settings. On failure the URL is reverted to the previous value.
    """
    old_url = QgsSettings().value(f"{RANA_SETTINGS_ENTRY}/base_url")
    set_base_url(new_url)

    url = f"{api_url()}/frontend-settings"
    nm = NetworkManager(url)
    status, _ = nm.fetch()

    if not status or nm.content is None:
        set_base_url(old_url)
        return False

    settings = nm.content
    default_id = settings.get("default_client_id") if settings else None
    native_id = settings.get("native_client_id") if settings else None

    if not default_id or not native_id:
        set_base_url(old_url)
        return False

    set_cognito_client_id(default_id)
    set_cognito_client_id_native(native_id)
    return True


def fetch_identity_providers(tenant_id: str) -> Optional[list]:
    """Fetch identity providers for tenant_id from the Rana API.

    Returns a list of provider dicts on success, or None on network failure.
    """
    url = f"{api_url()}/tenants/{tenant_id}/identity-providers"
    network_manager = NetworkManager(url)
    status, error = network_manager.fetch()
    if not status:
        QgsMessageLog.logMessage(f"Failed to fetch identity providers: {error}", "Rana")
        return None
    response = network_manager.content
    if response is None:
        return []
    return response.get("items", [])


def create_oauth2_config(provider: dict) -> Optional[str]:
    """Create an OAuth2 auth config in QgsAuthManager and return its ID.

    Uses SSO client ID + identity_provider query param for external providers;
    uses native client ID + empty identity_provider for username/password.
    Returns None if QgsAuthManager fails to store the config.
    """
    auth_manager = QgsApplication.authManager()
    if auth_manager is None:
        QgsMessageLog.logMessage("QgsAuthManager unavailable.", "Rana")
        return None
    auth_manager.setMasterPassword()
    is_sso = provider.get("type") != "rana"
    client_id = cognito_client_id() if is_sso else cognito_client_id_native()
    query_pairs = (
        {"identity_provider": provider["id"]} if is_sso else {"identity_provider": ""}
    )

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
        "queryPairs": query_pairs,
    }

    authcfg = QgsAuthMethodConfig()
    authcfg.setMethod("OAuth2")
    authcfg.setName(RANA_SETTINGS_ENTRY)
    authcfg.setConfigMap({"oauth2config": json.dumps(config_map)})

    auth_manager.storeAuthenticationConfig(authcfg)
    new_id = authcfg.id()
    if not new_id:
        QgsMessageLog.logMessage("Failed to create OAuth2 configuration.", "Rana")
        return None

    return new_id
