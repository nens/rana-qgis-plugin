import math
import os
from pathlib import Path
from typing import Any, Dict, Tuple
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from osgeo import gdal
from qgis.PyQt.QtCore import QBuffer, QByteArray, QIODevice, QSettings, Qt
from qgis.PyQt.QtGui import QFont, QFontMetrics, QImage, QStandardItem
from slugify import slugify
from threedi_mi_utils import (
    LocalRevision,
    LocalSchematisation,
    list_local_schematisations,
)

from rana_qgis_plugin.auth_3di import get_3di_auth
from rana_qgis_plugin.simulation.threedi_calls import (
    get_api_client_with_personal_api_token,
)
from rana_qgis_plugin.utlis.api import get_frontend_settings, get_tenant_details
from rana_qgis_plugin.utlis.settings import rana_cache_dir


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


def sanitize_path_for_filesystem(path: str) -> str:
    """
    Sanitize a path to be valid for Linux and Windows using python-slugify.
    """
    # Split into parts (directories and file)
    slugify_kwargs = {"separator": "_", "lowercase": False, "allow_unicode": True}
    if not path:
        return path
    path_obj = Path(path)
    # Slugify each component of the path (excluding file extension)
    sanitized_parts = [
        slugify(part, **slugify_kwargs)
        for part in path_obj.parts[:-1]  # Slugify directories
    ]
    # Handle the file name separately to preserve extensions
    file_name = path_obj.name
    file_stem = Path(file_name).stem
    file_extension = Path(file_name).suffix

    # Slugify file stem and attach the extension back
    sanitized_file_name = f"{slugify(file_stem, **slugify_kwargs)}{file_extension}"
    sanitized_parts.append(sanitized_file_name)

    # prefix / for absolute paths
    if path_obj.is_absolute():
        sanitized_parts = ["/"] + sanitized_parts

    # Rebuild sanitized path
    return str(Path(*sanitized_parts))


def get_local_dir_structure(project_slug: str, path: str) -> str:
    file_name_without_extension = Path(path).stem
    if not rana_cache_dir():
        base_dir = Path.home() / "Rana"
    else:
        base_dir = Path(rana_cache_dir())
    local_dir_structure = base_dir.joinpath(
        project_slug, "files", Path(path).parent, file_name_without_extension
    )
    return sanitize_path_for_filesystem(str(local_dir_structure))


def get_local_file_path(project_slug: str, path: str) -> str:
    local_dir_structure = Path(get_local_dir_structure(project_slug, path))
    file_name = sanitize_path_for_filesystem(Path(path).name)
    return str(local_dir_structure.joinpath(file_name))


def get_local_publication_dir_structure(
    project_slug: str, path: str, publication_tree: list[str]
) -> str:
    file_name_without_extension = Path(path).stem
    if not rana_cache_dir():
        base_dir = Path.home() / "Rana"
    else:
        base_dir = Path(rana_cache_dir())
    local_dir_structure = base_dir.joinpath(
        project_slug, "publications", *publication_tree, file_name_without_extension
    )
    return sanitize_path_for_filesystem(str(local_dir_structure))


def get_local_publication_file_path(
    project_slug: str, path: str, publication_tree: list[str]
) -> str:
    local_dir_structure = Path(
        get_local_publication_dir_structure(project_slug, path, publication_tree)
    )
    local_file_path = local_dir_structure.joinpath(Path(path).name)
    return sanitize_path_for_filesystem(str(local_file_path))


def get_threedi_api():
    _, personal_api_token = get_3di_auth()
    frontend_settings = get_frontend_settings()
    api_url = frontend_settings["hcc_url"].rstrip("/")
    threedi_api = get_api_client_with_personal_api_token(personal_api_token, api_url)
    return threedi_api


def get_threedi_organisations(communication) -> list[str]:
    """Retrieve threedi organisations linked to rana tenant and fromat the uuids to match threedi-api"""
    return [
        org_id.replace("-", "")
        for org_id in get_tenant_details(communication).get("threedi_organisations", [])
    ]


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
    simulation_id: int,
) -> str:
    local_schematisations = list_local_schematisations(working_dir)
    if schematisation_id:
        local_schematisation = local_schematisations.get(schematisation_id)
        if not local_schematisation:
            local_schematisation = LocalSchematisation(
                working_dir, schematisation_id, schematisation_name, create=True
            )
        local_revision = local_schematisation.revisions.get(revision_number)
        if not local_revision:
            local_revision = LocalRevision(local_schematisation, revision_number)
            local_revision.make_revision_structure()
        result = str(
            Path(local_revision.results_dir).joinpath(
                f"{simulation_name} ({simulation_id})"
            )
        )
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


def get_file_icon_name(data_type: str) -> str:
    # Ensure that data_type is a string so we can safely use string operations
    if not data_type:
        data_type = ""
    icon_map = {
        "scenario": "mIconTemporalRaster.svg",
        "threedi_schematisation": "mIconDbSchema.svg",
        "raster": "mIconRaster.svg",
        "vector": "mIconVector.svg",
        "sqlite": "mIconDbSchema.svg",
        "polygon": "mIconPolygonLayer.svg",
        "point": "mIconPointLayer.svg",
        "linestring": "mIconLineLayer.svg",
        "multipoint": "mIconPointLayer.svg",
        "multilinestring": "mIconLineLayer.svg",
        "multipolygon": "mIconPolygonLayer.svg",
        "geometrycollection": "mIconGeometryCollection.svg",
    }
    return icon_map.get(data_type.lower(), "mIconFile.svg")


def find_publication_map_layer_from_tree(publication_version: dict, tree: list[str]):
    def traverse_layers(layers, path):
        for layer in layers:
            if layer["name"] == path[0]:
                if layer["type"] == "layer" and len(path) == 1:
                    return layer
                # Continue recursion in nested layers
                return traverse_layers(layer.get("layers", []), path[1:])
        return None  # No match found

    for map_ in publication_version.get("maps", []):
        if map_["name"] == tree[0]:
            return traverse_layers(map_.get("layers", []), tree[1:])
    return None
