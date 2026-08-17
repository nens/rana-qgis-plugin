"""QgsDataItemGuiProvider for Rana browser item GUI actions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from qgis.core import QgsDataItem
from qgis.gui import QgsDataItemGuiContext, QgsDataItemGuiProvider

from rana_qgis_plugin.data_items.file_item import RanaFileDataItem
from rana_qgis_plugin.data_items.folder_item import (
    RanaFilesDataItem,
    RanaFolderDataItem,
)

if TYPE_CHECKING:
    from rana_qgis_plugin.loader import Loader


class RanaDataItemGuiProvider(QgsDataItemGuiProvider):
    """Handles GUI-level actions (rename) for Rana browser items."""

    def __init__(self, loader: Loader):
        super().__init__()
        self.loader = loader

    def name(self) -> str:
        return "Rana"

    def rename(
        self, item: QgsDataItem | None, name: str | None, context: QgsDataItemGuiContext
    ) -> bool:
        if isinstance(item, RanaFilesDataItem):
            return False
        if isinstance(item, RanaFolderDataItem):
            old_path = item.folder_path
            is_folder = True
        elif isinstance(item, RanaFileDataItem):
            old_path = item.file_item["id"]
            is_folder = False
        else:
            return False

        error = self.loader.rename_item(
            item.project["id"], old_path, name or "", is_folder
        )
        if error:
            self.notify("Rename failed", error, context)
            return False

        item.setName(name or "")
        parent = item.parent()
        if parent is not None:
            parent.refresh()
        return True
