from pyproj import CRS
from shapely.geometry import box


def get_bbox_area_in_m2(
    bbox: list[float], crs_str: str, pixel_size: float = 1
) -> float:
    if CRS.from_string(crs_str).axis_info[0].unit_name == "metre":
        return box(*bbox).area * pixel_size**2
    else:
        polygon = to_crs(box(*bbox), crs_from=crs_str, crs_to="EPSG:3857")
        return polygon.area * pixel_size**2
