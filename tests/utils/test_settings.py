from unittest.mock import MagicMock, patch

import pytest

from rana_qgis_plugin.utils.settings import get_advanced_settings, get_hcc_url_override


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


@pytest.mark.parametrize(
    "hcc_url_value,excepthook_value,expected_dict",
    [
        (None, None, {}),
        (
            "https://dev-3di-api.example.com",
            None,
            {"hcc_url": "https://dev-3di-api.example.com"},
        ),
        (None, "true", {"use_plugin_excepthook": "true"}),
        (
            "https://dev-3di-api.example.com",
            "true",
            {
                "hcc_url": "https://dev-3di-api.example.com",
                "use_plugin_excepthook": "true",
            },
        ),
        ("", None, {}),
        (None, "", {}),
        ("", "", {}),
    ],
    ids=[
        "both_empty",
        "only_hcc_url",
        "only_excepthook",
        "both_set",
        "hcc_url_empty",
        "excepthook_empty",
        "both_empty_strings",
    ],
)
def test_get_advanced_settings(hcc_url_value, excepthook_value, expected_dict):
    """Test get_advanced_settings returns only non-empty settings"""
    with patch("rana_qgis_plugin.utils.settings.QgsSettings") as mock_settings:
        mock_instance = MagicMock()
        mock_settings.return_value = mock_instance

        def mock_value(key, default=None, **kwargs):
            if key == "Rana/hcc_url":
                return hcc_url_value if hcc_url_value else None
            elif key == "Rana/use_plugin_excepthook":
                return excepthook_value if excepthook_value else None
            return default

        mock_instance.value.side_effect = mock_value

        result = get_advanced_settings()
        assert result == expected_dict
