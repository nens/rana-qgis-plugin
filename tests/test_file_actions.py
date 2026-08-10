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
                FileAction.OPEN_IN_QGIS,
                FileAction.OPEN_IN_BROWSER,
                FileAction.RENAME,
                FileAction.DELETE,
            ],
        ),
        (
            "scenario",
            [
                FileAction.OPEN_WMS,
                FileAction.DOWNLOAD_RESULTS,
                FileAction.RENAME,
                FileAction.DELETE,
            ],
        ),
        (
            "other",
            [FileAction.OPEN_IN_BROWSER, FileAction.RENAME, FileAction.DELETE],
        ),
    ],
)
def test_get_file_actions(data_type, expected):
    assert get_file_actions(data_type) == expected


def test_get_folder_actions_excludes_delete_for_root():
    assert FileAction.DELETE not in get_folder_actions(is_root=True)
    assert FileAction.DELETE in get_folder_actions(is_root=False)
