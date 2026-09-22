from unittest.mock import MagicMock, Mock

import pytest
from qgis.PyQt.QtWidgets import QAction, QMenu

from rana_qgis_plugin.data_items.file_actions import FileAction
from rana_qgis_plugin.data_items.file_item import RanaFileDataItem
from rana_qgis_plugin.data_items.folder_item import (
    RanaFilesDataItem,
    RanaFolderDataItem,
)
from rana_qgis_plugin.data_items.gui_provider import (
    RanaDataItemGuiProvider,
    SelectionKind,
    classify_selection,
    merge_multi_select_actions,
)
from rana_qgis_plugin.data_items.project_item import RanaProjectDataItem
from rana_qgis_plugin.utils.data_models import (
    OpenScenarioRequest,
    OpenScenarioWmsRequest,
)


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


def test_open_selected_items_includes_scenarios_in_batch():
    loader = MagicMock()
    project = {"id": "project", "name": "Project", "slug": "project"}
    scenario_files = [
        {"id": "scenario-1.json", "descriptor_id": "descriptor-1"},
        {"id": "scenario-2.json", "descriptor_id": "descriptor-2"},
    ]
    items = []
    for file_item in scenario_files:
        item = Mock(spec=RanaFileDataItem)
        item.data_type = "scenario"
        item.project = project
        item.file_item = file_item
        item.loader = loader
        items.append(item)

    RanaDataItemGuiProvider.open_selected_items(items)

    loader.open_items.assert_called_once_with(
        [OpenScenarioRequest(project, file_item) for file_item in scenario_files]
    )


def test_open_selected_wms_dispatches_scenario_requests():
    loader = MagicMock()
    project = {"id": "project", "name": "Project"}
    scenario_files = [
        {"id": "scenario-1", "descriptor_id": "descriptor-1"},
        {"id": "scenario-2", "descriptor_id": "descriptor-2"},
    ]
    items = []
    for file_item in scenario_files:
        item = Mock(spec=RanaFileDataItem)
        item.data_type = "scenario"
        item.project = project
        item.file_item = file_item
        item.loader = loader
        items.append(item)

    RanaDataItemGuiProvider.open_selected_wms(items)

    loader.open_scenario_wms_batch.assert_called_once_with(
        [OpenScenarioWmsRequest(project, file_item) for file_item in scenario_files]
    )


def test_multi_select_menu_keeps_open_in_qgis_for_scenarios(qgis_application):
    menu = QMenu()
    first = Mock(spec=RanaFileDataItem)
    second = Mock(spec=RanaFileDataItem)
    for item in (first, second):
        item.data_type = "scenario"
        item.actions.return_value = [QAction(FileAction.OPEN_IN_QGIS.value)]

    provider = RanaDataItemGuiProvider()
    provider.populateContextMenu(first, menu, [first, second], MagicMock())

    assert [action.text() for action in menu.actions()] == [
        FileAction.OPEN_IN_QGIS.value
    ]


def test_multi_select_menu_keeps_open_wms_for_scenarios(qgis_application):
    menu = QMenu()
    first = Mock(spec=RanaFileDataItem)
    second = Mock(spec=RanaFileDataItem)
    for item in (first, second):
        item.data_type = "scenario"
        item.actions.return_value = [QAction(FileAction.OPEN_WMS.value)]

    provider = RanaDataItemGuiProvider()
    provider.populateContextMenu(first, menu, [first, second], MagicMock())

    assert [action.text() for action in menu.actions()] == [FileAction.OPEN_WMS.value]
