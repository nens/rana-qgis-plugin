"""Keep layer-panel Rana references in sync with Browser renames/deletes."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from qgis.core import QgsProject

from rana_qgis_plugin.layer_management.layer_manager import (
    clear_rana_refs,
    get_rana_refs,
    set_rana_refs,
)

if TYPE_CHECKING:
    from rana_qgis_plugin.loader import Loader


class LocalLinkingListener:
    """Remap or clear Rana refs when items are renamed/deleted via the Browser."""

    def __init__(self, loader: "Loader") -> None:
        self.loader = loader

    def connect(self) -> None:
        self.loader.item_renamed.connect(self.on_item_renamed)
        self.loader.item_deleted.connect(self.on_item_deleted)

    def disconnect(self) -> None:
        self.loader.item_renamed.disconnect(self.on_item_renamed)
        self.loader.item_deleted.disconnect(self.on_item_deleted)

    def on_item_renamed(
        self, old_path: str, new_path: str, project_id: str, is_folder: bool
    ) -> None:
        """Remap stored file_id for layers whose path starts with *old_path*."""
        project = QgsProject.instance()
        if project is None:
            return
        for layer in project.mapLayers().values():
            ref = get_rana_refs(layer)
            if ref is None or ref.project_id != project_id:
                continue
            if is_folder:
                old_prefix = old_path.rstrip("/") + "/"
                new_prefix = new_path.rstrip("/") + "/"
                if ref.file_id.startswith(old_prefix) or ref.file_id == old_path.rstrip(
                    "/"
                ):
                    updated_id = new_prefix + ref.file_id[len(old_prefix) :]
                    set_rana_refs(layer, replace(ref, file_id=updated_id))
            else:
                if ref.file_id == old_path:
                    set_rana_refs(layer, replace(ref, file_id=new_path))

    def on_item_deleted(self, path: str, project_id: str, is_folder: bool) -> None:
        """Clear Rana refs for layers under the deleted path."""
        project = QgsProject.instance()
        if project is None:
            return
        for layer in project.mapLayers().values():
            ref = get_rana_refs(layer)
            if ref is None or ref.project_id != project_id:
                continue
            if is_folder:
                prefix = path.rstrip("/") + "/"
                if ref.file_id.startswith(prefix) or ref.file_id == path.rstrip("/"):
                    clear_rana_refs(layer)
            else:
                if ref.file_id == path:
                    clear_rana_refs(layer)
