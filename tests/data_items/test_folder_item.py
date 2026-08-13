from unittest.mock import MagicMock, patch

import pytest
from qgis.core import Qgis, QgsDataItem
from qgis.PyQt.QtWidgets import QAction

from rana_qgis_plugin.data_items.file_actions import FileAction
from rana_qgis_plugin.data_items.folder_item import RanaFolderDataItem


class ParentItem(QgsDataItem):
    def __init__(self):
        super().__init__(
            Qgis.BrowserItemType.Collection, None, "Project", "project", "Rana"
        )
        self.loader = MagicMock()


@pytest.mark.parametrize("folder_path", ["", "folder/subfolder"])
def test_upload_action_passes_folder_context(folder_path, qapp):
    action_parent = qapp.activeWindow()
    parent = ParentItem()
    folder = RanaFolderDataItem(
        parent, parent.loader, "project-id", folder_path, "Folder", MagicMock()
    )
    actions = folder.actions(action_parent)
    upload_action = next(
        action
        for action in actions
        if isinstance(action, QAction)
        and action.text() == FileAction.UPLOAD_FILES.value
    )
    upload_action.trigger()

    parent.loader.upload_files.assert_called_once_with(
        {"id": "project-id"},
        folder_path,
        action_parent,
        refresh_callback=folder.refresh_if_populated,
    )


@pytest.mark.parametrize("populate", [True, False])
def test_refresh_if_populated(qapp, populate):
    parent = ParentItem()
    folder = RanaFolderDataItem(
        parent, parent.loader, "project-id", "folder", "Folder", MagicMock()
    )
    if populate:
        folder.setState(Qgis.BrowserItemState.Populated)
    with patch.object(folder, "refresh") as refresh:
        folder.refresh_if_populated()
    if populate:
        refresh.assert_called_once_with()
    else:
        refresh.assert_not_called()
