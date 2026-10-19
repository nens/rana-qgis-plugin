from unittest.mock import MagicMock, patch

from rana_qgis_plugin.utils.api import get_user_tenants, paginated_fetch


def test_paginated_fetch_returns_all_pages():
    responses = [
        {"total": 101, "items": [{"id": f"tenant-{i}"} for i in range(100)]},
        {"total": 101, "items": [{"id": "tenant-100"}]},
    ]

    with patch(
        "rana_qgis_plugin.utils.api.single_fetch", side_effect=responses
    ) as single_fetch:
        result = paginated_fetch(
            "https://rana.test/tenants", limit=100, params={"user_id": "user-1"}
        )

    assert result == {
        "total": 101,
        "items": [{"id": f"tenant-{i}"} for i in range(101)],
    }


def test_get_user_tenants_fetches_filtered_tenants():
    communication = MagicMock()
    with (
        patch("rana_qgis_plugin.utils.api.api_url", return_value="https://rana.test"),
        patch(
            "rana_qgis_plugin.utils.api.paginated_fetch",
            return_value={"total": 1, "items": [{"id": "tenant-1"}]},
        ) as fetch,
    ):
        tenants = get_user_tenants(communication, "user-1")

    assert tenants == [{"id": "tenant-1"}]
