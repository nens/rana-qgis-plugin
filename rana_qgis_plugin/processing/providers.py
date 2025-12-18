from pathlib import Path

from qgis.core import QgsProcessingProvider
from qgis.PyQt.QtGui import QIcon

from rana_qgis_plugin.processing.algorithms_wq import (
    SimulateWithDWFLabellingAlgorithm,
    SimulateWithRainZonesAlgorithm,
)


class RanaQgisPluginProvider(QgsProcessingProvider):
    """Loads the Processing Toolbox algorithms for 3Di"""

    def loadAlgorithms(self, *args, **kwargs):
        self.addAlgorithm(SimulateWithRainZonesAlgorithm())
        self.addAlgorithm(SimulateWithDWFLabellingAlgorithm())
        # pass

    def id(self, *args, **kwargs):
        """The ID of your plugin, used for identifying the provider.

        This string should be a unique, short, character only string,
        eg "qgis" or "gdal". This string should not be localised.
        """
        return "rana_desktop_client"

    def name(self, *args, **kwargs):
        """The human friendly name of your plugin in Processing.

        This string should be as short as possible (e.g. "Lastools", not
        "Lastools version 1.0.1 64-bit") and localised.
        """
        return "Rana Desktop Client"

    def icon(self):
        """Should return a QIcon which is used for your provider inside
        the Processing toolbox.
        """
        icon_path = str(Path(__file__).parents[1].joinpath("icons", "rana.svg"))
        return QIcon(icon_path)
