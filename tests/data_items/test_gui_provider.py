from unittest.mock import Mock

import pytest

from rana_qgis_plugin.data_items.file_item import RanaFileDataItem
from rana_qgis_plugin.data_items.folder_item import (
    RanaFilesDataItem,
    RanaFolderDataItem,
)
from rana_qgis_plugin.data_items.gui_provider import SelectionKind, classify_selection
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
