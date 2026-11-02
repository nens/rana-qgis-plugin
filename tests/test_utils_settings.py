from unittest.mock import MagicMock, patch

import pytest

from rana_qgis_plugin.utils.settings import (
    get_advanced_settings,
    get_hcc_url_override,
    get_log_api_requests,
)


@pytest.mark.parametrize(
    "mock_return_value,expected_result",
    [
        (None, None),
        ("https://dev-3di-api.example.com", "https://dev-3di-api.example.com"),
        ("", None),
    ],
    ids=["not_set", "with_value", "empty_string"],
)
def test_get_hcc_url_override(mock_return_value, expected_result):
    """Test get_hcc_url_override with various QgsSettings values"""
    with patch("rana_qgis_plugin.utils.settings.QgsSettings") as mock_settings:
        mock_instance = MagicMock()
        mock_settings.return_value = mock_instance
        mock_instance.value.return_value = mock_return_value

        result = get_hcc_url_override()
        assert result == expected_result
        mock_instance.value.assert_called_with("Rana/hcc_url")


@pytest.mark.parametrize("stored_value", [False, True])
def test_get_log_api_requests(stored_value):
    with patch("rana_qgis_plugin.utils.settings.QgsSettings") as mock_settings:
        mock_instance = MagicMock()
        mock_settings.return_value = mock_instance
        mock_instance.value.return_value = stored_value

        result = get_log_api_requests()

        assert result is stored_value
        mock_instance.value.assert_called_once_with(
            "Rana/log_api_requests", False, type=bool
        )


@pytest.mark.parametrize(
    "hcc_url_value,excepthook_value,request_logging_value,expected_dict",
    [
        (None, None, None, {}),
        (
            "https://dev-3di-api.example.com",
            None,
            None,
            {"hcc_url": "https://dev-3di-api.example.com"},
        ),
        (None, "true", None, {"use_plugin_excepthook": "true"}),
        (None, None, True, {"log_api_requests": True}),
        (
            "https://dev-3di-api.example.com",
            "true",
            True,
            {
                "hcc_url": "https://dev-3di-api.example.com",
                "use_plugin_excepthook": "true",
                "log_api_requests": True,
            },
        ),
        ("", None, None, {}),
        (None, "", None, {}),
        ("", "", "", {}),
    ],
    ids=[
        "both_empty",
        "only_hcc_url",
        "only_excepthook",
        "only_request_logging",
        "both_set",
        "hcc_url_empty",
        "excepthook_empty",
        "both_empty_strings",
    ],
)
def test_get_advanced_settings(
    hcc_url_value, excepthook_value, request_logging_value, expected_dict
):
    """Test get_advanced_settings returns only non-empty settings"""
    with patch("rana_qgis_plugin.utils.settings.QgsSettings") as mock_settings:
        mock_instance = MagicMock()
        mock_settings.return_value = mock_instance

        def mock_value(key, default=None, **kwargs):
            if key == "Rana/hcc_url":
                return hcc_url_value if hcc_url_value else None
            elif key == "Rana/use_plugin_excepthook":
                return excepthook_value if excepthook_value else None
            elif key == "Rana/log_api_requests":
                return request_logging_value if request_logging_value else None
            return default

        mock_instance.value.side_effect = mock_value

        result = get_advanced_settings()
        assert result == expected_dict
