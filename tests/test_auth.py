from unittest.mock import MagicMock, patch

import pytest

from rana_qgis_plugin.auth import (
    clear_credentials,
    create_oauth2_config,
    is_authenticated,
)
from rana_qgis_plugin.constant import RANA_AUTHCFG_ENTRY, RANA_SETTINGS_ENTRY

# Patch targets used throughout
_SETTINGS = "rana_qgis_plugin.auth.QgsSettings"
_AUTH_MGR = "rana_qgis_plugin.auth.QgsApplication.authManager"


# --- Helpers ---


def make_mock_settings(base_url=None, authcfg_id=None):
    """Return a mock QgsSettings with controlled values."""
    mock = MagicMock()

    def settings_value(key, default=None):
        if key == f"{RANA_SETTINGS_ENTRY}/base_url":
            return base_url
        if key == RANA_AUTHCFG_ENTRY:
            return authcfg_id
        return default

    mock.value.side_effect = settings_value
    return mock


def make_mock_auth_manager(authcfg_id=None, authcfg_exists=False):
    """Return a mock QgsAuthManager with controlled config lookup."""
    mock = MagicMock()
    mock.availableAuthMethodConfigs.return_value = (
        {authcfg_id: object()} if authcfg_exists and authcfg_id else {}
    )
    return mock


# --- is_authenticated() ---


@pytest.mark.parametrize(
    "base_url,authcfg_id,authcfg_exists,expected,removes_authcfg",
    [
        ("https://example.com", "abc123", True, True, False),
        (None, "abc123", True, False, False),
        ("https://example.com", None, False, False, False),
    ],
    ids=["valid", "no_base_url", "no_authcfg_id"],
)
def test_is_authenticated(
    base_url, authcfg_id, authcfg_exists, expected, removes_authcfg
):
    """is_authenticated() returns expected result; stale authcfg is cleaned up."""
    settings = make_mock_settings(base_url=base_url, authcfg_id=authcfg_id)
    auth_mgr = make_mock_auth_manager(
        authcfg_id=authcfg_id, authcfg_exists=authcfg_exists
    )

    with (
        patch(_SETTINGS, return_value=settings),
        patch(_AUTH_MGR, return_value=auth_mgr),
    ):
        assert is_authenticated() == expected

    if removes_authcfg:
        settings.remove.assert_called_once_with(RANA_AUTHCFG_ENTRY)
    else:
        settings.remove.assert_not_called()


def test_is_authenticated_removes_stale():
    """Stale authcfg (ID in settings but not in QgsAuthManager) is cleaned up."""
    settings = make_mock_settings(base_url="https://example.com", authcfg_id="stale_id")
    auth_mgr = make_mock_auth_manager(authcfg_id="stale_id", authcfg_exists=False)

    with (
        patch(_SETTINGS, return_value=settings),
        patch(_AUTH_MGR, return_value=auth_mgr),
    ):
        is_authenticated()

    settings.remove.assert_called_once_with(RANA_AUTHCFG_ENTRY)


def test_clear_credentials_clears_authcfg():
    """clear_credentials() removes authcfg from QgsAuthManager and settings."""
    settings = make_mock_settings(base_url="https://example.com", authcfg_id="abc123")
    auth_mgr = make_mock_auth_manager(authcfg_id="abc123", authcfg_exists=True)

    with (
        patch(_SETTINGS, return_value=settings),
        patch(_AUTH_MGR, return_value=auth_mgr),
    ):
        clear_credentials()

    auth_mgr.removeAuthenticationConfig.assert_called_once_with("abc123")
    settings.remove.assert_called_once_with(RANA_AUTHCFG_ENTRY)


def test_clear_credentials_when_already_signed_out_is_noop():
    """clear_credentials() when no authcfg is stored does not raise and does nothing."""
    settings = make_mock_settings(base_url="https://example.com", authcfg_id=None)
    auth_mgr = make_mock_auth_manager()

    with (
        patch(_SETTINGS, return_value=settings),
        patch(_AUTH_MGR, return_value=auth_mgr),
    ):
        clear_credentials()

    auth_mgr.removeAuthenticationConfig.assert_not_called()
    settings.remove.assert_not_called()


def make_mock_auth_manager_for_store(store_succeeds=True):
    """Return a mock QgsAuthManager that simulates storeAuthenticationConfig."""
    mock = MagicMock()

    def store_config(authcfg):
        if store_succeeds:
            authcfg.setId("new-cfg-id")

    mock.storeAuthenticationConfig.side_effect = store_config
    return mock


def test_create_oauth2_config_sso_returns_authcfg_id():
    """create_oauth2_config() stores OAuth2 config and returns the new ID for SSO provider."""
    provider = {"id": "cognito-sso", "name": "MySSO", "type": "saml"}
    auth_mgr = make_mock_auth_manager_for_store(store_succeeds=True)

    with (
        patch(_AUTH_MGR, return_value=auth_mgr),
        patch("rana_qgis_plugin.auth.cognito_client_id", return_value="client-sso"),
        patch(
            "rana_qgis_plugin.auth.cognito_client_id_native",
            return_value="client-native",
        ),
    ):
        result = create_oauth2_config(provider)

    assert result == "new-cfg-id"
    auth_mgr.setMasterPassword.assert_called_once()
    auth_mgr.storeAuthenticationConfig.assert_called_once()


def test_create_oauth2_config_native_uses_native_client_id():
    """create_oauth2_config() uses native client ID for username/password (rana-type) provider."""
    provider = {"id": "", "name": "", "type": "rana"}
    auth_mgr = make_mock_auth_manager_for_store(store_succeeds=True)

    with (
        patch(_AUTH_MGR, return_value=auth_mgr),
        patch("rana_qgis_plugin.auth.cognito_client_id", return_value="client-sso"),
        patch(
            "rana_qgis_plugin.auth.cognito_client_id_native",
            return_value="client-native",
        ),
    ):
        result = create_oauth2_config(provider)

    assert result == "new-cfg-id"
    stored_cfg = auth_mgr.storeAuthenticationConfig.call_args[0][0]
    import json

    config_map = json.loads(stored_cfg.configMap()["oauth2config"])
    assert config_map["clientId"] == "client-native"


def test_create_oauth2_config_store_failure_returns_none():
    """create_oauth2_config() returns None when QgsAuthManager fails to store the config."""
    provider = {"id": "cognito-sso", "name": "MySSO", "type": "saml"}
    auth_mgr = make_mock_auth_manager_for_store(store_succeeds=False)

    with (
        patch(_AUTH_MGR, return_value=auth_mgr),
        patch("rana_qgis_plugin.auth.cognito_client_id", return_value="client-sso"),
        patch(
            "rana_qgis_plugin.auth.cognito_client_id_native",
            return_value="client-native",
        ),
    ):
        result = create_oauth2_config(provider)

    assert result is None
