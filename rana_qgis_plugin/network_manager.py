import configparser
import json
import os
import urllib.parse
from typing import Any, Optional

from qgis.core import (  # type: ignore[attr-defined]
    QgsApplication,
    QgsAuthManager,
    QgsNetworkAccessManager,
    QgsProcessingException,
)
from qgis.PyQt.QtCore import (
    QEventLoop,
    QFile,
    QIODevice,
    QJsonDocument,
    QThread,
    QUrl,
)
from qgis.PyQt.QtGui import QImage
from qgis.PyQt.QtNetwork import (
    QHttpMultiPart,
    QHttpPart,
    QNetworkReply,
    QNetworkRequest,
)


def _get_plugin_version() -> str:
    """Read the plugin version from metadata.txt."""
    metadata_path = os.path.join(os.path.dirname(__file__), "metadata.txt")
    config = configparser.ConfigParser()
    config.read(metadata_path)
    return config.get("general", "version", fallback="unknown")


PLUGIN_USER_AGENT = f"rana_plugin/{_get_plugin_version()}"

CONNECTIVITY_ERRORS = {
    QNetworkReply.NetworkError.HostNotFoundError,
    QNetworkReply.NetworkError.TimeoutError,
    QNetworkReply.NetworkError.ConnectionRefusedError,
    QNetworkReply.NetworkError.RemoteHostClosedError,
    QNetworkReply.NetworkError.NetworkSessionFailedError,
    QNetworkReply.NetworkError.UnknownNetworkError,
}


class NetworkUnavailableError(Exception):
    """Raised when a request fails due to connectivity issues."""

    pass


def _append_user_agent(request):
    """Request preprocessor that appends the plugin UA to QGIS's User-Agent.
    QGIS overwrites the User-Agent header in QgsNetworkAccessManager.createRequest(),
    so we must use a preprocessor (which runs after) to append our own identifier.
    Only applied to requests targeting the Rana API.
    """
    try:
        from rana_qgis_plugin.utils.settings import base_url

        url = request.url().toString()
        if not url.startswith(base_url()):
            return
    except Exception:
        return
    existing_ua = bytes(request.rawHeader(b"User-Agent")).decode("utf-8")
    if PLUGIN_USER_AGENT in existing_ua:
        return

    request.setRawHeader(
        b"User-Agent", f"{existing_ua} {PLUGIN_USER_AGENT}".encode("utf-8")
    )


_preprocessor_id = QgsNetworkAccessManager.setRequestPreprocessor(_append_user_agent)


