from qgis.core import QgsApplication, QgsAuthMethodConfig
from qgis.PyQt.QtCore import QSettings

from .communication import UICommunication
from .constant import THREEDI_AUTHCFG_ENTRY
from .utils_api import get_threedi_personal_api_key, get_user_info


def get_3di_authcfg_id():
    settings = QSettings()
    authcfg_id = settings.value(THREEDI_AUTHCFG_ENTRY)
    return authcfg_id


def get_3di_auth():
    """Getting 3Di credentials from the QGIS Authorization Manager."""
    authcfg_id = get_3di_authcfg_id()
    auth_manager = QgsApplication.authManager()
    authcfg = QgsAuthMethodConfig()
    auth_manager.loadAuthenticationConfig(authcfg_id, authcfg, True)
    username = authcfg.config("username")
    password = authcfg.config("password")
    return username, password


def set_3di_auth(personal_api_key: str, username="__key__"):
    """Setting 3Di credentials in the QGIS Authorization Manager."""
    settings = QSettings()
    authcfg_id = get_3di_authcfg_id()
    authcfg = QgsAuthMethodConfig()
    auth_manager = QgsApplication.authManager()
    auth_manager.setMasterPassword()
    auth_manager.loadAuthenticationConfig(authcfg_id, authcfg, True)

    if authcfg.id():
        authcfg.setConfig("username", username)
        authcfg.setConfig("password", personal_api_key)
        auth_manager.updateAuthenticationConfig(authcfg)
    else:
        authcfg.setMethod("Basic")
        authcfg.setName("3Di Personal Api Key")
        authcfg.setConfig("username", username)
        authcfg.setConfig("password", personal_api_key)
        auth_manager.storeAuthenticationConfig(authcfg)
        settings.setValue(THREEDI_AUTHCFG_ENTRY, authcfg.id())


def setup_3di_auth(communication: UICommunication):
    authcf_id = get_3di_authcfg_id()
    if authcf_id:
        username, password = get_3di_auth()
        if username and password:
            # Existing authentication found in the QGIS Authorization Manager
            return
    user = get_user_info(communication)
    if not user:
        return
    personal_api_key = get_threedi_personal_api_key(communication, user["sub"])
    if personal_api_key:
        set_3di_auth(personal_api_key)
    else:
        communication.show_error("Failed to setup Rana authentication.")
