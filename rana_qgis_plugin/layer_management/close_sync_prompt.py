"""Warn about Rana-linked file changes before a QGIS project is cleared."""

import html

from qgis.core import (
    QgsLayerTreeGroup,
    QgsLayerTreeLayer,
    QgsLayerTreeNode,
    QgsMapLayer,
    QgsProject,
)
from qgis.PyQt.QtCore import QTimer

from rana_qgis_plugin.layer_management.dirty_state import (
    DataDirtyState,
    data_dirty_state,
    has_unsynced_style,
    should_badge,
)
from rana_qgis_plugin.layer_management.layer_tree_menu import LayerTreeMenuProvider
from rana_qgis_plugin.utils.data_models import StyleUploadItem, UploadableLayerItem
from rana_qgis_plugin.workers.styling import discard_layer_sources

SYNC_NOW = "Sync now"
CONTINUE_WITHOUT_SYNCING = "Continue without syncing"


def collect_dirty_file_groups(
    root: QgsLayerTreeGroup,
    layer_ids: set[str] | None = None,
) -> tuple[list[QgsLayerTreeGroup], list[QgsLayerTreeGroup]]:
    """Return dirty file groups, optionally restricted to layer IDs."""
    style_groups = []
    data_groups = []
    for group in LayerTreeMenuProvider.file_groups([root]):
        layers = LayerTreeMenuProvider.collect_all_layers([group])
        rana_layers = [
            layer for layer in layers if layer_ids is None or layer.id() in layer_ids
        ]
        if any(has_unsynced_style(layer) for layer in rana_layers):
            style_groups.append(group)
        if any(
            data_dirty_state(layer) is DataDirtyState.DIRTY for layer in rana_layers
        ):
            data_groups.append(group)
    return style_groups, data_groups


