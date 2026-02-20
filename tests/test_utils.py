from pathlib import Path

import pytest

import rana_qgis_plugin.utils as utils


def test_get_local_file_path():
    rana_root = "/root/Rana/"
    project = "foo"
    file_id = "bar.txt"
    file_stem = Path(file_id).stem
    local_dir, local_path = utils.get_local_file_path(project, file_id)
    assert local_dir == rana_root + project + "/" + file_stem
    assert local_path == rana_root + project + "/" + file_stem + "/" + file_id


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


def test_get_threedi_schematisation_simulation_results_folder_no_local_data():
    results_folder = utils.get_threedi_schematisation_simulation_results_folder(
        "./", 1, "foo", 1, "bar"
    )
    assert results_folder == "foo/revision 1/results/bar"


def test_get_threedi_schematisation_simulation_results_folder_with_local_schema(
    tmp_path,
):
    workdir = Path(tmp_path)
    schemadir = workdir.joinpath("foo")
    schemadir.mkdir(parents=True, exist_ok=True)
    results_folder = utils.get_threedi_schematisation_simulation_results_folder(
        str(workdir), 1, "foo", 1, "bar"
    )
    expected_folder = str(schemadir.joinpath("revision 1", "results", "bar"))
    assert results_folder == expected_folder


def test_get_threedi_schematisation_simulation_results_folder_with_local_rev(tmp_path):
    workdir = Path(tmp_path)
    schemadir = workdir.joinpath("foo")
    revdir = schemadir.joinpath("revision 1")
    revdir.mkdir(parents=True, exist_ok=True)
    results_folder = utils.get_threedi_schematisation_simulation_results_folder(
        str(workdir), 1, "foo", 1, "bar"
    )
    expected_folder = str(revdir.joinpath("results", "bar"))
    assert results_folder == expected_folder


def test_get_threedi_schematisation_simulation_results_folder_with_color(tmp_path):
    workdir = Path(tmp_path)
    schemadir = workdir.joinpath("foo:bar")
    schemadir.mkdir(parents=True, exist_ok=True)
    results_folder = utils.get_threedi_schematisation_simulation_results_folder(
        str(workdir), 1, "foo:bar", 1, "bar"
    )
    expected_folder = str(schemadir.joinpath("revision 1", "results", "bar")).replace(
        ":", "_"
    )
    assert results_folder == expected_folder
