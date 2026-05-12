from unittest.mock import patch

import pytest

from rana_qgis_plugin.widgets.utils_file_action import (
    FileAction,
    get_file_actions,
    get_file_actions_by_data_type,
)


@pytest.mark.parametrize(
    "data_type,expected_actions",
    [
        (
            "vector",
            {
                FileAction.DELETE,
                FileAction.RENAME,
                FileAction.OPEN_IN_QGIS,
                FileAction.UPLOAD_FILE,
                FileAction.SAVE_VECTOR_STYLING,
                FileAction.OPEN_IN_FILE_BROWSER,
            },
        ),
        (
            "raster",
            {
                FileAction.DELETE,
                FileAction.RENAME,
                FileAction.OPEN_IN_QGIS,
                FileAction.UPLOAD_FILE,
                FileAction.SAVE_RASTER_STYLING,
                FileAction.OPEN_IN_FILE_BROWSER,
            },
        ),
        (
            "sqlite",
            {
                FileAction.DELETE,
                FileAction.RENAME,
                FileAction.OPEN_IN_QGIS,
                FileAction.OPEN_IN_FILE_BROWSER,
            },
        ),
        (
            "unknown_type",
            {
                FileAction.DELETE,
                FileAction.RENAME,
            },
        ),
    ],
)
def test_get_file_actions_by_data_type(data_type, expected_actions):
    """Test that each data type returns the correct set of actions."""
    actions = get_file_actions_by_data_type(data_type)
    actions_set = set(actions)

    # Check that actions match expected exactly
    assert actions_set == expected_actions, (
        f"Actions mismatch for {data_type}:\n"
        f"  Missing: {expected_actions - actions_set}\n"
        f"  Unexpected: {actions_set - expected_actions}"
    )

    # Verify actions are sorted
    assert actions == sorted(actions)


@pytest.mark.parametrize(
    "has_3di_authcfg,expected_actions",
    [
        (
            True,
            {
                FileAction.REMOVE_FROM_PROJECT,
                FileAction.RENAME,
                FileAction.OPEN_IN_QGIS,
                FileAction.SAVE_REVISION,
                FileAction.VIEW_REVISIONS,
                FileAction.OPEN_IN_BROWSER,
                FileAction.OPEN_IN_FILE_BROWSER,
            },
        ),
        (
            False,
            {
                FileAction.REMOVE_FROM_PROJECT,
                FileAction.RENAME,
                FileAction.OPEN_IN_BROWSER,
            },
        ),
    ],
)
@patch("rana_qgis_plugin.widgets.utils_file_action.has_3di_authcfg")
def test_get_file_actions_by_data_type_threedi_schematisation(
    mock_has_3di_authcfg, has_3di_authcfg, expected_actions
):
    """Test 3Di schematisation actions with and without authentication."""
    mock_has_3di_authcfg.return_value = has_3di_authcfg
    actions = get_file_actions_by_data_type("threedi_schematisation")
    actions_set = set(actions)

    assert actions_set == expected_actions, (
        f"Actions mismatch for threedi_schematisation (auth={has_3di_authcfg}):\n"
        f"  Missing: {expected_actions - actions_set}\n"
        f"  Unexpected: {actions_set - expected_actions}"
    )

    # Verify actions are sorted
    assert actions == sorted(actions)


@pytest.mark.parametrize(
    "descriptor,expected_actions,test_id",
    [
        (
            {
                "meta": {
                    "id": "sim123",
                    "simulation": {"software": {"id": "3Di"}},
                }
            },
            {
                FileAction.DOWNLOAD_RESULTS,
                FileAction.OPEN_WMS,
                FileAction.COPY_WMS_URL,
                FileAction.OPEN_IN_FILE_BROWSER,
            },
            "3di_simulation",
        ),
        (
            {
                "meta": {
                    "id": "sim123",
                    "simulation": {"software": {"id": "OtherSoftware"}},
                }
            },
            {FileAction.DOWNLOAD_RESULTS, FileAction.OPEN_IN_FILE_BROWSER},
            "non_3di_simulation",
        ),
        (
            {
                "meta": None,
                "status": {"id": "processing"},
            },
            set(),  # Empty set - all actions removed for processing scenarios
            "processing",
        ),
    ],
)
@patch("rana_qgis_plugin.widgets.utils_file_action.get_tenant_file_descriptor")
def test_get_file_actions_for_data_type_scenarios(
    mock_get_descriptor, descriptor, expected_actions, test_id
):
    mock_get_descriptor.return_value = descriptor
    selected_item = {
        "id": "test/scenario.json",
        "type": "file",
        "data_type": "scenario",
        "descriptor_id": "desc789",
    }

    actions = get_file_actions(selected_item)
    actions_set = set(actions)

    if expected_actions:
        # Check that expected scenario-specific actions are present
        assert expected_actions.issubset(actions_set), (
            f"Scenario actions missing for {test_id}:\n"
            f"  Expected: {expected_actions}\n"
            f"  Got: {actions_set}"
        )
    else:
        # Processing scenarios should return empty list
        assert actions_set == expected_actions, (
            f"Processing scenario should have no actions, got: {actions_set}"
        )

    # Verify actions are sorted
    assert actions == sorted(actions)
