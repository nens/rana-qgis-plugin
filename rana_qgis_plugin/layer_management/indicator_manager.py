"""Show dirty-state indicators on Rana-linked layer tree items."""

from collections.abc import Callable

from qgis.core import QgsApplication, QgsMapLayer, QgsProject
from qgis.gui import QgsLayerTreeView, QgsLayerTreeViewIndicator

from rana_qgis_plugin.layer_management.dirty_tracking import (
    DATA_DIRTY_PROPERTY,
    STYLE_DIRTY_PROPERTY,
    is_data_dirty,
    is_style_dirty,
)
from rana_qgis_plugin.layer_management.layer_manager import is_rana_linked


class IndicatorManager:
    """Attach an indicator to Rana-linked layers when they become dirty."""

    def __init__(self, project: QgsProject, layer_tree_view: QgsLayerTreeView):
        self.project = project
        self.layer_tree_view = layer_tree_view
        self._tracked_layers: dict[str, tuple[QgsMapLayer, Callable[[str], None]]] = {}
        self._indicators: dict[str, QgsLayerTreeViewIndicator] = {}

    def connect(self) -> None:
        """Start tracking layers added to the project."""
        self.project.layersAdded.connect(self.track_layers)

    def disconnect(self) -> None:
        """Stop tracking project and layer signals."""
        self.project.layersAdded.disconnect(self.track_layers)
        for layer, property_slot in self._tracked_layers.values():
            layer.customPropertyChanged.disconnect(property_slot)
        self._tracked_layers.clear()

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
        """Add or remove the layer's indicator according to its dirty flags."""
        layer_id = layer.id()
        is_dirty = is_data_dirty(layer) or is_style_dirty(layer)
        root = self.project.layerTreeRoot()
        assert root is not None
        node = root.findLayer(layer_id)
        indicator = self._indicators.get(layer_id)

        if is_dirty and node is not None and indicator is None:
            indicator = QgsLayerTreeViewIndicator(self.layer_tree_view)
            indicator.setIcon(QgsApplication.getThemeIcon("/mIconWarning.svg"))
            indicator.setToolTip("Has unsynced changes to Rana")
            self.layer_tree_view.addIndicator(node, indicator)
            self._indicators[layer_id] = indicator
        elif not is_dirty and node is not None and indicator is not None:
            self.layer_tree_view.removeIndicator(node, indicator)
            indicator.deleteLater()
            del self._indicators[layer_id]
