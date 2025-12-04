import math
import os
from datetime import datetime, timezone
from typing import Any, Dict, Tuple
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from dateutil import parser
from dateutil.relativedelta import relativedelta
from osgeo import gdal
from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer
from qgis.PyQt.QtCore import QBuffer, QByteArray, QIODevice, QSettings, Qt
from qgis.PyQt.QtGui import QFont, QFontMetrics, QImage, QStandardItem
from threedi_mi_utils import (
    LocalRevision,
    LocalSchematisation,
    list_local_schematisations,
)

from rana_qgis_plugin.auth_3di import get_3di_auth
from rana_qgis_plugin.simulation.threedi_calls import (
    get_api_client_with_personal_api_token,
)
from rana_qgis_plugin.simulation.utils import load_remote_schematisation
from rana_qgis_plugin.utils_api import get_frontend_settings
from rana_qgis_plugin.utils_settings import hcc_working_dir

from .communication import UICommunication


def is_writable(working_dir: str) -> bool:
    """Try to write and remove an empty text file into given location."""
    try:
        test_filename = f"{uuid4()}.txt"
        test_file_path = os.path.join(working_dir, test_filename)
        with open(test_file_path, "w") as test_file:
            test_file.write("")
        os.remove(test_file_path)
    except (PermissionError, OSError):
        return False
    else:
        return True


def get_local_file_path(project_slug: str, path: str) -> tuple[str, str]:
    file_name = os.path.basename(path.rstrip("/"))
    file_name_without_extension = os.path.splitext(file_name)[0]
    base_dir = os.path.join(os.path.expanduser("~"), "Rana")
    local_dir_structure = os.path.join(
        base_dir, project_slug, os.path.dirname(path), file_name_without_extension
    )
    local_file_path = os.path.join(local_dir_structure, file_name)
    return local_dir_structure, local_file_path


def get_threedi_api():
    _, personal_api_token = get_3di_auth()
    frontend_settings = get_frontend_settings()
    api_url = frontend_settings["hcc_url"].rstrip("/")
    threedi_api = get_api_client_with_personal_api_token(personal_api_token, api_url)
    return threedi_api


def add_layer_to_qgis(
    communication: UICommunication,
    local_file_path: str,
    project_name: str,
    file: dict,
    descriptor: dict,
    schematisation_instance: dict,
):
    path = file["id"]
    file_name = os.path.basename(path.rstrip("/"))
    data_type = descriptor["data_type"]

    # Save the last modified date of the downloaded file in QSettings
    last_modified_key = f"{project_name}/{path}/last_modified"
    QSettings().setValue(last_modified_key, file["last_modified"])

    # Add the layer to QGIS
    if data_type == "raster":
        layer = QgsRasterLayer(local_file_path, file_name)
        if layer.isValid():
            QgsProject.instance().addMapLayer(layer)
            communication.bar_info(f"Added {data_type} layer: {local_file_path}")
        else:
            communication.show_error(
                f"Failed to add {data_type} layer: {local_file_path}"
            )
    elif data_type == "vector":
        if descriptor["meta"] is None:
            communication.show_warn(
                f"No metadata found for {file_name}, processing probably has not finished yet."
            )
            return
        layers = descriptor["meta"].get("layers", [])
        if not layers:
            communication.show_warn(f"No layers found for {file_name}.")
            return
        for layer in layers:
            layer_name = layer["name"]
            layer_uri = f"{local_file_path}|layername={layer_name}"
            layer = QgsVectorLayer(layer_uri, layer_name, "ogr")
            if layer.isValid():
                QgsProject.instance().addMapLayer(layer)
                # Apply the QML style file to the layer
                qml_path = os.path.join(
                    os.path.dirname(local_file_path), f"{layer_name}.qml"
                )
                if os.path.exists(qml_path):
                    layer.loadNamedStyle(qml_path)
                    layer.triggerRepaint()
            else:
                communication.show_error(
                    f"Failed to add {layer_name} layer from: {local_file_path}"
                )
        communication.bar_info(f"Added {data_type} file: {local_file_path}")
    elif data_type == "threedi_schematisation" and schematisation_instance:
        communication.clear_message_bar()

        schematisation = schematisation_instance["schematisation"]
        revision = schematisation_instance["latest_revision"]
        if not revision:
            communication.show_warn("Cannot open a schematisation without a revision.")
            return
        pb = communication.progress_bar(
            msg="Downloading remote schematisation...", clear_msg_bar=True
        )

        if not hcc_working_dir():
            communication.show_warn(
                "Working directory not yet set, please configure this in the plugin settings."
            )
            return

        load_remote_schematisation(
            communication,
            schematisation,
            revision,
            pb,
            hcc_working_dir(),
            get_threedi_api(),
        )
        communication.clear_message_bar()
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
    return font_metrics.elidedText(text, Qt.TextElideMode.ElideRight, max_width)


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


