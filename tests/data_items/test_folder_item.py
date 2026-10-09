from unittest.mock import MagicMock

import pytest
from qgis.core import Qgis, QgsDataItem
from qgis.PyQt.QtWidgets import QWidget

from rana_qgis_plugin.api_error_signals import ApiErrorSignals
from rana_qgis_plugin.data_items.file_actions import FileAction
from rana_qgis_plugin.data_items.folder_item import RanaFolderDataItem
from rana_qgis_plugin.icons import download_icon, new_icon, upload_icon


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

    route_actions[0].trigger()
    route_actions[1].trigger()
    route_actions[2].trigger()

    loader.import_schematisation_from_hcc.assert_called_once()
    hcc_call = loader.import_schematisation_from_hcc.call_args
    assert hcc_call.args == (project, folder_path, parent)
    assert callable(hcc_call.kwargs["refresh_callback"])
    for handler in (
        loader.upload_existing_schematisation,
        loader.create_schematisation_from_scratch,
    ):
        handler.assert_called_once()
        route_call = handler.call_args
        assert route_call.args == (project, folder_path, parent)
        assert callable(route_call.kwargs["refresh_callback"])
