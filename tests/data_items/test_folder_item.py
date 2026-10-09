from unittest.mock import MagicMock

import pytest
from qgis.core import Qgis, QgsDataItem
from qgis.PyQt.QtWidgets import QWidget

from rana_qgis_plugin.api_error_signals import ApiErrorSignals
from rana_qgis_plugin.data_items.file_actions import FileAction
from rana_qgis_plugin.data_items.folder_item import RanaFolderDataItem


@pytest.mark.parametrize("folder_path", ["", "nested/folder/"])
def test_add_schematisation_submenu_routes_with_folder_context(
    qgis_application, folder_path
):
    loader = MagicMock()
    project = {"id": "project"}
    browser_root = QgsDataItem(Qgis.BrowserItemType.Custom, None, "Rana", "Rana")
    parent = QWidget()
    item = RanaFolderDataItem(
        browser_root, loader, project, folder_path, "Files", ApiErrorSignals()
    )

    actions = item.actions(parent)
    add_action = next(
        action
        for action in actions
        if action.text() == FileAction.ADD_SCHEMATISATION.value
    )
    route_actions = add_action.menu().actions()

    assert [action.text() for action in route_actions] == [
        "Import from HCC",
        "Upload existing",
        "From scratch",
    ]

    for action in route_actions:
        action.trigger()

    loader.import_schematisation_from_hcc.assert_called_once_with(
        project, folder_path, parent
    )
    loader.upload_existing_schematisation.assert_called_once_with(
        project, folder_path, parent
    )
    loader.create_schematisation_from_scratch.assert_called_once_with(
        project, folder_path, parent
    )
