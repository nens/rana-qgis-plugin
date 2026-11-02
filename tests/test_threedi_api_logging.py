import pytest

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
