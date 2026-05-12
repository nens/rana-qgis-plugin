import pytest

import rana_qgis_plugin.utils.generic as utils


@pytest.mark.parametrize(
    "input_bytes, expected_output",
    [
        (0, "0 Byte"),
        (1, "1.0 Bytes"),
        (1023, "1023.0 Bytes"),
        (1024, "1.0 KB"),
        (2048, "2.0 KB"),
        (1048576, "1.0 MB"),
        (1073741824, "1.0 GB"),
        (pow(1024, 4), "1.0 TB"),  # 1 Terabyte
        (123456789, "117.74 MB"),
    ],
)
def test_display_bytes(input_bytes, expected_output):
    assert utils.display_bytes(input_bytes) == expected_output


@pytest.mark.parametrize(
    "url",
    [
        "/tenant/something/project",
        "/tenant/something/project/somethingelse",
        "/tenant/something/project/somethingelse/file.txt",
    ],
)
def test_parse_url_no_query(url):
    # ensure the correct elements are extracted from the path
    path_params, query_params = utils.parse_url(url)
    assert path_params == {"tenant_id": "tenant", "project_id": "project"}


def test_parse_url_with_query():
    # just ensure that query_parmas are returned, no need to test urllib
    url = "/tenant/something/project?param1=value1"
    path_params, query_params = utils.parse_url(url)
    assert query_params == {"param1": ["value1"]}
