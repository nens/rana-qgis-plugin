from collections.abc import Sequence
from functools import wraps
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from qgis.core import Qgis, QgsMessageLog

from rana_qgis_plugin.constant import PLUGIN_NAME

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


def install_request_logger(api_client: Any) -> None:
    """Log redacted request attempts for a ThreeDi API client instance."""
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
