import math
import os
from datetime import datetime, timezone

from dateutil import parser
from dateutil.relativedelta import relativedelta
from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer
from qgis.PyQt.QtCore import QSettings, Qt
from qgis.PyQt.QtGui import QFont, QFontMetrics, QStandardItem

from .communication import UICommunication
from .constant import RANA_TENANT_ENTRY
from .utils_qgis import get_threedi_models_and_simulations_instance


def set_tenant_id(tenant: str):
    settings = QSettings()
    settings.setValue(RANA_TENANT_ENTRY, tenant)


def get_tenant_id() -> str:
    settings = QSettings()
    tenant = settings.value(RANA_TENANT_ENTRY)
    return tenant


def get_local_file_path(project_slug: str, file_path: str, file_name: str) -> tuple[str, str]:
    base_dir = os.path.join(os.path.expanduser("~"), "Rana")
    local_dir_structure = os.path.join(base_dir, project_slug, os.path.dirname(file_path))
    local_file_path = os.path.join(local_dir_structure, file_name)
    return local_dir_structure, local_file_path


def add_layer_to_qgis(
    communication: UICommunication,
    local_file_path: str,
    project_name: str,
    file: dict,
    schematisation_instance: dict,
):
    file_path = file["id"]
    file_name = os.path.basename(file_path.rstrip("/"))
    data_type = file["descriptor"]["data_type"]

    # Save the last modified date of the downloaded file in QSettings
    last_modified_key = f"{project_name}/{file_path}/last_modified"
    QSettings().setValue(last_modified_key, file["last_modified"])

    # Add the layer to QGIS
    if data_type == "raster":
        layer = QgsRasterLayer(local_file_path, file_name)
        if layer.isValid():
            QgsProject.instance().addMapLayer(layer)
            communication.bar_info(f"Added {data_type} layer: {local_file_path}")
        else:
            communication.show_error(f"Failed to add {data_type} layer: {local_file_path}")
    elif data_type == "vector":
        # Load the vector layer and its sub layers
        base_layer = QgsVectorLayer(local_file_path, "temp", "ogr")
        if not base_layer.isValid():
            communication.show_error(f"Vector layer is not valid: {local_file_path}")
            return
        sub_layers = base_layer.dataProvider().subLayers()
        if not sub_layers:
            communication.show_error(f"Failed to get sub layers from: {local_file_path}")
            return
        if len(sub_layers) == 1:
            # Single layer vector file
            layer = QgsVectorLayer(local_file_path, file_name, "ogr")
            if layer.isValid():
                QgsProject.instance().addMapLayer(layer)
                communication.bar_info(f"Added {data_type} layer: {local_file_path}")
            else:
                communication.show_error(f"Failed to add {data_type} layer: {local_file_path}")
            return
        for sub_layer in sub_layers:
            # Multiple layer vector file
            # Extract correct layer name from the sub_layer string
            # Example sub_layer string: "0!!::!!v2_2d_boundary_conditions!!::!!0!!::!!LineString!!::!!the_geom!!::!!"
            # we need to get only the layer name: "v2_2d_boundary_conditions"
            layer_name = sub_layer.split("!!::!!")[1]
            layer_uri = f"{local_file_path}|layername={layer_name}"
            layer = QgsVectorLayer(layer_uri, layer_name, "ogr")
            if layer.isValid():
                QgsProject.instance().addMapLayer(layer)
            else:
                communication.show_error(f"Failed to add {layer_name} layer from: {local_file_path}")
        communication.bar_info(f"Added {data_type} layer: {local_file_path}")
    elif data_type == "threedi_schematisation" and schematisation_instance:
        communication.clear_message_bar()
        threedi_models_and_simulations = get_threedi_models_and_simulations_instance()
        if not threedi_models_and_simulations:
            communication.show_error("Please enable the 3Di Models and Simulations plugin to open this schematisation.")
            return
        schematisation = schematisation_instance["schematisation"]
        revision = schematisation_instance["latest_revision"]
        if not revision:
            communication.show_warn("Cannot open a schematisation without a revision.")
            return
        communication.bar_info(f"Opening the schematisation in the 3Di Models and Simulations plugin...")
        threedi_models_and_simulations.run()
        threedi_models_and_simulations.dockwidget.build_options.load_remote_schematisation(schematisation, revision)
    else:
        communication.show_warn(f"Unsupported data type: {data_type}")


def display_bytes(bytes: int) -> str:
    sizes = ["Bytes", "KB", "MB", "GB", "TB"]
    if bytes == 0:
        return "0 Byte"
    i = int(math.floor(math.log(bytes, 1024)))
    p = math.pow(1024, i)
    s = round(bytes / p, 2)
    return f"{s} {sizes[i]}"


def elide_text(font: QFont, text: str, max_width: int) -> str:
    # Calculate elided text based on font and max width
    font_metrics = QFontMetrics(font)
    return font_metrics.elidedText(text, Qt.ElideRight, max_width)


def convert_to_timestamp(timestamp: str) -> float:
    if timestamp.endswith("Z"):
        timestamp = timestamp.replace("Z", "+00:00")
    dt = datetime.fromisoformat(timestamp)
    return dt.timestamp()


def convert_to_local_time(timestamp: str) -> str:
    time = parser.isoparse(timestamp)
    return time.astimezone().strftime("%d-%m-%Y %H:%M")


def convert_to_relative_time(timestamp: str) -> str:
    """Convert a timestamp into a relative time string."""
    now = datetime.now(timezone.utc)
    past = parser.isoparse(timestamp)
    delta = relativedelta(now, past)

    if delta.years > 0:
        return f"{delta.years} year{'s' if delta.years > 1 else ''} ago"
    elif delta.months > 0:
        return f"{delta.months} month{'s' if delta.months > 1 else ''} ago"
    elif delta.days > 0:
        return f"{delta.days} day{'s' if delta.days > 1 else ''} ago"
    elif delta.hours > 0:
        return f"{delta.hours} hour{'s' if delta.hours > 1 else ''} ago"
    elif delta.minutes > 0:
        return f"{delta.minutes} minute{'s' if delta.minutes > 1 else ''} ago"
    else:
        return "Just now"


class NumericItem(QStandardItem):
    def __lt__(self, other):
        return self.data(Qt.UserRole) < other.data(Qt.UserRole)
