"""Show dirty-state indicators on Rana-linked layer tree items."""

from collections.abc import Callable

from qgis.core import (
    QgsApplication,
    QgsLayerTreeGroup,
    QgsLayerTreeLayer,
    QgsLayerTreeNode,
    QgsMapLayer,
    QgsProject,
)
from qgis.gui import QgsLayerTreeView, QgsLayerTreeViewIndicator

from rana_qgis_plugin.layer_management.dirty_tracking import (
    DATA_DIRTY_PROPERTY,
    STYLE_DIRTY_PROPERTY,
    is_data_dirty,
    is_style_dirty,
)
from rana_qgis_plugin.layer_management.layer_manager import is_rana_linked

_INDICATOR_TOOLTIP = "Has unsynced changes to Rana"


class IndicatorManager:
    """Attach an indicator to Rana-linked layers when they become dirty."""

    def __init__(self, project: QgsProject, layer_tree_view: QgsLayerTreeView):
        self.project = project
        self.layer_tree_view = layer_tree_view
        self._tracked_layers: dict[str, tuple[QgsMapLayer, Callable[[str], None]]] = {}
        self._indicators: list[tuple[QgsLayerTreeNode, QgsLayerTreeViewIndicator]] = []

    def connect(self) -> None:
        """Start tracking layers added to the project."""
        self.project.layersAdded.connect(self.track_layers)
        root = self.project.layerTreeRoot()
        assert root is not None
        root.willRemoveChildren.connect(self.on_will_remove_children)
        root.removedChildren.connect(self.on_removed_children)

    def disconnect(self) -> None:
        """Stop tracking project and layer signals."""
        self.project.layersAdded.disconnect(self.track_layers)
        root = self.project.layerTreeRoot()
        assert root is not None
        root.willRemoveChildren.disconnect(self.on_will_remove_children)
        root.removedChildren.disconnect(self.on_removed_children)
        for layer, property_slot in self._tracked_layers.values():
            layer.customPropertyChanged.disconnect(property_slot)
        self._tracked_layers.clear()
        root = self.project.layerTreeRoot()
        assert root is not None
        self.remove_subtree_indicators(root)

    def track_layers(self, layers: list[QgsMapLayer]) -> None:
        """Watch dirty-state custom properties on newly added Rana layers."""
        for layer in layers:
            if not is_rana_linked(layer) or layer.id() in self._tracked_layers:
                continue
            property_slot = lambda key, target=layer: self.on_custom_property_changed(
                target, key
            )
            layer.customPropertyChanged.connect(property_slot)
            self._tracked_layers[layer.id()] = (layer, property_slot)

    def on_custom_property_changed(self, layer: QgsMapLayer, key: str) -> None:
        """Refresh the layer badge when either Rana dirty property changes."""
        if key in {DATA_DIRTY_PROPERTY, STYLE_DIRTY_PROPERTY}:
            self.update_layer(layer)

    def update_layer(self, layer: QgsMapLayer) -> None:
        """Refresh a layer indicator and its ancestor group indicators."""
        layer_id = layer.id()
        is_dirty = is_data_dirty(layer) or is_style_dirty(layer)
        root = self.project.layerTreeRoot()
        assert root is not None
        node = root.findLayer(layer_id)
        if node is None:
            return
        self.set_indicator(node, is_dirty)
        parent = node.parent()
        while isinstance(parent, QgsLayerTreeGroup):
            self.update_group(parent)
            parent = parent.parent()

    def update_group(self, group: QgsLayerTreeGroup) -> None:
        """Set a group indicator if any linked descendant layer is dirty."""
        is_dirty = False
        for layer_node in self.descendant_layers(group):
            layer = layer_node.layer()
            if (
                layer is not None
                and is_rana_linked(layer)
                and (is_data_dirty(layer) or is_style_dirty(layer))
            ):
                is_dirty = True
                break
        self.set_indicator(group, is_dirty)

    @staticmethod
    def descendant_layers(group: QgsLayerTreeGroup) -> list[QgsLayerTreeLayer]:
        """Return all layer nodes nested under a group."""
        layer_nodes = []
        for child in group.children():
            if isinstance(child, QgsLayerTreeLayer):
                layer_nodes.append(child)
            elif isinstance(child, QgsLayerTreeGroup):
                layer_nodes.extend(IndicatorManager.descendant_layers(child))
        return layer_nodes

    def set_indicator(self, node: QgsLayerTreeNode, is_dirty: bool) -> None:
        """Attach or detach the managed indicator on one tree node."""
        indicator = self.managed_indicator(node)
        if is_dirty and indicator is None:
            indicator = QgsLayerTreeViewIndicator(self.layer_tree_view)
            indicator.setIcon(QgsApplication.getThemeIcon("/mIconWarning.svg"))
            indicator.setToolTip(_INDICATOR_TOOLTIP)
            self.layer_tree_view.addIndicator(node, indicator)
            self._indicators.append((node, indicator))
        elif not is_dirty and indicator is not None:
            self.layer_tree_view.removeIndicator(node, indicator)
            indicator.deleteLater()
            self._indicators = [
                entry for entry in self._indicators if entry[1] != indicator
            ]

    def managed_indicator(
        self, node: QgsLayerTreeNode
    ) -> QgsLayerTreeViewIndicator | None:
        """Return this manager's indicator on a node, if one is attached."""
        return next(
            (
                indicator
                for tracked_node, indicator in self._indicators
                if tracked_node == node
            ),
            None,
        )

    def on_will_remove_children(
        self, parent: QgsLayerTreeNode, index_from: int, index_to: int
    ) -> None:
        """Remove indicators from a subtree before QGIS deletes its nodes."""
        if not isinstance(parent, QgsLayerTreeGroup):
            return
        for child in parent.children()[index_from : index_to + 1]:
            self.remove_subtree_indicators(child)

    def on_removed_children(
        self, parent: QgsLayerTreeNode, _index_from: int, _index_to: int
    ) -> None:
        """Refresh surviving groups after their children have been removed."""
        if isinstance(parent, QgsLayerTreeGroup):
            self.update_group(parent)
            ancestor = parent.parent()
            while isinstance(ancestor, QgsLayerTreeGroup):
                self.update_group(ancestor)
                ancestor = ancestor.parent()

    def remove_subtree_indicators(self, node: QgsLayerTreeNode) -> None:
        """Detach indicators owned by this manager from a removed subtree."""
        indicator = self.managed_indicator(node)
        if indicator is not None:
            self.layer_tree_view.removeIndicator(node, indicator)
            indicator.deleteLater()
            self._indicators = [
                entry for entry in self._indicators if entry[1] != indicator
            ]
        if isinstance(node, QgsLayerTreeGroup):
            for child in node.children():
                self.remove_subtree_indicators(child)
        elif isinstance(node, QgsLayerTreeLayer):
            layer = node.layer()
            if layer is not None:
                tracked = self._tracked_layers.pop(layer.id(), None)
                if tracked is not None:
                    layer.customPropertyChanged.disconnect(tracked[1])
