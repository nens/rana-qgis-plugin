from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from qgis.core import Qgis

import rana_qgis_plugin.simulation.threedi_calls as threedi_calls
import rana_qgis_plugin.utils.api_logging as api_logging
from rana_qgis_plugin.utils.api_logging import (
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


def test_redact_url_query_omits_fragment():
    summary = api_logging.redact_url_query(
        "https://example.test/items?limit=5#access_token=secret"
    )

    assert summary == "https://example.test/items?limit=5"
    assert "secret" not in summary


def make_api_client(request):
    rest_client = SimpleNamespace(request=request)
    return SimpleNamespace(_client=SimpleNamespace(rest_client=rest_client))


def test_install_threedi_request_logger_logs_attempt_and_returns_result():
    result = object()
    original_request = Mock(return_value=result)
    api_client = make_api_client(original_request)
    with patch.object(api_logging, "log_message") as log_message:
        api_logging.install_threedi_request_logger(api_client)
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


def test_install_threedi_request_logger_logs_failure_without_exception_text():
    # The exception's text is excluded because it may contain response
    # headers/body content (the client's ApiException includes both in its
    # string representation), which must not be logged.
    error = RuntimeError("could contain secrets")
    original_request = Mock(side_effect=error)
    api_client = make_api_client(original_request)
    with patch.object(api_logging, "log_message") as log_message:
        api_logging.install_threedi_request_logger(api_client)
        with pytest.raises(RuntimeError, match="could contain secrets") as exc_info:
            api_client._client.rest_client.request("GET", "https://example.test/items")

    assert exc_info.value is error
    assert log_message.call_count == 2
    assert log_message.call_args_list[-1].args == (
        "ThreeDi API request failed: GET https://example.test/items (RuntimeError)",
        Qgis.MessageLevel.Warning,
    )
    assert "could contain secrets" not in str(log_message.call_args_list)


def test_install_threedi_request_logger_still_sends_request_when_attempt_log_raises():
    result = object()
    original_request = Mock(return_value=result)
    api_client = make_api_client(original_request)
    with patch.object(
        api_logging, "log_message", side_effect=RuntimeError("logger failed")
    ):
        api_logging.install_threedi_request_logger(api_client)
        actual = api_client._client.rest_client.request("GET", "https://example.test")

    assert actual is result
    original_request.assert_called_once()


def test_install_threedi_request_logger_preserves_transport_error_if_warning_log_raises():
    error = RuntimeError("transport failed")
    original_request = Mock(side_effect=error)
    api_client = make_api_client(original_request)
    with patch.object(
        api_logging,
        "log_message",
        side_effect=[None, RuntimeError("logger failed")],
    ):
        api_logging.install_threedi_request_logger(api_client)
        with pytest.raises(RuntimeError, match="transport failed") as exc_info:
            api_client._client.rest_client.request("GET", "https://example.test")

    assert exc_info.value is error


def test_install_threedi_request_logger_logs_api_status_without_reason():
    error = RuntimeError("secret reason")
    setattr(error, "status", 503)
    original_request = Mock(side_effect=error)
    api_client = make_api_client(original_request)
    with patch.object(api_logging, "log_message") as log_message:
        api_logging.install_threedi_request_logger(api_client)
        with pytest.raises(RuntimeError):
            api_client._client.rest_client.request("GET", "https://example.test")

    assert log_message.call_args_list[-1].args == (
        "ThreeDi API request failed: GET https://example.test "
        "(RuntimeError, HTTP status 503)",
        Qgis.MessageLevel.Warning,
    )
    assert "secret reason" not in str(log_message.call_args_list)


def test_install_threedi_request_logger_still_sends_request_when_summary_raises():
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
        api_logging.install_threedi_request_logger(api_client)
        actual = api_client._client.rest_client.request("GET", "https://example.test")

    assert actual is result
    original_request.assert_called_once()
    assert not log_message.called


def test_install_threedi_request_logger_skips_missing_transport_and_warns_once():
    with (
        patch.object(api_logging, "log_message") as log_message,
        patch.object(api_logging, "_INSTALLATION_WARNING_EMITTED", False),
    ):
        api_logging.install_threedi_request_logger(SimpleNamespace())
        api_logging.install_threedi_request_logger(SimpleNamespace())

    log_message.assert_called_once_with(
        "ThreeDi API request logging could not be installed; continuing without it.",
        Qgis.MessageLevel.Warning,
    )


@patch("rana_qgis_plugin.simulation.threedi_calls.install_threedi_request_logger")
@patch("rana_qgis_plugin.simulation.threedi_calls.ThreediApi")
@patch("rana_qgis_plugin.simulation.threedi_calls.get_log_api_requests")
@pytest.mark.parametrize("logging_enabled_return", [True, False])
def test_personal_token_factory_installs_request_logger(
    logging_enabled, threedi_api_class, install_logger, logging_enabled_return
):
    api_client = object()
    threedi_api_class.return_value = api_client
    logging_enabled.return_value = logging_enabled_return

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
    if logging_enabled_return:
        install_logger.assert_called_once_with(api_client)
    else:
        install_logger.assert_not_called()


def test_build_upload_summary_omits_query_string():
    summary = api_logging.build_upload_summary(
        "put",
        "https://user:password@example.test/bucket/file?signature=secret&x=1",
    )

    assert summary == "PUT https://example.test/bucket/file"
    assert "signature" not in summary
    assert "secret" not in summary
    assert "password" not in summary


def test_logged_put_logs_attempt_and_returns_result():
    response = object()
    with (
        patch.object(api_logging, "get_log_api_requests", return_value=True),
        patch.object(api_logging.requests, "put", return_value=response) as put,
        patch.object(api_logging, "log_message") as log_message,
    ):
        actual = api_logging.logged_put(
            "https://example.test/bucket/file?sig=secret", data=b"payload"
        )

    assert actual is response
    put.assert_called_once_with(
        "https://example.test/bucket/file?sig=secret", data=b"payload"
    )
    log_message.assert_called_once_with(
        "Upload attempt: PUT https://example.test/bucket/file",
        Qgis.MessageLevel.Info,
    )


def test_logged_put_logs_failure_without_exception_text():
    # The exception's text is excluded because, for HTTP errors (e.g. from
    # response.raise_for_status()), it commonly includes the full request
    # URL -- including the query string this summary otherwise omits,
    # since that query string may contain a presigned signature.
    error = RuntimeError("could contain secrets")
    with (
        patch.object(api_logging, "get_log_api_requests", return_value=True),
        patch.object(api_logging.requests, "put", side_effect=error),
        patch.object(api_logging, "log_message") as log_message,
    ):
        with pytest.raises(RuntimeError, match="could contain secrets") as exc_info:
            api_logging.logged_put("https://example.test/bucket/file")

    assert exc_info.value is error
    assert log_message.call_count == 2
    assert log_message.call_args_list[-1].args == (
        "Upload failed: PUT https://example.test/bucket/file (RuntimeError)",
        Qgis.MessageLevel.Warning,
    )
    assert "could contain secrets" not in str(log_message.call_args_list)


def test_logged_put_still_sends_request_when_summary_raises():
    response = object()
    with (
        patch.object(
            api_logging,
            "build_upload_summary",
            side_effect=RuntimeError("format failed"),
        ),
        patch.object(api_logging.requests, "put", return_value=response) as put,
        patch.object(api_logging, "log_message") as log_message,
    ):
        actual = api_logging.logged_put("https://example.test/bucket/file")

    assert actual is response
    put.assert_called_once()
    assert not log_message.called


def test_logged_put_still_sends_request_when_attempt_log_raises():
    response = object()
    with (
        patch.object(
            api_logging, "log_message", side_effect=RuntimeError("logger failed")
        ),
        patch.object(api_logging.requests, "put", return_value=response) as put,
    ):
        actual = api_logging.logged_put("https://example.test/bucket/file")

    assert actual is response
    put.assert_called_once()


def test_logged_put_disabled_skips_logging_and_returns_result():
    response = object()
    with (
        patch.object(api_logging, "get_log_api_requests", return_value=False),
        patch.object(api_logging.requests, "put", return_value=response) as put,
        patch.object(api_logging, "log_message") as log_message,
    ):
        actual = api_logging.logged_put(
            "https://example.test/bucket/file?sig=secret", data=b"payload"
        )

    assert actual is response
    put.assert_called_once_with(
        "https://example.test/bucket/file?sig=secret", data=b"payload"
    )
    assert not log_message.called


def test_logged_put_disabled_skips_logging_on_failure():
    error = RuntimeError("could contain secrets")
    with (
        patch.object(api_logging, "get_log_api_requests", return_value=False),
        patch.object(api_logging.requests, "put", side_effect=error),
        patch.object(api_logging, "log_message") as log_message,
    ):
        with pytest.raises(RuntimeError, match="could contain secrets") as exc_info:
            api_logging.logged_put("https://example.test/bucket/file")

    assert exc_info.value is error
    assert not log_message.called


def test_get_logging_pool_disabled_returns_plain_pool_with_matching_retry_policy():
    with patch.object(api_logging, "get_log_api_requests", return_value=False):
        pool = api_logging.get_logging_pool()

    assert type(pool) is api_logging.urllib3.PoolManager
    retries = pool.connection_pool_kw["retries"]
    assert retries.total == 3
    assert retries.backoff_factor == 1.0


def test_get_logging_pool_enabled_returns_logging_pool_with_matching_retry_policy():
    with patch.object(api_logging, "get_log_api_requests", return_value=True):
        pool = api_logging.get_logging_pool()

    assert isinstance(pool, api_logging.LoggingPoolManager)
    retries = pool.connection_pool_kw["retries"]
    assert retries.total == 3
    assert retries.backoff_factor == 1.0


def test_logging_pool_manager_from_pool_reuses_source_pool_configuration():
    source_retries = api_logging.urllib3.util.retry.Retry(7, backoff_factor=2.5)
    source_pool = api_logging.urllib3.PoolManager(retries=source_retries)

    pool = api_logging.LoggingPoolManager.from_pool(source_pool)

    assert isinstance(pool, api_logging.LoggingPoolManager)
    assert pool.connection_pool_kw["retries"] is source_retries
    assert pool.headers == source_pool.headers


def test_get_logging_pool_disabled_returns_threedi_api_clients_own_pool():
    with (
        patch.object(api_logging, "get_log_api_requests", return_value=False),
        patch.object(api_logging, "get_pool") as get_pool_mock,
    ):
        pool = api_logging.get_logging_pool()

    get_pool_mock.assert_called_once_with()
    assert pool is get_pool_mock.return_value


def test_get_logging_pool_enabled_wraps_threedi_api_clients_own_pool():
    with (
        patch.object(api_logging, "get_log_api_requests", return_value=True),
        patch.object(api_logging, "get_pool") as get_pool_mock,
        patch.object(api_logging.LoggingPoolManager, "from_pool") as from_pool_mock,
    ):
        pool = api_logging.get_logging_pool()

    get_pool_mock.assert_called_once_with()
    from_pool_mock.assert_called_once_with(get_pool_mock.return_value)
    assert pool is from_pool_mock.return_value


def test_logging_pool_manager_logs_attempt_and_returns_result():
    response = object()
    pool = api_logging.LoggingPoolManager()
    with (
        patch.object(
            api_logging.urllib3.PoolManager, "request", return_value=response
        ) as request,
        patch.object(api_logging, "log_message") as log_message,
    ):
        actual = pool.request(
            "PUT", "https://example.test/bucket/file?sig=secret", body=b"payload"
        )

    assert actual is response
    request.assert_called_once_with(
        "PUT", "https://example.test/bucket/file?sig=secret", body=b"payload"
    )
    log_message.assert_called_once_with(
        "Upload attempt: PUT https://example.test/bucket/file",
        Qgis.MessageLevel.Info,
    )


def test_logging_pool_manager_logs_failure_without_exception_text():
    error = RuntimeError("could contain secrets")
    pool = api_logging.LoggingPoolManager()
    with (
        patch.object(api_logging.urllib3.PoolManager, "request", side_effect=error),
        patch.object(api_logging, "log_message") as log_message,
    ):
        with pytest.raises(RuntimeError, match="could contain secrets") as exc_info:
            pool.request("PUT", "https://example.test/bucket/file")

    assert exc_info.value is error
    assert log_message.call_count == 2
    assert log_message.call_args_list[-1].args == (
        "Upload failed: PUT https://example.test/bucket/file (RuntimeError)",
        Qgis.MessageLevel.Warning,
    )
    assert "could contain secrets" not in str(log_message.call_args_list)


def test_logging_pool_manager_still_sends_request_when_summary_raises():
    response = object()
    pool = api_logging.LoggingPoolManager()
    with (
        patch.object(
            api_logging,
            "build_upload_summary",
            side_effect=RuntimeError("format failed"),
        ),
        patch.object(
            api_logging.urllib3.PoolManager, "request", return_value=response
        ) as request,
        patch.object(api_logging, "log_message") as log_message,
    ):
        actual = pool.request("PUT", "https://example.test/bucket/file")

    assert actual is response
    request.assert_called_once()
    assert not log_message.called
