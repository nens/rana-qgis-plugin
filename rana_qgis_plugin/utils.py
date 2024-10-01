from qgis.core import (
    QgsApplication,
    QgsAuthMethodConfig,
    QgsLogger,
    QgsNetworkAccessManager,
    QgsMessageLog,
)
from qgis.PyQt.QtCore import QSettings, QUrl
from qgis.PyQt.QtNetwork import QNetworkReply, QNetworkRequest

RANA_SETTINGS_ENTRY = "Rana"
RANA_AUTHCFG_ENTRY = f"{RANA_SETTINGS_ENTRY}/authcfg"

def get_tenant():
    oauth2_id = 'n9p1erl'
    url = "https://test.ranawaterintelligence.com/v1-alpha/tenants/nenstest"
    QgsMessageLog.logMessage(f"Making a request to {url}")

    # Set up the request using QgsNetworkAccessManager
    request = QNetworkRequest(QUrl(url))
    manager = QgsNetworkAccessManager.instance()
    auth_manager = QgsApplication.authManager()
    updated, request = auth_manager.updateNetworkRequest(request, oauth2_id)
    reply = manager.get(request)

    while not reply.isFinished():
        QgsApplication.processEvents()

    if reply.error() != QNetworkReply.NetworkError.NoError:
        QgsMessageLog.logMessage(f"Error: {reply.errorString()}")
        QgsLogger.warning(f"Error: {reply.errorString()}")
    else:
        content = reply.readAll().data().decode()
        QgsMessageLog.logMessage(f"Success: {content}")
        QgsLogger.warning(f"Success: {content}")

def setup_oauth2():
    settings = QSettings()
    authcfg_id = settings.value(RANA_AUTHCFG_ENTRY, None)
    authcfg = QgsAuthMethodConfig()
    auth_manager = QgsApplication.authManager()
    auth_manager.setMasterPassword()
    auth_manager.loadAuthenticationConfig(authcfg_id, authcfg, True)

    # Define your OAuth2 configuration parameters
    name = "Rana OAuth2"  # The display name
    auth_url = "https://auth.lizard.net/oauth2/authorize"
    token_url = "https://auth.lizard.net/oauth2/token"
    refresh_token_url = "https://auth.lizard.net/oauth2/token"
    redirect_url = "localhost:7070/rana-callback"
    client_id = "69jtptvra09q59kp5m56o9gfks"
    grant_flow = 3

    if authcfg.id():
        authcfg.setId(authcfg.id())
        auth_manager.updateAuthenticationConfig(authcfg)
    else:
        authcfg.setMethod("OAuth2")
        authcfg.setName(name)
        authcfg.setConfig("grantFlow", grant_flow)
        authcfg.setConfig("clientId", client_id)
        authcfg.setConfig("requestUrl", auth_url)
        authcfg.setConfig("tokenUrl", token_url)
        authcfg.setConfig("refreshTokenUrl", refresh_token_url)
        authcfg.setConfig("redirectUrl", redirect_url)
        auth_manager.storeAuthenticationConfig(authcfg)
        settings.setValue(RANA_AUTHCFG_ENTRY, authcfg.id())
