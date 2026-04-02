import os
from pathlib import Path

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
