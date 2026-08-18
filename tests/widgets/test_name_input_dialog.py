import pytest

from rana_qgis_plugin.widgets.name_input_dialog import validate_item_name


@pytest.mark.parametrize(
    "name",
    ["hello", "my_file.tif", "folder-name", "name with spaces"],
)
def test_valid_names(name):
    assert validate_item_name(name) is None


@pytest.mark.parametrize(
    "name,expected_fragment",
    [
        ("", "empty"),
        ("   ", "empty"),
        (".", "'.'"),
        ("..", "'.'"),
        ("path/to", "slashes"),
        ("back\\slash", "slashes"),
        (" leading", "leading or trailing"),
        ("trailing ", "leading or trailing"),
    ],
)
def test_invalid_names(name, expected_fragment):
    error = validate_item_name(name)
    assert error is not None
    assert expected_fragment in error.lower()