class NetworkManager(object):
    """Network manager class for handling network requests."""

    def __init__(self, url: str, auth_cfg: Optional[str] = None):
        self._network_manager: QgsNetworkAccessManager = (  # type: ignore[assignment]
            QgsNetworkAccessManager.instance()  # type: ignore[assignment]
        )
        # Don't follow redirects automatically: the Rana API returns 302s to
        # S3 presigned URLs, and auto-following would forward the Authorization
        # header, causing S3 to reject the request with HTTP 400.
        self._network_manager.setRedirectPolicy(
            QNetworkRequest.RedirectPolicy.ManualRedirectPolicy
        )
        self._auth_manager: QgsAuthManager = QgsApplication.authManager()  # type: ignore[assignment]
        self._network_finished = False
        self._network_timeout = False
        self._url = url
        self._reply: QNetworkReply = None  # type: ignore[assignment]
        self._auth_cfg = auth_cfg
        self._content = None
        self._request: QNetworkRequest = None  # type: ignore[assignment]
        self.last_http_status = None

        if auth_cfg:
            is_auth_configured = self._auth_cfg in self._auth_manager.configIds()
            if not is_auth_configured:
                raise QgsProcessingException("Authorization not configured!")

    @property
    def content(self) -> Any:
        return self._content

    @property
    def network_finished(self):
        return self._network_finished

    @property
    def network_timeout(self):
        return self._network_timeout

    def fetch(self, params: Optional[dict] = None) -> tuple[bool, str | None]:
        self.prepare_request(params)
        self._reply = self._network_manager.get(self._request)  # type: ignore[assignment]
        return self.process_request()

    def post(
        self, params: Optional[dict] = None, payload: Optional[dict] = None
    ) -> tuple[bool, str | None]:
        self.prepare_request(params)
        self._reply = self._network_manager.post(
            self._request, json.dumps(payload or {}).encode("utf-8")
        )  # type: ignore[assignment]
        return self.process_request()

    def put(
        self, params: Optional[dict] = None, payload: Optional[dict] = None
    ) -> tuple[bool, str | None]:
        self.prepare_request(params)
        self._reply = self._network_manager.put(
            self._request, json.dumps(payload).encode("utf-8")
        )  # type: ignore[assignment]
        return self.process_request()

    def get_multipart_for_files(self, files: list):
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
        return multipart

    def post_multipart(
        self,
        params: Optional[dict] = None,
        files: Optional[list] = None,
        multipart_data: Optional[dict] = None,
    ) -> tuple[bool, str | None]:
        self.prepare_request(params)
        multipart = self.get_multipart_for_files(files)  # type: ignore[arg-type]
        if multipart_data:
            for field_name, field_value in multipart_data.items():
                field_part = QHttpPart()
                field_part.setHeader(
                    QNetworkRequest.KnownHeaders.ContentDispositionHeader,
                    f'form-data; name="{field_name}"',
                )
                field_part.setBody(
                    field_value.encode("utf-8")
                )  # Ensure it's sent as bytes
                multipart.append(field_part)
        # Don't set ContentTypeHeader manually - multipart sets it with boundary
        # Remove the content-type header from prepare_request
        self._request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, None)
        self._reply = self._network_manager.post(self._request, multipart)  # type: ignore[assignment]
        multipart.setParent(self._reply)  # Delete multipart with reply
        return self.process_request()

    def put_multipart(
        self, params: Optional[dict] = None, files: Optional[dict] = None
    ) -> tuple[bool, str | None]:
        self.prepare_request(params)
        multipart = self.get_multipart_for_files(files)  # type: ignore[arg-type]
        # Don't set ContentTypeHeader manually - multipart sets it with boundary
        # Remove the content-type header from prepare_request
        self._request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, None)
        self._reply = self._network_manager.put(self._request, multipart)  # type: ignore[assignment]
        multipart.setParent(self._reply)  # Delete multipart with reply
        return self.process_request()

    def delete(self, params: Optional[dict] = None) -> tuple[bool, str | None]:
        self.prepare_request(params)
        self._reply = self._network_manager.deleteResource(self._request)  # type: ignore[assignment]
        return self.process_request()

    def prepare_request(self, params: Optional[dict] = None):
        # Initialize some properties again
        self._content = None
        self._reply = None  # type: ignore[assignment]
        self._request = None  # type: ignore[assignment]
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

    def process_request(self) -> tuple[bool, str | None]:
        assert self._reply is not None
        # Keep the reply in a local variable while the nested event loop runs.
        # The NetworkManager instance may be accessed again from code handling
        # events, so response processing must remain tied to this request.
        reply = self._reply
        event_loop = QEventLoop()

        def on_finished() -> None:
            # QNetworkReply is asynchronous, but callers of this class expect
            # fetch/post/etc. to return only after their request is complete.
            self.fetch_finished()
            event_loop.quit()

        def on_timeout(timed_out_reply=None) -> None:
            # QgsNetworkAccessManager emits this signal for all requests made
            # through that manager. Only handle a timeout for this reply.
            if timed_out_reply is None or timed_out_reply is reply:
                self.request_timeout()

        reply.finished.connect(on_finished)
        self._network_manager.requestTimedOut.connect(on_timeout)
        try:
            if not reply.isFinished():
                # Process events until this reply finishes without allowing
                # mouse/keyboard input to re-enter the initiating action.
                # Other queued events may still be delivered by this loop.
                event_loop.exec(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
        finally:
            # These handlers are only needed while this request is pending.
            # Disconnect them even when event processing raises or is stopped.
            reply.finished.disconnect(on_finished)
            self._network_manager.requestTimedOut.disconnect(on_timeout)

        description = None
        self.last_http_status = reply.attribute(
            QNetworkRequest.Attribute.HttpStatusCodeAttribute
        )
        # Check for redirect status codes FIRST (before checking for errors)
        if reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute) in (
            301,
            302,
            303,
            307,
            308,
        ):
            location = reply.rawHeader(b"Location")
            if location:
                redirect_url = str(location, "utf-8")
                reply.deleteLater()
                return True, redirect_url
            else:
                reply.deleteLater()
                return False, "Redirect response missing Location header"

        if reply.error() != QNetworkReply.NetworkError.NoError:
            error_code = reply.error()
            description = reply.errorString()
            reply.deleteLater()
            if error_code in CONNECTIVITY_ERRORS:
                raise NetworkUnavailableError(description)
            status = False
            raw_content = reply.readAll()
            try:
                self._content = json.loads(str(raw_content, "utf-8"))
            except json.JSONDecodeError:
                pass
        else:
            status = True
            if (
                reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
                == 204
            ):
                reply.deleteLater()
                return status, description

            raw_content = reply.readAll()
            content_type = reply.header(QNetworkRequest.KnownHeaders.ContentTypeHeader)
            content_type = str(content_type) if content_type else ""
            if content_type.startswith("application/json"):
                json_doc = QJsonDocument.fromJson(raw_content)
                if json_doc.isObject():
                    self._content = (
                        json_doc.toVariant()
                    )  # Returns QVariant which can be used like a Python dict
                else:
                    try:
                        self._content = json.loads(str(raw_content, "utf-8"))
                    except json.JSONDecodeError:
                        status = False
                        description = (
                            f"Received an invalid response body (HTTP "
                            f"{self.last_http_status}, content-type="
                            f"{content_type!r}, {len(raw_content)} bytes)"
                        )
            elif content_type.startswith("image/"):
                image = QImage()
                image.loadFromData(raw_content)
                self._content = image
            else:
                try:
                    self._content = json.loads(str(raw_content, "utf-8"))
                except json.JSONDecodeError:
                    status = False
                    description = (
                        f"Received an invalid response body (HTTP "
                        f"{self.last_http_status}, content-type="
                        f"{content_type!r}, {len(raw_content)} bytes)"
                    )
        reply.deleteLater()
        return status, description

    def fetch_finished(self):
        """Called when fetching metadata has finished."""
        self._network_finished = True

    def request_timeout(self):
        """Called when a request timeout signal is emitted."""
        self._network_timeout = True