class CloseSyncPrompt:
    """Prompt and optionally start existing syncs before project clearing."""

    def __init__(
        self,
        project: QgsProject,
        layer_tree_menu: LayerTreeMenuProvider,
        communication,
        parent=None,
    ):
        self.project = project
        self.layer_tree_menu = layer_tree_menu
        self.communication = communication
        self.parent = parent
        self._project_clear_in_progress = False
        self._prompted_layer_ids: set[str] = set()
        self._pending_style_names: list[str] = []
        self._pending_data_names: list[str] = []
        self._pending_style_items: list[StyleUploadItem] = []
        self._pending_data_items: list[UploadableLayerItem] = []
        self._flush_scheduled = False

    def connect(self) -> None:
        """Show prompts before dirty layers or the project are removed."""
        self.project.aboutToBeCleared.connect(self.on_project_about_to_be_cleared)
        self.project.cleared.connect(self.on_project_cleared)
        self.project.layersWillBeRemoved.connect(self.on_layers_will_be_removed)
        self.project.layersRemoved.connect(self.on_layers_removed)
        root = self.project.layerTreeRoot()
        assert root is not None
        root.willRemoveChildren.connect(self.on_will_remove_children)
        root.removedChildren.connect(self.on_removed_children)

    def disconnect(self) -> None:
        """Stop showing layer-removal and project-clear prompts."""
        self.project.aboutToBeCleared.disconnect(self.on_project_about_to_be_cleared)
        self.project.cleared.disconnect(self.on_project_cleared)
        self.project.layersWillBeRemoved.disconnect(self.on_layers_will_be_removed)
        self.project.layersRemoved.disconnect(self.on_layers_removed)
        root = self.project.layerTreeRoot()
        assert root is not None
        root.willRemoveChildren.disconnect(self.on_will_remove_children)
        root.removedChildren.disconnect(self.on_removed_children)

    def on_project_about_to_be_cleared(self) -> None:
        """Ask about syncing dirty file groups and dispatch existing syncs."""
        self._project_clear_in_progress = True
        root = self.project.layerTreeRoot()
        assert root is not None
        style_groups, data_groups = collect_dirty_file_groups(root)
        if not style_groups and not data_groups:
            return

        self.prompt_to_sync_groups(style_groups, data_groups)

    def on_project_cleared(self) -> None:
        """Reset removal deduplication after QGIS finishes clearing the project."""
        self._project_clear_in_progress = False
        self._prompted_layer_ids.clear()

    def on_layers_removed(self, removed_layers: list) -> None:
        """Release layer IDs after QGIS completes their project removal."""
        self._prompted_layer_ids.difference_update(self.layer_ids(removed_layers))

    def on_layers_will_be_removed(self, removed_layers: list) -> None:
        """Prompt once for dirty file groups represented by removed layers."""
        if self._project_clear_in_progress:
            return
        layer_ids = self.layer_ids(removed_layers)
        pending_ids = set(layer_ids) - self._prompted_layer_ids
        if pending_ids:
            self.prompt_for_layer_ids(pending_ids)

    def on_will_remove_children(
        self, parent: QgsLayerTreeNode, index_from: int, index_to: int
    ) -> None:
        """Handle tree-driven layer/group removal while nodes are still attached."""
        if self._project_clear_in_progress:
            return
        project_root = self.project.layerTreeRoot()
        assert project_root is not None

        # Removing a non-empty group detaches it first, then QGIS emits child
        # removal notifications while destroying the detached group. Scan the
        # detached subtree on its first notification so all dirty children are
        # collected into one prompt.
        if isinstance(parent, QgsLayerTreeGroup) and parent is not project_root:
            if parent.parent() is None:
                layer_ids = self.layer_ids_in_subtree(parent) - self._prompted_layer_ids
                if layer_ids:
                    self.queue_prompt_for_layer_ids(layer_ids, scan_root=parent)
                return

        layer_ids = set()
        removed_children = parent.children()[index_from : index_to + 1]
        for child in removed_children:
            layer_ids.update(self.layer_ids_in_subtree(child))

        # A file group contains sibling layer nodes from the same remote file.
        # If a dirty child is removed, include its dirty siblings in the same
        # prompt so a multi-layer file is handled in one sync decision.
        removed_dirty_layer = False
        for child in removed_children:
            if not isinstance(child, QgsLayerTreeLayer):
                continue
            layer = child.layer()
            if layer is not None and should_badge(layer):
                removed_dirty_layer = True
                break
        if isinstance(parent, QgsLayerTreeGroup) and removed_dirty_layer:
            layer_ids.update(self.layer_ids_in_subtree(parent))

        pending_ids = layer_ids - self._prompted_layer_ids
        if pending_ids:
            root = self.project.layerTreeRoot()
            assert root is not None
            self.queue_prompt_for_layer_ids(pending_ids, scan_root=root)

    def find_dirty_groups(
        self, layer_ids: set[str], root: QgsLayerTreeGroup
    ) -> tuple[list[QgsLayerTreeGroup], list[QgsLayerTreeGroup]]:
        """Return dirty file groups among the given layer IDs, marking them prompted."""
        dirty_ids: set[str] = set()
        for group in LayerTreeMenuProvider.file_groups([root]):
            layers = LayerTreeMenuProvider.collect_all_layers([group])
            linked_dirty_layers = [layer for layer in layers if should_badge(layer)]
            if layer_ids.intersection(layer.id() for layer in linked_dirty_layers):
                dirty_ids.update(layer.id() for layer in linked_dirty_layers)
        if not dirty_ids:
            return [], []
        style_groups, data_groups = collect_dirty_file_groups(root, dirty_ids)
        if not style_groups and not data_groups:
            return [], []
        prompted_group_ids = set(style_groups + data_groups)
        self._prompted_layer_ids.update(
            layer.id()
            for layer in LayerTreeMenuProvider.collect_all_layers(
                list(prompted_group_ids)
            )
            if should_badge(layer)
        )
        return style_groups, data_groups

    def prompt_for_layer_ids(
        self, layer_ids: set[str], scan_root: QgsLayerTreeGroup | None = None
    ) -> None:
        """Find and prompt once for dirty groups among the specified layers."""
        root = scan_root or self.project.layerTreeRoot()
        assert root is not None
        style_groups, data_groups = self.find_dirty_groups(layer_ids, root)
        if not style_groups and not data_groups:
            return
        self.prompt_to_sync_groups(style_groups, data_groups)

    def queue_prompt_for_layer_ids(
        self, layer_ids: set[str], scan_root: QgsLayerTreeGroup | None = None
    ) -> None:
        """Capture dirty-group sync inputs now, then flush one prompt later.

        Tree-driven removal of a group tears it down bottom-up, one node at a
        time, emitting a separate ``willRemoveChildren`` for every sibling file
        group along the way. Each node is still fully live at the moment its
        own notification fires, but by the time a later sibling's notification
        arrives, earlier siblings may already be destroyed. So upload inputs
        are extracted into plain data immediately (while each group is live)
        and accumulated; only the prompt display and dispatch are deferred
        (via a zero-delay timer) until the whole removal cascade has finished
        emitting, so all affected files are covered by a single prompt.
        """
        root = scan_root or self.project.layerTreeRoot()
        assert root is not None
        style_groups, data_groups = self.find_dirty_groups(layer_ids, root)
        if not style_groups and not data_groups:
            return
        for group in style_groups:
            if group.name() not in self._pending_style_names:
                self._pending_style_names.append(group.name())
        for group in data_groups:
            if group.name() not in self._pending_data_names:
                self._pending_data_names.append(group.name())
        if style_groups:
            self._pending_style_items.extend(
                self.layer_tree_menu.capture_style_items(style_groups, for_close=True)
            )
        if data_groups:
            self._pending_data_items.extend(
                self.layer_tree_menu.capture_data_items(data_groups)
            )
        if not self._flush_scheduled:
            self._flush_scheduled = True
            QTimer.singleShot(0, self._flush_pending_prompt)

    def _flush_pending_prompt(self) -> None:
        """Show one prompt for all dirty groups captured since the last flush."""
        self._flush_scheduled = False
        style_names = self._pending_style_names
        data_names = self._pending_data_names
        style_items = self._pending_style_items
        data_items = self._pending_data_items
        self._pending_style_names = []
        self._pending_data_names = []
        self._pending_style_items = []
        self._pending_data_items = []
        self.prompt_and_dispatch(style_names, data_names, style_items, data_items)

    def prompt_and_dispatch(
        self,
        style_names: list[str],
        data_names: list[str],
        style_items: list[StyleUploadItem],
        data_items: list[UploadableLayerItem],
    ) -> None:
        """Ask whether to sync the captured items, releasing them if not."""
        if not style_names and not data_names:
            discard_layer_sources(style_items)
            return
        answer = self.communication.custom_ask(
            self.parent,
            "Unsynced changes",
            self.build_question(style_names, data_names),
            SYNC_NOW,
            CONTINUE_WITHOUT_SYNCING,
        )
        if answer != SYNC_NOW:
            discard_layer_sources(style_items)
            return
        if style_items:
            self.layer_tree_menu.dispatch_style_items(style_items)
        if data_items:
            self.layer_tree_menu.dispatch_data_items(data_items)

    @staticmethod
    def layer_ids_in_subtree(node: QgsLayerTreeNode) -> set[str]:
        """Return layer IDs nested under a layer or group tree node."""
        if isinstance(node, QgsLayerTreeLayer):
            layer = node.layer()
            return {layer.id()} if layer is not None else set()
        if isinstance(node, QgsLayerTreeGroup):
            return {
                layer_id
                for child in node.children()
                for layer_id in CloseSyncPrompt.layer_ids_in_subtree(child)
            }
        return set()

    def on_removed_children(
        self, parent: QgsLayerTreeNode, index_from: int, index_to: int
    ) -> None:
        """Release IDs after tree-only removal if registry removal won't follow."""
        if not isinstance(parent, QgsLayerTreeGroup):
            return
        removed_ids = set()
        for child in parent.children()[index_from : index_to + 1]:
            removed_ids.update(self.layer_ids_in_subtree(child))
        if removed_ids:
            QTimer.singleShot(
                0,
                lambda ids=removed_ids: self.clear_tree_only_prompted_ids(ids),
            )

    def clear_tree_only_prompted_ids(self, layer_ids: set[str]) -> None:
        """Clear dedupe IDs only for layers still registered after tree removal."""
        registered_ids = set(self.project.mapLayers())
        self._prompted_layer_ids.difference_update(layer_ids & registered_ids)

    @staticmethod
    def layer_ids(removed_layers: list) -> set[str]:
        """Normalize either project removal-signal overload to layer IDs."""
        return {
            layer.id() if isinstance(layer, QgsMapLayer) else layer
            for layer in removed_layers
        }

    def prompt_to_sync_groups(
        self,
        style_groups: list[QgsLayerTreeGroup],
        data_groups: list[QgsLayerTreeGroup],
    ) -> None:
        """Ask whether to dispatch the existing sync actions for these groups.

        Styles are snapshotted before prompting: the layers are still alive in
        this handler, but the upload task only runs once the project has been
        cleared, by which point they are gone.
        """
        style_items = (
            self.layer_tree_menu.capture_style_items(style_groups, for_close=True)
            if style_groups
            else []
        )
        data_items = (
            self.layer_tree_menu.capture_data_items(data_groups) if data_groups else []
        )
        self.prompt_and_dispatch(
            [group.name() for group in style_groups],
            [group.name() for group in data_groups],
            style_items,
            data_items,
        )

    @staticmethod
    def describe_changes(has_style: bool, has_data: bool, single_file: bool) -> str:
        """Name the kinds of change being reported.

        For one file both flags describe that same file, so they can be stated
        as fact. Across several files the flags may come from different files,
        so "and/or" avoids claiming every file changed in both ways.
        """
        if has_style and has_data:
            return "data and style" if single_file else "data and/or style"
        return "style" if has_style else "data"

    @staticmethod
    def build_question(style_names: list[str], data_names: list[str]) -> str:
        """Build the sync-prompt question text listing the given file names.

        The dialog renders this as rich text, so plain newlines/bullets do not
        produce a visible list; HTML markup is required. The phrasing and
        shape also depend on how many files are involved: a single file is
        named inline, 2-10 files are shown as a bullet list, and 11+ files
        show the first 10 plus an "...and N more files" summary line.

        Names are sorted alphabetically rather than by layer-tree position:
        tree-driven removal fires bottom-up across multiple deferred signals,
        so the original visual order isn't reliably reconstructable once
        several files are captured across that cascade.
        """
        names = sorted(set(style_names) | set(data_names), key=str.casefold)
        changes = CloseSyncPrompt.describe_changes(
            bool(style_names), bool(data_names), len(names) == 1
        )
        if len(names) == 1:
            return (
                f"<b>{html.escape(names[0])}</b> has unsynced {changes} changes."
                "<br><br>Sync it now, or continue without syncing?"
            )
        shown = names[:10]
        items = "".join(f"<li>{html.escape(name)}</li>" for name in shown)
        if len(names) > 10:
            items += f"<li>…and {len(names) - 10} more files</li>"
        return (
            f"The following files have unsynced {changes} changes:"
            f"<ul>{items}</ul>"
            "Sync them now, or continue without syncing?"
        )
