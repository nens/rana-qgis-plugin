import os
from collections import namedtuple

from qgis.core import (
    QgsColorRampShader,
    QgsGradientColorRamp,
    QgsGradientStop,
    QgsRasterBandStats,
    QgsRasterLayer,
    QgsRasterShader,
    QgsSingleBandPseudoColorRenderer,
)
from qgis.PyQt.QtGui import QColor
from qgis.utils import plugins

ColorRampData = namedtuple("ColorRampData", ["name", "colors", "info"])

COLOR_RAMP_OCEAN_DEEP = ColorRampData(
    "Ocean Deep",
    ["#ffffcc", "#a1dab4", "#41b6c4", "#2c7fb8", "#253494", "#0d1336"],
    {
        "source": "Thyng, K.M., C.A. Greene, R.D. Hetland, H.M. Zimmerle, and S.F. DiMarco (2016). True colors of "
        "oceanography: Guidelines for effective and accurate colormap selection. Oceanography, 29(3):9-13, "
        "http://dx.doi.org/10.5670/oceanog.2016.66."
    },
)

COLOR_RAMP_OCEAN_HALINE = ColorRampData(
    "Ocean Haline",
    [
        "#231067",
        "#2c1d90",
        "#19399f",
        "#0c5094",
        "#15628d",
        "#237289",
        "#308088",
        "#3a9187",
        "#45a383",
        "#53b47a",
        "#69c26e",
        "#8dd05f",
        "#b7da60",
        "#dce378",
        "#fdf2ae",
    ],
    {
        "source": "Thyng, K.M., C.A. Greene, R.D. Hetland, H.M. Zimmerle, and S.F. DiMarco (2016). True colors of "
        "oceanography: Guidelines for effective and accurate colormap selection. Oceanography, 29(3):9-13, "
        "http://dx.doi.org/10.5670/oceanog.2016.66."
    },
)

COLOR_RAMP_OCEAN_CURL = ColorRampData(
    "Ocean Curl",
    [
        # '#0D163E',
        "#1B3E57",
        "#185F6A",
        "#1B8179",
        "#4B9F84",
        "#8FBA99",
        "#CBD5C1",
        "#FAF1EE",
        "#EAC5B4",
        "#DD9983",
        "#CC6C67",
        "#B24560",
        "#8D2560",
        "#611554",
        # '#330C34'
    ],
    {
        "source": "Thyng, K.M., C.A. Greene, R.D. Hetland, H.M. Zimmerle, and S.F. DiMarco (2016). True colors of "
        "oceanography: Guidelines for effective and accurate colormap selection. Oceanography, 29(3):9-13, "
        "http://dx.doi.org/10.5670/oceanog.2016.66."
    },
)

COLOR_RAMPS = [COLOR_RAMP_OCEAN_DEEP, COLOR_RAMP_OCEAN_HALINE, COLOR_RAMP_OCEAN_CURL]


def get_plugin_instance(plugin_name):
    """Return given plugin name instance."""
    try:
        plugin_instance = plugins[plugin_name]
    except (AttributeError, KeyError):
        plugin_instance = None
    return plugin_instance


def get_threedi_results_analysis_tool_instance():
    return get_plugin_instance("threedi_results_analysis")


def is_loaded_in_schematisation_editor(local_schematisation_gpkg):
    """Check if local schematisation revision is loaded in the Schematisation Editor."""
    if local_schematisation_gpkg is None:
        return None
    local_schematisation_gpkg = os.path.normpath(local_schematisation_gpkg)
    try:
        schematisation_editor = plugins["threedi_schematisation_editor"]
        return (
            local_schematisation_gpkg
            in schematisation_editor.workspace_context_manager.layer_managers
        )
    except KeyError:
        return None


def multiband_raster_min_max(layer):
    """Return the min and max values across all bands"""
    provider = layer.dataProvider()
    band_count = provider.bandCount()

    global_min = float("inf")
    global_max = float("-inf")

    for band in range(1, band_count + 1):
        stats = provider.bandStatistics(
            band, QgsRasterBandStats.Min | QgsRasterBandStats.Max
        )
        global_min = min(global_min, stats.minimumValue)
        global_max = max(global_max, stats.maximumValue)

    return global_min, global_max


def color_ramp_from_data(data: ColorRampData):
    assert len(data.colors) >= 2, "A color ramp needs at least three colors"
    color1 = QColor(data.colors[0])
    color2 = QColor(data.colors[-1])
    stops = []
    if len(data.colors) > 2:
        for i, color in enumerate(data.colors[1:-1]):
            stop = QgsGradientStop((i + 1) / (len(data.colors) - 1), QColor(color))
            stops.append(stop)
    ramp = QgsGradientColorRamp(color1=color1, color2=color2, stops=stops)
    ramp.setInfo(data.info)
    return ramp


def apply_gradient_ramp(
    layer: QgsRasterLayer,
    color_ramp: QgsGradientColorRamp,
    min_value: float,
    max_value: float,
    band: int = 1,
):
    """
    Apply a gradient color ramp to a raster layer, stretched over given min/max values.

    Parameters
    ----------
    layer : QgsRasterLayer
        The raster layer to style.
    color_ramp : QgsGradientColorRamp
        The gradient color ramp to apply.
    min_value : float
        The minimum value to be used when stretching the color map over the data
    max_value : float
        The maximum value to be used when stretching the color map over the data
    band : int
        Raster band index (default=1).
    """
    # Define the color ramp shader
    color_ramp_shader = QgsColorRampShader()
    color_ramp_shader.setColorRampType(QgsColorRampShader.Interpolated)
    color_ramp_shader.setMinimumValue(min_value)
    color_ramp_shader.setMaximumValue(max_value)
    color_ramp_shader.setSourceColorRamp(color_ramp)
    color_ramp_shader.classifyColorRamp(classes=25)

    # Create shader function
    shader = QgsRasterShader()
    shader.setRasterShaderFunction(color_ramp_shader)

    # Create renderer
    renderer = QgsSingleBandPseudoColorRenderer(layer.dataProvider(), band, shader)
    renderer.setClassificationMin(min_value)
    renderer.setClassificationMax(max_value)

    # Apply renderer to layer
    layer.setRenderer(renderer)
    layer.triggerRepaint()
