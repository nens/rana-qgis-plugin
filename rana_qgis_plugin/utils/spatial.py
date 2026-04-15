from functools import partial

from pyproj import CRS, Transformer
from shapely.geometry import box
from shapely.ops import transform


def get_bbox_area_in_m2(bbox: list[float], crs_str: str) -> float:
    if CRS.from_string(crs_str).axis_info[0].unit_name == "metre":
        return box(*bbox).area
    else:
        transformer = Transformer.from_crs(crs_str, "EPSG:3857", always_xy=True)
        project = partial(transformer.transform)
        transformed_geom = transform(project, box(*bbox))
        return transformed_geom.area
