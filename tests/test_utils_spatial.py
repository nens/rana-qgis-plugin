import math

import pytest

from rana_qgis_plugin.utils_spatial import get_bbox_area_in_m2


@pytest.mark.parametrize(
    "bbox,crs_str,expected_area",
    [
        ([500000, 5000000, 501000, 5001000], "EPSG:32623", 1e6),
        ([0, 0, 0.008984, 0.008984], "EPSG:4326", 1000188.6235655261),
    ],
)
def test_get_bbox_area_in_m2(bbox, crs_str, expected_area):
    area = get_bbox_area_in_m2(bbox, crs_str)
    assert math.isclose(area, expected_area, rel_tol=1e-9)
