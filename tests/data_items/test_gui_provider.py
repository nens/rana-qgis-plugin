from unittest.mock import Mock

import pytest
from qgis.PyQt.QtWidgets import QAction

from rana_qgis_plugin.data_items.file_actions import FileAction
from rana_qgis_plugin.data_items.file_item import RanaFileDataItem
from rana_qgis_plugin.data_items.folder_item import (
    RanaFilesDataItem,
    RanaFolderDataItem,
)
from rana_qgis_plugin.data_items.gui_provider import (
    SelectionKind,
    classify_selection,
    merge_multi_select_actions,
)
from rana_qgis_plugin.data_items.project_item import RanaProjectDataItem


def fake(cls):
    return Mock(spec=cls)


@pytest.mark.parametrize(
    "items, expected",
    [
        ([], SelectionKind.SINGLE),
        ([fake(RanaFileDataItem)], SelectionKind.SINGLE),
        (
            [fake(RanaFileDataItem), fake(RanaFolderDataItem)],
            SelectionKind.VALID_MULTI,
        ),
        (
            [fake(RanaFolderDataItem), fake(RanaFolderDataItem)],
            SelectionKind.VALID_MULTI,
        ),
        (
            [fake(RanaProjectDataItem), fake(RanaProjectDataItem)],
            SelectionKind.INVALID_MULTI,
        ),
        (
            [fake(RanaProjectDataItem), fake(RanaFileDataItem)],
            SelectionKind.INVALID_MULTI,
        ),
        (
            [fake(RanaFolderDataItem), fake(RanaFilesDataItem)],
            SelectionKind.INVALID_MULTI,
        ),
        (
            [fake(RanaFilesDataItem), fake(RanaFilesDataItem)],
            SelectionKind.INVALID_MULTI,
        ),
    ],
)
def test_classify_selection(items, expected):
    assert classify_selection(items) == expected


def test_merge_multi_select_actions_keeps_only_common_whitelisted(qgis_application):
    rename = QAction(FileAction.RENAME.value)
    delete = QAction(FileAction.DELETE.value)
    refresh = QAction(FileAction.REFRESH.value)
    primary_actions = [rename, delete, refresh]

    result = merge_multi_select_actions(
        primary_actions,
        per_item_action_texts=[
            {FileAction.RENAME.value, FileAction.DELETE.value},  # item A
            {FileAction.DELETE.value, FileAction.REFRESH.value},  # item B lacks RENAME
        ],
        whitelist=[FileAction.DELETE, FileAction.REFRESH],
    )

    # DELETE is common to both items AND whitelisted -> kept.
    # RENAME is whitelist-excluded here; REFRESH isn't common to both items.
    assert result == [delete]


def test_merge_multi_select_actions_empty_whitelist_keeps_nothing(qgis_application):
    primary_actions = [QAction(FileAction.DELETE.value)]

    result = merge_multi_select_actions(
        primary_actions,
        per_item_action_texts=[
            {FileAction.DELETE.value},
            {FileAction.DELETE.value},
        ],
        whitelist=[],
    )

    assert result == []


def test_merge_multi_select_actions_no_items_keeps_nothing(qgis_application):
    result = merge_multi_select_actions(
        [], per_item_action_texts=[], whitelist=[FileAction.DELETE]
    )

    assert result == []
