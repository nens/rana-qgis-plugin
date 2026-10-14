"""Find Rana-linked file groups with changes that have not been synced."""

from qgis.core import QgsLayerTreeGroup, QgsRasterLayer

from rana_qgis_plugin.layer_management.dirty_tracking import (
    is_data_dirty,
    is_style_dirty,
)
from rana_qgis_plugin.layer_management.layer_manager import is_rana_linked
from rana_qgis_plugin.layer_management.layer_tree_menu import LayerTreeMenuProvider


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