def image_to_bytes(image: QImage) -> bytes:
    """Convert QImage to bytes."""
    byte_array = QByteArray()
    buffer = QBuffer(byte_array)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(byte_array.data())


class NumericItem(QStandardItem):
    def __lt__(self, other):
        return self.data(Qt.ItemDataRole.UserRole) < other.data(
            Qt.ItemDataRole.UserRole
        )


def parse_url(url: str) -> Tuple[Dict[Any, Any], Dict[Any, Any]]:
    """Returns dict with path params and dict with query params"""
    parsed = urlparse(url)
    # Remove leading slash and then split
    path_parts = parsed.path.strip("/").split("/")
    path_params = {
        "tenant_id": path_parts[0],
        "project_id": path_parts[2],
    }
    query_params = parse_qs(parsed.query)
    return path_params, query_params


def get_threedi_schematisation_simulation_results_folder(
    working_dir: str,
    schematisation_id: int,
    schematisation_name: str,
    revision_number: int,
    simulation_name: str,
) -> str:
    local_schematisations = list_local_schematisations(working_dir)

    if schematisation_id:
        try:
            local_schematisation = local_schematisations[schematisation_id]
        except KeyError:
            local_schematisation = LocalSchematisation(
                working_dir, schematisation_id, schematisation_name, create=True
            )
        try:
            local_revision = local_schematisation.revisions[revision_number]
        except KeyError:
            local_revision = LocalRevision(local_schematisation, revision_number)
            local_revision.make_revision_structure()
        result = os.path.join(local_revision.results_dir, simulation_name)
        # replace colons, invalid for Windows paths (don't replace drive colon)
        return result[:3] + result[3:].replace(":", "_")


def split_scenario_extent(grid, resolution=None, max_pixel_count=1 * 10**8):
    """
    Split raster task spatial bounds to fit in to maximum pixel count limit.
    Reimplemented code from https://github.com/nens/threedi-scenario-downloader
    """
    x1 = grid["x"]["origin"]
    y1 = grid["y"]["origin"]
    size_x = grid["x"]["size"]
    size_y = grid["y"]["size"]
    x2 = x1 + size_x
    y2 = y1 + size_y
    if resolution is None:
        pixelsize_x = grid["x"]["cell_size"]
        pixelsize_y = grid["y"]["cell_size"]
    else:
        pixelsize_x = resolution
        pixelsize_y = resolution
    pixelcount_x = abs(size_x / pixelsize_x)
    pixelcount_y = abs(size_y / pixelsize_y)
    if not pixelcount_x.is_integer():
        pixelcount_x = math.ceil(pixelcount_x)
        x2 = (pixelcount_x * pixelsize_x) + x1
    if not pixelcount_y.is_integer():
        pixelcount_y = math.ceil(pixelcount_y)
        y2 = (pixelcount_y * pixelsize_y) + y1
    raster_pixel_count = pixelcount_x * pixelcount_y
    if raster_pixel_count > max_pixel_count:
        max_pixel_per_axis = int(math.sqrt(max_pixel_count))
        columns_count = math.ceil(pixelcount_x / max_pixel_per_axis)
        rows_count = math.ceil(pixelcount_y / max_pixel_per_axis)
        sub_pixelcount_x = max_pixel_per_axis * pixelsize_x
        sub_pixelcount_y = max_pixel_per_axis * pixelsize_y
        bboxes = []
        for column_idx in range(columns_count):
            sub_x1 = x1 + (column_idx * sub_pixelcount_x)
            sub_x2 = sub_x1 + sub_pixelcount_x
            for row_idx in range(rows_count):
                sub_y1 = y1 + (row_idx * sub_pixelcount_y)
                sub_y2 = sub_y1 + sub_pixelcount_y
                sub_bbox = (sub_x1, sub_y1, sub_x2, sub_y2)
                bboxes.append(sub_bbox)
        spatial_bounds = (bboxes, sub_pixelcount_x, sub_pixelcount_y)
    else:
        bboxes = [(x1, y1, x2, y2)]
        spatial_bounds = (bboxes, pixelcount_x, pixelcount_y)
    return spatial_bounds


def build_vrt(output_filepath, raster_filepaths, **vrt_options):
    """Build VRT for the list of rasters."""
    gdal.UseExceptions()
    options = gdal.BuildVRTOptions(**vrt_options)
    vrt_ds = gdal.BuildVRT(output_filepath, raster_filepaths, options=options)
    vrt_ds = None
