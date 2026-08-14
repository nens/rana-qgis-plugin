"""QgsDataItemGuiProvider for Rana browser item GUI actions."""

from __future__ import annotations

import logging

from qgis.core import QgsDataItem
from qgis.gui import QgsDataItemGuiContext, QgsDataItemGuiProvider

from rana_qgis_plugin.data_items.file_item import RanaFileDataItem
from rana_qgis_plugin.data_items.folder_item import (
    RanaFilesDataItem,
    RanaFolderDataItem,
)

logger = logging.getLogger(__name__)

RENAMABLE_TYPES = (RanaFolderDataItem, RanaFileDataItem)


class RanaDataItemGuiProvider(QgsDataItemGuiProvider):
    """Handles GUI-level actions (rename) for Rana browser items."""

    def name(self) -> str:
        return "Rana"

    def rename(
        self, item: QgsDataItem | None, name: str | None, context: QgsDataItemGuiContext
    ) -> bool:
        if isinstance(item, RanaFilesDataItem):
            return False
        if not isinstance(item, RENAMABLE_TYPES):
            return False
        logger.warning(
            "SPIKE: rename() called for %s with new name: %s", item.name(), name
        )
        return False
