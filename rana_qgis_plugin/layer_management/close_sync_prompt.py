"""Warn about Rana-linked file changes before a QGIS project is cleared."""

from qgis.core import QgsLayerTreeGroup, QgsProject, QgsRasterLayer

from rana_qgis_plugin.layer_management.dirty_tracking import (
    is_data_dirty,
    is_style_dirty,
)
from rana_qgis_plugin.layer_management.layer_manager import is_rana_linked
from rana_qgis_plugin.layer_management.layer_tree_menu import LayerTreeMenuProvider

SYNC_NOW = "Sync now"
CONTINUE_WITHOUT_SYNCING = "Continue without syncing"


def collect_dirty_file_groups(
    root: QgsLayerTreeGroup,
) -> tuple[list[QgsLayerTreeGroup], list[QgsLayerTreeGroup]]:
    """Return file groups with unsynced style and vector-data changes."""
    style_groups = []
    data_groups = []
    for group in LayerTreeMenuProvider.file_groups([root]):
        layers = LayerTreeMenuProvider.collect_all_layers([group])
        rana_layers = [layer for layer in layers if is_rana_linked(layer)]
        if any(is_style_dirty(layer) for layer in rana_layers):
            style_groups.append(group)
        if any(
            not isinstance(layer, QgsRasterLayer) and is_data_dirty(layer)
            for layer in rana_layers
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

    def connect(self) -> None:
        """Show the prompt before the project clears its layer tree."""
        self.project.aboutToBeCleared.connect(self.on_project_about_to_be_cleared)

    def disconnect(self) -> None:
        """Stop showing project-clear prompts."""
        self.project.aboutToBeCleared.disconnect(self.on_project_about_to_be_cleared)

    def on_project_about_to_be_cleared(self) -> None:
        """Ask about syncing dirty file groups and dispatch existing syncs."""
        root = self.project.layerTreeRoot()
        assert root is not None
        style_groups, data_groups = collect_dirty_file_groups(root)
        if not style_groups and not data_groups:
            return

        groups = []
        seen_groups = set()
        for group in style_groups + data_groups:
            if id(group) not in seen_groups:
                groups.append(group)
                seen_groups.add(id(group))
        names = "\n".join(f"• {group.name()}" for group in groups)
        question = (
            "The following files have changes not yet synced to Rana:\n\n"
            f"{names}\n\n"
            "Sync them now, or continue without syncing?"
        )
        answer = self.communication.custom_ask(
            self.parent,
            "Unsynced changes",
            question,
            SYNC_NOW,
            CONTINUE_WITHOUT_SYNCING,
        )

        if answer == SYNC_NOW:
            if style_groups:
                self.layer_tree_menu.save_style(style_groups)
            if data_groups:
                self.layer_tree_menu.save_data(data_groups)
