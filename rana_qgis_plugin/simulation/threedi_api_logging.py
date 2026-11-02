from collections.abc import Sequence
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

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
