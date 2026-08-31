"""Rana context-menu entries for the QGIS layer-tree panel."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

from qgis.core import QgsLayerTreeGroup, QgsLayerTreeLayer, QgsMapLayer, QgsRasterLayer
from qgis.PyQt.QtWidgets import QAction, QMenu

from rana_qgis_plugin.icons import rana_icon
from rana_qgis_plugin.layer_management.dirty_tracking import (
    is_data_dirty,
    is_style_dirty,
)
from rana_qgis_plugin.layer_management.layer_manager import (
    _GROUP_SCHEMATISATION_ID_KEY,
    RanaLayerRef,
    get_rana_refs,
    is_rana_linked,
)
from rana_qgis_plugin.layer_management.sync_lock import LayerLockRegistry
from rana_qgis_plugin.utils.data_models import (
    DataType,
    StyleUploadItem,
    UploadableLayerItem,
)
from rana_qgis_plugin.workers.styling import make_file_style_upload_item

if TYPE_CHECKING:
    from qgis.gui import QgisInterface

_GROUP_PROJECT_ID_KEY = "rana/project_id"
_GROUP_LOADING_KEY = "rana/loading"


class LayerTreeMenuProvider:
    """Adds Rana sync actions to the layer-tree panel context menu.

    Connected to ``iface.layerTreeView().contextMenuAboutToShow``.
    Actions appear on any Rana-tagged group node (project, files, folder,
    or file level). Individual layer nodes do not receive Rana actions.
    """

    def __init__(
        self,
        iface: "QgisInterface",
        layer_lock_registry: LayerLockRegistry,
        loader=None,
    ) -> None:
        self.iface = iface
        self.layer_lock_registry = layer_lock_registry
        self.loader = loader

    def connect(self) -> None:
        view = self.iface.layerTreeView()
        if view is not None:
            view.contextMenuAboutToShow.connect(self.on_context_menu)

    def disconnect(self) -> None:
        view = self.iface.layerTreeView()
        if view is not None:
            view.contextMenuAboutToShow.disconnect(self.on_context_menu)

    def on_context_menu(self, menu: QMenu) -> None:
        """Append Rana sync actions to group nodes in the layer-tree context menu."""
        view = self.iface.layerTreeView()
        if view is None:
            return

        node = view.currentNode()
        if not isinstance(node, QgsLayerTreeGroup):
            return

        if node.customProperty(_GROUP_SCHEMATISATION_ID_KEY) is not None:
            separator = QAction(menu)
            separator.setSeparator(True)
            menu.addAction(separator)
            save_revision = QAction(rana_icon, "Save revision", menu)
            save_revision.setEnabled(
                not bool(node.customProperty(_GROUP_LOADING_KEY, False))
            )
            save_revision.triggered.connect(lambda: self.save_revision([node]))
            menu.addAction(save_revision)
            return

        if not self._is_rana_group(node):
            return

        separator = QAction(menu)
        separator.setSeparator(True)
        menu.addAction(separator)

        ref = self.get_group_rana_ref(node)
        if ref is None:
            return
        locked = self.layer_lock_registry.is_locked(
            (ref.project_id, ref.descriptor_id or ref.file_id)
        )

        is_file_group = any(
            isinstance(child, QgsLayerTreeLayer) for child in node.children()
        )
        style_label = "Save style to Rana" if is_file_group else "Save styles to Rana"

        save_style = QAction(rana_icon, style_label, menu)
        all_layers = self._collect_all_layers([node])
        style_dirty = any(is_style_dirty(layer) for layer in all_layers)
        data_dirty = any(
            isinstance(layer, QgsRasterLayer) or is_data_dirty(layer)
            for layer in all_layers
        )
        if locked or not style_dirty:
            save_style.setEnabled(False)
        else:
            save_style.triggered.connect(lambda: self.save_style([node]))
        menu.addAction(save_style)

        save_data = QAction(rana_icon, "Save data to Rana", menu)
        if locked or not data_dirty:
            save_data.setEnabled(False)
        else:
            save_data.triggered.connect(lambda: self.save_data([node]))
        menu.addAction(save_data)

    def save_style(self, groups: list[QgsLayerTreeGroup]) -> None:
        """Collect file-level style inputs and delegate them to Loader."""
        if self.loader is None:
            return
        items: list[StyleUploadItem] = []
        seen: set[tuple[str, str]] = set()
        for group, ref, layer in self.iterate_file_groups(groups):
            if ref is None or not ref.descriptor_id:
                continue
            key = (ref.project_id, ref.descriptor_id)
            if key in seen:
                continue
            data_type = (
                DataType.raster
                if isinstance(layer, QgsRasterLayer)
                else DataType.vector
            )
            items.append(
                make_file_style_upload_item(
                    ref.descriptor_id,
                    data_type,
                    layer.source().split("|", 1)[0],
                    f"file {ref.file_id}",
                    project_id=ref.project_id,
                )
            )
            seen.add(key)
        self.loader.upload_styles(items)

    def save_data(self, groups: list[QgsLayerTreeGroup]) -> None:
        """Collect linked files and delegate upload orchestration to Loader."""
        if self.loader is None:
            return
        items = []
        seen: set[tuple[str, str]] = set()
        for group, ref, layer in self.iterate_file_groups(groups):
            if ref is None:
                continue
            key = (ref.project_id, ref.descriptor_id or ref.file_id)
            if key in seen:
                continue
            items.append(
                UploadableLayerItem(
                    ref,
                    Path(layer.source().split("|", 1)[0]),
                    layer.name(),
                    ref.project_id,
                )
            )
            seen.add(key)
        self.loader.upload_existing_files(items)

    def save_revision(self, groups: list[QgsLayerTreeGroup]) -> None:
        """Show the placeholder until revision upload is implemented."""
        if self.loader is not None:
            self.loader.communication.bar_info("Save revision not yet implemented")

    @staticmethod
    def file_groups(groups: list[QgsLayerTreeGroup]) -> list[QgsLayerTreeGroup]:
        """Return file-level descendants, excluding folder-only groups."""
        result = []
        for group in groups:
            if any(isinstance(child, QgsLayerTreeLayer) for child in group.children()):
                result.append(group)
            for child in group.children():
                if isinstance(child, QgsLayerTreeGroup):
                    result.extend(LayerTreeMenuProvider.file_groups([child]))
        return [
            item
            for nested in result
            for item in (nested if isinstance(nested, list) else [nested])
        ]

    @staticmethod
    def _collect_all_layers(groups: list[QgsLayerTreeGroup]) -> list[QgsMapLayer]:
        """Return every map layer under the given groups (recursive)."""
        layers: list[QgsMapLayer] = []
        for group in groups:
            for child in group.children():
                if isinstance(child, QgsLayerTreeLayer):
                    layer = child.layer()
                    if layer is not None:
                        layers.append(layer)
                elif isinstance(child, QgsLayerTreeGroup):
                    layers.extend(LayerTreeMenuProvider._collect_all_layers([child]))
        return layers

    def _is_rana_group(self, group: QgsLayerTreeGroup) -> bool:
        """Return whether a group node was created by the Rana layer opener."""
        return group.customProperty(_GROUP_PROJECT_ID_KEY) is not None

    @staticmethod
    def get_first_layer_from_group(group: QgsLayerTreeGroup) -> QgsMapLayer | None:
        """Return the first layer directly contained in a file group."""
        for child in group.children():
            if isinstance(child, QgsLayerTreeLayer) and child.layer() is not None:
                return child.layer()
        return None

    @staticmethod
    def iterate_file_groups(
        groups: list[QgsLayerTreeGroup],
    ) -> Iterator[tuple[QgsLayerTreeGroup, RanaLayerRef, QgsMapLayer]]:
        """Yield file groups with their Rana reference and backing layer."""
        for group in LayerTreeMenuProvider.file_groups(groups):
            ref = LayerTreeMenuProvider.get_group_rana_ref(group)
            layer = LayerTreeMenuProvider.get_first_layer_from_group(group)
            if ref is not None and layer is not None:
                yield group, ref, layer

    @staticmethod
    def get_group_rana_ref(group: QgsLayerTreeGroup) -> RanaLayerRef | None:
        """Return the RanaLayerRef from the first rana-linked child layer."""
        for child in group.children():
            if isinstance(child, QgsLayerTreeLayer):
                layer = child.layer()
                if layer is not None and is_rana_linked(layer):
                    return get_rana_refs(layer)
            elif isinstance(child, QgsLayerTreeGroup):
                ref = LayerTreeMenuProvider.get_group_rana_ref(child)
                if ref is not None:
                    return ref
        return None
