import json
import urllib.parse

from qgis.core import (
    Qgis,
    QgsApplication,
    QgsMessageLog,
    QgsNetworkAccessManager,
    QgsProcessingException,
)
from qgis.PyQt.QtCore import QCoreApplication, QFile, QIODevice, QJsonDocument, QUrl
from qgis.PyQt.QtGui import QImage
from qgis.PyQt.QtNetwork import (
    QHttpMultiPart,
    QHttpPart,
    QNetworkReply,
    QNetworkRequest,
)


class NetworkManager(object):
    """Network manager class for handling network requests."""

    def __init__(self, url: str, auth_cfg: str = None):
        self._network_manager = QgsNetworkAccessManager.instance()
        # Don't follow redirects automatically
        self._network_manager.setRedirectPolicy(
            QNetworkRequest.RedirectPolicy.ManualRedirectPolicy
        )
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

    def put(self, params: dict = None, payload: dict = None):
        self.prepare_request(params)
        self._reply = self._network_manager.put(
            self._request, json.dumps(payload).encode("utf-8")
        )
        return self.process_request()

    def put_multipart(self, params: dict = None, files: dict = None):
        self.prepare_request(params)
        # Create multipart object
        multipart = QHttpMultiPart(QHttpMultiPart.ContentType.FormDataType)

        if files:
            for field_name, file_name, file_path, content_type in files:
                file = QFile(file_path)
                if file.open(QIODevice.OpenModeFlag.ReadOnly):
                    file_data = file.readAll()  # Read data into memory
                    file.close()  # Close immediately
                    part = QHttpPart()
                    part.setHeader(
                        QNetworkRequest.KnownHeaders.ContentDispositionHeader,
                        f'form-data; name="{field_name}"; filename="{file_name}"',
                    )

                    part.setHeader(
                        QNetworkRequest.KnownHeaders.ContentTypeHeader, content_type
                    )
                    part.setBody(file_data)
                    multipart.append(part)

        # Don't set ContentTypeHeader manually - multipart sets it with boundary
        # Remove the content-type header from prepare_request
        self._request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, None)

        self._reply = self._network_manager.put(self._request, multipart)
        multipart.setParent(self._reply)  # Delete multipart with reply

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

        # Check for redirect status codes FIRST (before checking for errors)
        if self._reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute) in (
            301,
            302,
            303,
            307,
            308,
        ):
            location = self._reply.rawHeader(b"Location")
            if location:
                redirect_url = str(location, "utf-8")
                self._reply.deleteLater()
                return True, redirect_url
            else:
                self._reply.deleteLater()
                return False, "Redirect response missing Location header"

        if self._reply.error() != QNetworkReply.NetworkError.NoError:
            status = False
            description = self._reply.errorString()
        else:
            status = True

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
                else:
                    self._content = json.loads(str(raw_content, "utf-8"))
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
