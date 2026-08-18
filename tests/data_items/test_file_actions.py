import pytest

from rana_qgis_plugin.data_items.file_actions import (
    FileAction,
    get_file_actions,
    get_folder_actions,
)


@pytest.mark.parametrize(
    "data_type, expected",
    [
        (
            "vector",
            [
                FileAction.VIEW_FILE_INFO,
                FileAction.OPEN_IN_QGIS,
                FileAction.OPEN_IN_BROWSER,
                FileAction.RENAME,
                FileAction.DELETE,
            ],
        ),
        (
            "scenario",
            [
                FileAction.VIEW_FILE_INFO,
                FileAction.OPEN_WMS,
                FileAction.DOWNLOAD_RESULTS,
                FileAction.RENAME,
                FileAction.DELETE,
            ],
        ),
        (
            "other",
            [
                FileAction.VIEW_FILE_INFO,
                FileAction.OPEN_IN_BROWSER,
                FileAction.RENAME,
                FileAction.DELETE,
            ],
        ),
    ],
)
def test_get_file_actions(data_type, expected):
    assert get_file_actions(data_type) == expected


def test_get_folder_actions_excludes_delete_and_rename_for_root():
    root_actions = get_folder_actions(is_root=True)
    assert FileAction.DELETE not in root_actions
    assert FileAction.RENAME not in root_actions


def test_get_folder_actions_includes_delete_and_rename_for_non_root():
    non_root_actions = get_folder_actions(is_root=False)
    assert FileAction.DELETE in non_root_actions
    assert FileAction.RENAME in non_root_actions
