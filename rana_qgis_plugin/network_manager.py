import json
import urllib.parse

from qgis.core import QgsApplication, QgsNetworkAccessManager, QgsProcessingException
from qgis.PyQt.QtCore import QEventLoop, QUrl
from qgis.PyQt.QtNetwork import QNetworkReply, QNetworkRequest


class NetworkManager(object):
    """Network manager class for handling network requests."""

    def __init__(self, url: str, auth_cfg: str = None):
        self._network_manager = QgsNetworkAccessManager.instance()
        self._auth_manager = QgsApplication.authManager()
        self._url = url
        self._reply = None
        self._auth_cfg = auth_cfg
        self._content = None
        self._request = None

        if auth_cfg:
            is_auth_configured = self._auth_cfg in self._auth_manager.configIds()
            if not is_auth_configured:
                raise QgsProcessingException("Authorization not configured!")

    @property
    def content(self):
        return self._content

    def fetch(self, params: dict = None):
        self.prepare_request(params)
        self._reply = self._network_manager.get(self._request)
        return self.process_request()

    def post(self, params: dict = None, payload: dict = {}):
        self.prepare_request(params)
        self._reply = self._network_manager.post(self._request, json.dumps(payload).encode("utf-8"))
        return self.process_request()

    def put(self, params: dict = None, payload: dict = {}):
        self.prepare_request(params)
        self._reply = self._network_manager.put(self._request, json.dumps(payload).encode("utf-8"))
        return self.process_request()

    def prepare_request(self, params: dict = None):
        # Initialize some properties again
        self._content = None
        self._reply = None
        self._request = None

        encoded_params = urllib.parse.urlencode(params) if params else None
        url = f"{self._url}?{encoded_params}" if encoded_params else self._url
        self._request = QNetworkRequest(QUrl(url))
        self._request.setHeader(QNetworkRequest.ContentTypeHeader, "application/json")

        if self._auth_cfg:
            self._auth_manager.updateNetworkRequest(self._request, self._auth_cfg)

    def process_request(self):
        loop = QEventLoop()

        # Connect the finished and timeout signals to stop the event loop
        self._reply.finished.connect(loop.quit)
        self._network_manager.requestTimedOut.connect(loop.quit)

        # Start the event loop and wait for the request to finish
        loop.exec_()

        description = None
        if self._reply.error() != QNetworkReply.NoError:
            status = False
            description = self._reply.errorString()
        else:
            status = True
            raw_content = self._reply.readAll()
            self._content = json.loads(str(raw_content, "utf-8"))

        self._reply.deleteLater()

        return status, description
