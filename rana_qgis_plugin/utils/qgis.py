import os
from pathlib import Path
from urllib.parse import quote
from xml.etree import ElementTree as ET

from qgis.core import (
    Qgis,
    QgsProject,
    QgsVectorFileWriter,
    QgsVectorLayer,
)
from qgis.utils import plugins


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


def convert_vectorfile_to_geopackage(
    vector_path: str, layer_name: str = "default"
) -> str:
    """Returns the path of the resulting geopackage"""
    layer = QgsVectorLayer(vector_path, layer_name, "ogr")
    if not layer.isValid():
        raise Exception("Layer failed to load")

    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = "GPKG"
    options.layerName = layer_name
    options.symbologyExport = Qgis.FeatureSymbologyExport.PerFeature

    gpkg_path = str(Path(vector_path).with_suffix(".gpkg"))

    error = QgsVectorFileWriter.writeAsVectorFormatV3(
        layer, gpkg_path, QgsProject.instance().transformContext(), options
    )

    if error[0] != QgsVectorFileWriter.NoError:
        raise Exception(error)

    # Explicitly embed the style in the geopackage
    gpkg_layer = QgsVectorLayer(
        f"{gpkg_path}|layername={layer_name}", layer_name, "ogr"
    )

    gpkg_layer.saveStyleToDatabase(
        name="default", description="", useAsDefault=True, uiFileContent=None
    )

    return gpkg_path


def rescale_qml_ranges(qml_string: str, new_min: float, new_max: float) -> str | None:
    """Rescale QML raster style to a new data range.

    Updates classificationMin/Max, shader ranges, and proportionally rescales color
    stop values. Returns None if no changes needed, otherwise returns modified QML.
    """
    # Validate input qml; skip rescaling in case of any problems
    try:
        root = ET.fromstring(qml_string)
    except ET.ParseError:
        return None
    raster_renderer = root.find(".//rasterrenderer")
    if raster_renderer is None:
        return None
    try:
        current_min = float(raster_renderer.get("classificationMin", "0"))
        current_max = float(raster_renderer.get("classificationMax", "1"))
    except (ValueError, TypeError):
        return None
    # Validate range; skip rescaling if degenerate
    if current_min == current_max:
        return None
    # Return if no changes are needed
    if current_min == new_min and current_max == new_max:
        return None

    # Update rasterrenderer attributes
    raster_renderer.set("classificationMin", str(new_min))
    raster_renderer.set("classificationMax", str(new_max))

    # Find and update the colorrampshader element
    shader = raster_renderer.find(".//colorrampshader")
    if shader is None:
        return ET.tostring(root, encoding="unicode")
    shader.set("minimumValue", str(new_min))
    shader.set("maximumValue", str(new_max))

    # Rescale color stop values proportionally
    for item in shader.findall("item"):
        try:
            old_value = float(item.get("value", "0"))
        except (ValueError, TypeError):
            continue
        t = (old_value - current_min) / (current_max - current_min)
        new_value = new_min + t * (new_max - new_min)
        item.set("value", str(new_value))

    return ET.tostring(root, encoding="unicode")


def rescale_qml_file(file_path: Path, new_min: float, new_max: float) -> None:
    """Rescale QML file ranges and save only if changed.

    Args:
        file_path: Path to the QML file
        new_min: Target minimum data value
        new_max: Target maximum data value
    """
    try:
        content = file_path.read_text()
    except (IOError, OSError):
        return

    rescaled = rescale_qml_ranges(content, new_min, new_max)
    if rescaled is not None:
        try:
            file_path.write_text(rescaled)
        except (IOError, OSError):
            pass


def get_qml_name_for_layer(layer_name: str) -> str:
    """Returns uri escaped layer name for QML file name."""
    return f"{quote(layer_name, safe='')}.qml"
