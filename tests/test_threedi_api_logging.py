from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from qgis.core import Qgis

import rana_qgis_plugin.simulation.threedi_api_logging as api_logging
import rana_qgis_plugin.simulation.threedi_calls as threedi_calls
from rana_qgis_plugin.simulation.threedi_api_logging import (
    build_request_summary,
    redact_query_params,
)


@pytest.mark.parametrize(
    "params,expected",
    [
        ([("limit", 10)], [("limit", 10)]),
        ([("Api_Key", "secret-value")], [("Api_Key", "***")]),
    ],
)
def test_redact_query_params(params, expected):
    assert redact_query_params(params) == expected


def test_build_request_summary_redacts_params_and_url_query():
    summary = build_request_summary(
        "get",
        "https://user:password@example.test/items?api_key=url-secret&limit=5",
        [("access_token", "param-secret"), ("limit", 5)],
    )

    assert summary == (
        "GET https://example.test/items?api_key=%2A%2A%2A&limit=5 "
        "params=[('access_token', '***'), ('limit', 5)]"
    )
    assert "url-secret" not in summary
    assert "param-secret" not in summary
    assert "password" not in summary


def test_build_request_summary_without_query_params():
    assert build_request_summary("POST", "https://example.test/items") == (
        "POST https://example.test/items"
    )


def make_api_client(request):
    rest_client = SimpleNamespace(request=request)
    return SimpleNamespace(_client=SimpleNamespace(rest_client=rest_client))


def test_install_request_logger_logs_attempt_and_returns_result():
    result = object()
    original_request = Mock(return_value=result)
    api_client = make_api_client(original_request)
    with patch.object(api_logging, "log_message") as log_message:
        api_logging.install_request_logger(api_client)
        actual = api_client._client.rest_client.request(
            "GET", "https://example.test/items", [("limit", 5)]
        )

    assert actual is result
    original_request.assert_called_once_with(
        "GET", "https://example.test/items", [("limit", 5)]
    )
    log_message.assert_called_once_with(
        "ThreeDi API request attempt: GET https://example.test/items "
        "params=[('limit', 5)]",
        Qgis.MessageLevel.Info,
    )


def test_install_request_logger_logs_failure_without_exception_text():
    error = RuntimeError("could contain secrets")
    original_request = Mock(side_effect=error)
    api_client = make_api_client(original_request)
    with patch.object(api_logging, "log_message") as log_message:
        api_logging.install_request_logger(api_client)
        with pytest.raises(RuntimeError, match="could contain secrets") as exc_info:
            api_client._client.rest_client.request("GET", "https://example.test/items")

    assert exc_info.value is error
    assert log_message.call_count == 2
    assert log_message.call_args_list[-1].args == (
        "ThreeDi API request failed: GET https://example.test/items (RuntimeError)",
        Qgis.MessageLevel.Warning,
    )
    assert "could contain secrets" not in str(log_message.call_args_list)


def test_install_request_logger_fails_open_when_attempt_log_raises():
    result = object()
    original_request = Mock(return_value=result)
    api_client = make_api_client(original_request)
    with patch.object(
        api_logging, "log_message", side_effect=RuntimeError("logger failed")
    ):
        api_logging.install_request_logger(api_client)
        actual = api_client._client.rest_client.request("GET", "https://example.test")

    assert actual is result
    original_request.assert_called_once()


def test_install_request_logger_preserves_transport_error_if_warning_log_raises():
    error = RuntimeError("transport failed")
    original_request = Mock(side_effect=error)
    api_client = make_api_client(original_request)
    with patch.object(
        api_logging,
        "log_message",
        side_effect=[None, RuntimeError("logger failed")],
    ):
        api_logging.install_request_logger(api_client)
        with pytest.raises(RuntimeError, match="transport failed") as exc_info:
            api_client._client.rest_client.request("GET", "https://example.test")

    assert exc_info.value is error


def test_install_request_logger_logs_api_status_without_reason():
    error = RuntimeError("secret reason")
    setattr(error, "status", 503)
    original_request = Mock(side_effect=error)
    api_client = make_api_client(original_request)
    with patch.object(api_logging, "log_message") as log_message:
        api_logging.install_request_logger(api_client)
        with pytest.raises(RuntimeError):
            api_client._client.rest_client.request("GET", "https://example.test")

    assert log_message.call_args_list[-1].args == (
        "ThreeDi API request failed: GET https://example.test "
        "(RuntimeError, HTTP status 503)",
        Qgis.MessageLevel.Warning,
    )
    assert "secret reason" not in str(log_message.call_args_list)


def test_install_request_logger_fails_open_when_summary_fails():
    result = object()
    original_request = Mock(return_value=result)
    api_client = make_api_client(original_request)
    with (
        patch.object(
            api_logging,
            "build_request_summary",
            side_effect=RuntimeError("format failed"),
        ),
        patch.object(api_logging, "log_message") as log_message,
    ):
        api_logging.install_request_logger(api_client)
        actual = api_client._client.rest_client.request("GET", "https://example.test")

    assert actual is result
    original_request.assert_called_once()
    assert not log_message.called


def test_install_request_logger_skips_missing_transport_and_warns_once():
    with (
        patch.object(api_logging, "log_message") as log_message,
        patch.object(api_logging, "_INSTALLATION_WARNING_EMITTED", False),
    ):
        api_logging.install_request_logger(SimpleNamespace())
        api_logging.install_request_logger(SimpleNamespace())

    log_message.assert_called_once_with(
        "ThreeDi API request logging could not be installed; continuing without it.",
        Qgis.MessageLevel.Warning,
    )


@patch("rana_qgis_plugin.simulation.threedi_calls.install_request_logger")
@patch("rana_qgis_plugin.simulation.threedi_calls.ThreediApi")
def test_personal_token_factory_installs_request_logger(
    threedi_api_class, install_logger
):
    api_client = object()
    threedi_api_class.return_value = api_client

    result = threedi_calls.get_api_client_with_personal_api_token(
        "api-token", "https://api.example", version="v3"
    )

    assert result is api_client
    threedi_api_class.assert_called_once_with(
        config={
            "THREEDI_API_HOST": "https://api.example",
            "THREEDI_API_USERNAME": "__key__",
            "THREEDI_API_PERSONAL_API_TOKEN": "api-token",
        },
        version="v3",
    )
    install_logger.assert_called_once_with(api_client)
