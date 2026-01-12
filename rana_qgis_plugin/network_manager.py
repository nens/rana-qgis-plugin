import json
import urllib.parse

from qgis.core import QgsApplication, QgsNetworkAccessManager, QgsProcessingException
from qgis.PyQt.QtCore import QCoreApplication, QJsonDocument, QUrl
from qgis.PyQt.QtGui import QImage
from qgis.PyQt.QtNetwork import QNetworkReply, QNetworkRequest


class NetworkManager(object):
    """Network manager class for handling network requests."""

    def __init__(self, url: str, auth_cfg: str = None):
        self._network_manager = QgsNetworkAccessManager.instance()
        self._auth_manager = QgsApplication.authManager()
        self._network_finished = False
        self._network_timeout = False
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

    @property
    def network_finished(self):
        return self._network_finished

    @property
    def network_timeout(self):
        return self._network_timeout

    def fetch(self, params: dict = None):
        self.prepare_request(params)
        self._reply = self._network_manager.get(self._request)
        return self.process_request()

    def post(self, params: dict = None, payload: dict = {}):
        self.prepare_request(params)
        self._reply = self._network_manager.post(
            self._request, json.dumps(payload).encode("utf-8")
        )
        return self.process_request()

    def put(self, params: dict = None, payload: dict = {}):
        self.prepare_request(params)
        self._reply = self._network_manager.put(
            self._request, json.dumps(payload).encode("utf-8")
        )
        return self.process_request()

    def delete(self, params: dict = None):
        self.prepare_request(params)
        self._reply = self._network_manager.deleteResource(self._request)
        return self.process_request()

    def prepare_request(self, params: dict = None):
        # Initialize some properties again
        self._content = None
        self._reply = None
        self._request = None
        self._network_finished = False
        self._network_timeout = False

        encoded_params = urllib.parse.urlencode(params) if params else None
        url = f"{self._url}?{encoded_params}" if encoded_params else self._url
        self._request = QNetworkRequest(QUrl(url))
        self._request.setHeader(
            QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json"
        )

        if self._auth_cfg:
            self._auth_manager.updateNetworkRequest(self._request, self._auth_cfg)

    def process_request(self):
        self._reply.finished.connect(self.fetch_finished)
        self._network_manager.requestTimedOut.connect(self.request_timeout)

        while not self._reply.isFinished():
            QCoreApplication.processEvents()

        description = None
        if self._reply.error() != QNetworkReply.NetworkError.NoError:
            status = False
            description = self._reply.errorString()
        else:
            status = True
            if (
                self._reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
                == 307
            ):
                # For HTTP status code 307 (Temporary Redirect),
                # look for the 'Location' header to get the new redirect URL
                location = self._reply.rawHeader(b"Location")
                if location:
                    return status, str(location, "utf-8")

            if (
                self._reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
                == 204
            ):
                self._reply.deleteLater()
                return status, description

            raw_content = self._reply.readAll()
            content_type = self._reply.header(QNetworkRequest.ContentTypeHeader)

            if content_type.startswith("application/json"):
                json_doc = QJsonDocument.fromJson(raw_content)
                if json_doc.isObject():
                    self._content = (
                        json_doc.toVariant()
                    )  # Returns QVariant which can be used like a Python dict
            elif content_type.startswith("image/"):
                image = QImage()
                image.loadFromData(raw_content)
                self._content = image
            else:
                self._content = json.loads(str(raw_content, "utf-8"))
        self._reply.deleteLater()
        return status, description

    def fetch_finished(self):
        """Called when fetching metadata has finished."""
        self._network_finished = True

    def request_timeout(self):
        """Called when a request timeout signal is emitted."""
        self._network_timeout = True
