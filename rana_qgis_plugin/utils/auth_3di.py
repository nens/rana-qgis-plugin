"""3Di authentication helpers using the QGIS Authorization Manager."""

from qgis.core import QgsApplication, QgsAuthManager, QgsAuthMethodConfig
from qgis.PyQt.QtCore import QSettings

from rana_qgis_plugin.constant import THREEDI_AUTHCFG_ENTRY
from rana_qgis_plugin.utils.api import get_threedi_personal_api_key


def get_3di_authcfg_id() -> str | None:
    return QSettings().value(THREEDI_AUTHCFG_ENTRY)


def auth_manager() -> QgsAuthManager:
    """Return the QGIS auth manager, raising if unavailable."""
    manager = QgsApplication.authManager()
    if manager is None:
        raise RuntimeError("QGIS auth manager is not available")
    return manager


def get_3di_auth() -> tuple[str | None, str | None]:
    """Return (username, password) from the QGIS Authorization Manager."""
    authcfg_id = get_3di_authcfg_id()
    if not authcfg_id:
        return None, None
    authcfg = QgsAuthMethodConfig()
    auth_manager().loadAuthenticationConfig(authcfg_id, authcfg, True)
    return authcfg.config("username"), authcfg.config("password")


def has_3di_auth() -> bool:
    """Return True when a non-empty personal API token is stored."""
    _, password = get_3di_auth()
    return bool(password)


def set_3di_auth(personal_api_key: str, username: str = "__key__") -> None:
    """Store or update the 3Di personal API key in the QGIS Authorization Manager."""
    settings = QSettings()
    authcfg_id = get_3di_authcfg_id()
    authcfg = QgsAuthMethodConfig()
    manager = auth_manager()
    manager.setMasterPassword()
    manager.loadAuthenticationConfig(authcfg_id, authcfg, True)

    if authcfg.id():
        authcfg.setConfig("username", username)
        authcfg.setConfig("password", personal_api_key)
        manager.updateAuthenticationConfig(authcfg)
    else:
        authcfg.setMethod("Basic")
        authcfg.setName("3Di Personal Api Key")
        authcfg.setConfig("username", username)
        authcfg.setConfig("password", personal_api_key)
        manager.storeAuthenticationConfig(authcfg)
        settings.setValue(THREEDI_AUTHCFG_ENTRY, authcfg.id())


def remove_3di_auth() -> None:
    """Remove the 3Di auth config from the QGIS Authorization Manager."""
    authcfg_id = get_3di_authcfg_id()
    if authcfg_id:
        auth_manager().removeAuthenticationConfig(authcfg_id)
    QSettings().remove(THREEDI_AUTHCFG_ENTRY)


def setup_3di_auth(user_id: str) -> None:
    authcf_id = get_3di_authcfg_id()
    if authcf_id:
        username, password = get_3di_auth()
        if username and password:
            # Existing authentication found in the QGIS Authorization Manager
            return
    personal_api_key = get_threedi_personal_api_key(user_id)
    set_3di_auth(personal_api_key)
