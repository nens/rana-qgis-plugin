from collections.abc import Sequence
from functools import wraps
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests
import urllib3
from qgis.core import Qgis, QgsMessageLog
from threedi_api_client.files import get_pool

from rana_qgis_plugin.constant import PLUGIN_NAME
from rana_qgis_plugin.utils.settings import get_log_api_requests

_INSTALLATION_WARNING_EMITTED = False
SENSITIVE_QUERY_TERMS = (
    "token",
    "password",
    "key",
    "secret",
    "authorization",
)


def is_sensitive_query_param(name: str) -> bool:
    """Return whether a query parameter name may contain a secret."""
    name = name.lower()
    return any(term in name for term in SENSITIVE_QUERY_TERMS)


def redact_query_params(
    params: Sequence[tuple[str, Any]] | None,
) -> list[tuple[str, Any]] | None:
    """Return query parameters with sensitive values replaced by ``***``."""
    if params is None:
        return None

    return [
        (name, "***" if is_sensitive_query_param(str(name)) else value)
        for name, value in params
    ]


def redact_url_query(url: str) -> str:
    """Redact sensitive values in a URL query string and omit user info."""
    parsed_url = urlsplit(url)
    query_params = parse_qsl(parsed_url.query, keep_blank_values=True)
    safe_query_params = redact_query_params(query_params)
    host = parsed_url.netloc.rsplit("@", 1)[-1]
    return urlunsplit(
        (
            parsed_url.scheme,
            host,
            parsed_url.path,
            urlencode(safe_query_params or []),
            parsed_url.fragment,
        )
    )


def build_request_summary(
    method: str,
    url: str,
    query_params: Sequence[tuple[str, Any]] | None = None,
) -> str:
    """Format a one-line request summary without headers or a body."""
    safe_url = redact_url_query(url)
    safe_params = redact_query_params(query_params)
    summary = f"{method.upper()} {safe_url}"
    if safe_params:
        summary += f" params={safe_params!r}"
    return summary


def log_message(message: str, level: Qgis.MessageLevel) -> None:
    """Write a diagnostic message without allowing logging failures to escape."""
    try:
        QgsMessageLog.logMessage(message, PLUGIN_NAME, level)
    except Exception:
        pass


def log_installation_warning_once() -> None:
    """Warn once if the client transport cannot be wrapped."""
    global _INSTALLATION_WARNING_EMITTED
    if _INSTALLATION_WARNING_EMITTED:
        return

    _INSTALLATION_WARNING_EMITTED = True
    log_message(
        "ThreeDi API request logging could not be installed; continuing without it.",
        Qgis.MessageLevel.Warning,
    )


def install_threedi_request_logger(api_client: Any) -> None:
    """Log redacted request attempts for a ThreeDi API client instance.

    This patches ``api_client._client.rest_client.request``, an internal
    attribute specific to the ``threedi-api-client`` package's ``ThreediApi``
    class, so it only applies to ThreeDi API clients.
    """
    try:
        rest_client = api_client._client.rest_client
        original_request = rest_client.request

        @wraps(original_request)
        def logged_request(method, url, *args, **kwargs):
            try:
                query_params = kwargs.get("query_params")
                if query_params is None and args:
                    query_params = args[0]
                summary = build_request_summary(method, url, query_params)
                log_message(
                    f"ThreeDi API request attempt: {summary}",
                    Qgis.MessageLevel.Info,
                )
            except Exception:
                summary = "request summary unavailable"

            try:
                return original_request(method, url, *args, **kwargs)
            except Exception as error:
                try:
                    status = getattr(error, "status", None)
                    if not isinstance(status, int):
                        status = None
                    status_text = (
                        f", HTTP status {status}" if status is not None else ""
                    )
                    log_message(
                        f"ThreeDi API request failed: {summary} "
                        f"({type(error).__name__}{status_text})",
                        Qgis.MessageLevel.Warning,
                    )
                except Exception:
                    pass
                raise

        rest_client.request = logged_request
    except Exception:
        log_installation_warning_once()


def build_upload_summary(method: str, url: str) -> str:
    """Format a one-line upload summary with the query string always omitted.

    Upload URLs are often presigned and may carry signatures or credentials
    in their query string, so unlike ``build_request_summary`` this never
    includes query parameters, not even redacted.
    """
    parsed_url = urlsplit(url)
    host = parsed_url.netloc.rsplit("@", 1)[-1]
    safe_url = urlunsplit((parsed_url.scheme, host, parsed_url.path, "", ""))
    return f"{method.upper()} {safe_url}"


def logged_put(url: str, **kwargs: Any) -> requests.Response:
    """Log a PUT upload attempt, then delegate to ``requests.put`` unchanged.

    Logging failures never prevent the upload or alter its result/exception.
    """
    try:
        summary = build_upload_summary("PUT", url)
        log_message(f"Upload attempt: {summary}", Qgis.MessageLevel.Info)
    except Exception:
        summary = "upload summary unavailable"

    try:
        return requests.put(url, **kwargs)
    except Exception as error:
        try:
            # The exception's text is excluded deliberately: for HTTP errors
            # (e.g. `response.raise_for_status()`), it commonly includes the
            # full request URL, including the query string this summary
            # otherwise omits because it may hold a presigned signature.
            log_message(
                f"Upload failed: {summary} ({type(error).__name__})",
                Qgis.MessageLevel.Warning,
            )
        except Exception:
            pass
        raise


class _LoggingPoolManager(urllib3.PoolManager):
    """A ``urllib3.PoolManager`` that logs each request attempt.

    Used only for ``threedi_api_client.files.upload_file()``, which does not
    use a ``ThreediApi`` instance and therefore cannot be instrumented via
    ``install_threedi_request_logger``. Behaves exactly like the base
    ``PoolManager`` except for logging; arguments, responses, and exceptions
    are passed through unchanged.
    """

    @classmethod
    def from_pool(cls, pool: urllib3.PoolManager) -> "_LoggingPoolManager":
        """Build a logging pool with the same configuration as ``pool``.

        Reuses ``pool``'s actual ``connection_pool_kw`` (which includes its
        retry policy) and headers, rather than re-specifying them here, so
        this stays in sync with whatever ``threedi_api_client.files.get_pool()``
        actually constructs.
        """
        return cls(headers=pool.headers, **pool.connection_pool_kw)

    def request(self, method, url, *args, **kwargs):
        try:
            summary = build_upload_summary(method, url)
            log_message(f"Upload attempt: {summary}", Qgis.MessageLevel.Info)
        except Exception:
            summary = "upload summary unavailable"

        try:
            return super().request(method, url, *args, **kwargs)
        except Exception as error:
            try:
                # See logged_put() for why the exception text is excluded.
                log_message(
                    f"Upload failed: {summary} ({type(error).__name__})",
                    Qgis.MessageLevel.Warning,
                )
            except Exception:
                pass
            raise


def get_logging_pool() -> urllib3.PoolManager:
    """Return a pool for ``threedi_api_client.files.upload_file(pool=...)``.

    When API request logging is disabled, this is simply
    ``threedi_api_client.files.get_pool()`` — the same default pool
    ``upload_file()`` would otherwise construct itself when no ``pool=`` is
    passed. When enabled, it returns a pool built with the same
    configuration that additionally logs each request attempt.
    """
    pool = get_pool()
    if not get_log_api_requests():
        return pool
    return _LoggingPoolManager.from_pool(pool)
