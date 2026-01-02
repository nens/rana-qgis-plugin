from pyproj import CRS
from shapely.geometry import box


def get_bbox_area_in_m2(bbox: list[float], crs_str: str) -> float:
    if CRS.from_string(crs_str).axis_info[0].unit_name == "metre":
        return box(*bbox).area
    else:
        polygon = to_crs(box(*bbox), crs_from=crs_str, crs_to="EPSG:3857")
        return polygon.area
