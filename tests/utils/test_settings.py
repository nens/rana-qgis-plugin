import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from qgis.core import QgsSettings

from rana_qgis_plugin.utils.settings import (
    base_url,
    get_advanced_settings,
    get_hidden_projects,
    rana_open_cache_dir,
    read_hidden_projects,
    set_base_url,
    set_hidden_projects,
    set_rana_open_cache_dir,
    unhide_project,
)

BASE_URL = "https://www.ranawaterintelligence.com"
TENANT = "tenant-uuid-123"
OTHER_TENANT = "tenant-uuid-456"
OTHER_BASE = "https://staging.rana.com"


@pytest.fixture(scope="function")
def settings():
    settings = QgsSettings()
    rana_keys = [key for key in settings.allKeys() if key.startswith("Rana/")]
    for key in rana_keys:
        print(f"Removing key: {key}")
        settings.remove(key)
    return settings


def test_rana_open_cache_dir_default(settings):
    assert rana_open_cache_dir() == str(Path(tempfile.gettempdir()) / "rana_downloads")


def test_set_rana_open_cache_dir(settings):
    custom_dir = "/tmp/custom-rana-open"
    set_rana_open_cache_dir(custom_dir)
    assert rana_open_cache_dir() == custom_dir


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
def test_get_advanced_settings(
    settings, hcc_url_value, excepthook_value, expected_dict
):
    if hcc_url_value:
        settings.setValue("Rana/hcc_url", hcc_url_value)
    if excepthook_value:
        settings.setValue("Rana/use_plugin_excepthook", excepthook_value)
    result = get_advanced_settings()
    assert result == expected_dict


@pytest.mark.parametrize(
    "input_url,expected_stored",
    [
        ("https://example.com", "https://example.com"),
        ("https://example.com/", "https://example.com"),
        ("https://example.com///", "https://example.com"),
    ],
    ids=["no_slash", "trailing_slash", "multiple_trailing_slashes"],
)
def test_set_base_url_strips_trailing_slash(input_url, expected_stored):
    set_base_url(input_url)
    assert base_url() == expected_stored


@pytest.fixture()
def hidden_file(tmp_path):
    """Patch hidden_projects_file() to use a temp path."""
    rana_dir = tmp_path / "rana"
    rana_dir.mkdir()
    path = rana_dir / "hidden_projects.json"
    with patch(
        "rana_qgis_plugin.utils.settings.hidden_projects_file",
        return_value=path,
    ):
        yield path


def test_read_hidden_projects_missing_file(hidden_file):
    assert read_hidden_projects() == {}


def test_read_hidden_projects_unset(hidden_file):
    assert read_hidden_projects() == {}


@pytest.mark.parametrize(
    "json_str,expected",
    [
        ('{"valid": ["project-1"]}', {"valid": ["project-1"]}),
        ('"{invalid"', {}),
        (
            '{"valid": ["project-1"], "not-a-list": "project-2", "mixed": [1]}',
            {"valid": ["project-1"]},
        ),
    ],
)
def test_read_hidden_projects_malformed(hidden_file, json_str, expected):
    hidden_file.write_text(json_str, encoding="utf-8")
    assert read_hidden_projects() == expected


def test_invalid_hidden_projects_data_is_ignored(hidden_file):
    hidden_file.write_text(
        '{"valid": ["project-1"], "not-a-list": "project-2", "mixed": [1]}',
        encoding="utf-8",
    )
    assert read_hidden_projects() == {"valid": ["project-1"]}


def test_get_hidden_projects_missing_file(hidden_file):
    assert get_hidden_projects(BASE_URL, TENANT) == set()


def test_get_hidden_projects_unset(hidden_file):
    assert get_hidden_projects(BASE_URL, TENANT) == set()


def test_get_hidden_projects(hidden_file):
    hidden_file.write_text(
        f'{{"{BASE_URL}|{TENANT}": ["project-1", "project-2"]}}', encoding="utf-8"
    )
    assert get_hidden_projects(BASE_URL, TENANT) == {"project-1", "project-2"}


def test_set_hidden_projects_recovers_from_malformed_file(hidden_file):
    hidden_file.write_text("{invalid", encoding="utf-8")
    set_hidden_projects(BASE_URL, TENANT, {"project-1"})
    assert get_hidden_projects(BASE_URL, TENANT) == {"project-1"}


def test_set_hidden_projects_removes_empty_scope(hidden_file):
    set_hidden_projects(BASE_URL, TENANT, {"project-1"})
    set_hidden_projects(BASE_URL, TENANT, set())
    assert get_hidden_projects(BASE_URL, TENANT) == set()


def test_set_hidden_projects(hidden_file):
    set_hidden_projects(BASE_URL, TENANT, {"project-1", "project-2"})
    assert (
        hidden_file.read_text(encoding="utf-8")
        == f'{{"{BASE_URL}|{TENANT}": ["project-1", "project-2"]}}'
    )


def test_scopes_are_independent(hidden_file):
    set_hidden_projects(BASE_URL, TENANT, {"proj-a"})
    set_hidden_projects(BASE_URL, OTHER_TENANT, {"proj-b"})
    set_hidden_projects(OTHER_BASE, TENANT, {"proj-c"})
    assert get_hidden_projects(BASE_URL, TENANT) == {"proj-a"}
    assert get_hidden_projects(BASE_URL, OTHER_TENANT) == {"proj-b"}
    assert get_hidden_projects(OTHER_BASE, TENANT) == {"proj-c"}


def test_unhide_project(hidden_file):
    set_hidden_projects(BASE_URL, TENANT, {"proj-1", "proj-2"})
    unhide_project(BASE_URL, TENANT, "proj-1")
    assert get_hidden_projects(BASE_URL, TENANT) == {"proj-2"}
