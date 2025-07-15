from urllib.parse import quote

from qgis.core import QgsSettings

from .constant import COGNITO_LOGOUT_ENDPOINT, RANA_SETTINGS_ENTRY, RANA_TENANT_ENTRY


def initialize_settings():
    """Sets up the settings with default values"""
    settings = QgsSettings()

    settings.setValue(
        f"{RANA_SETTINGS_ENTRY}/cognito_client_id",
        settings.value(
            f"{RANA_SETTINGS_ENTRY}/cognito_client_id", "250mkcukj5tn6lblsd6ka42c0a"
        ),
    )
    settings.setValue(
        f"{RANA_SETTINGS_ENTRY}/cognito_client_id_native",
        settings.value(
            f"{RANA_SETTINGS_ENTRY}/cognito_client_id_native",
            "2epleb6bkli509b0a6fmddcrj6",
        ),
    )
    settings.setValue(
        f"{RANA_SETTINGS_ENTRY}/base_url",
        settings.value(
            f"{RANA_SETTINGS_ENTRY}/base_url", "https://www.ranawaterintelligence.com"
        ),
    )


def set_tenant_id(tenant: str):
    QgsSettings().setValue(RANA_TENANT_ENTRY, tenant)


def get_tenant_id() -> str:
    return QgsSettings().value(RANA_TENANT_ENTRY)


def set_cognito_client_id(id: str):
    QgsSettings().setValue(f"{RANA_SETTINGS_ENTRY}/cognito_client_id", id)


def cognito_client_id() -> str:
    return QgsSettings().value(f"{RANA_SETTINGS_ENTRY}/cognito_client_id")


def set_cognito_client_id_native(id: str):
    QgsSettings().setValue(f"{RANA_SETTINGS_ENTRY}/cognito_client_id_native", id)


def cognito_client_id_native() -> str:
    return QgsSettings().value(f"{RANA_SETTINGS_ENTRY}/cognito_client_id_native")


def set_base_url(url: str):
    QgsSettings().setValue(f"{RANA_SETTINGS_ENTRY}/base_url", url)


def base_url():
    return QgsSettings().value(f"{RANA_SETTINGS_ENTRY}/base_url")


def api_url():
    return f"{base_url()}/v1-alpha"


def logout_redirect_uri():
    return f"{base_url()}/auth/callback/cognito/logout"


def logout_redirect_uri_encoded():
    return quote(logout_redirect_uri, safe="")


def logout_url():
    return f"{COGNITO_LOGOUT_ENDPOINT}?client_id={cognito_client_id()}&logout_uri={logout_redirect_uri_encoded()}"
