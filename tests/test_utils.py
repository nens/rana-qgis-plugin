import json
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


@pytest.fixture
def result_folder_info():
    return {
        "schematisation_id": 1,
        "schematisation_name": "foo",
        "revision_number": 1,
        "simulation_name": "bar",
    }


@pytest.fixture
def results_folder_subpath(result_folder_info):
    return [
        f"revision {result_folder_info['revision_number']}",
        "results",
        result_folder_info["simulation_name"],
    ]


def test_get_threedi_schematisation_simulation_results_folder_no_local_data(
    result_folder_info, results_folder_subpath
):
    results_folder = utils.get_threedi_schematisation_simulation_results_folder(
        "./", **result_folder_info
    )
    expected_folder = str(
        Path(result_folder_info["schematisation_name"]).joinpath(
            *results_folder_subpath
        )
    )
    assert results_folder == expected_folder


def test_get_threedi_schematisation_simulation_results_folder_with_local_schema(
    tmp_path, result_folder_info, results_folder_subpath
):
    workdir = Path(tmp_path)
    schemadir = workdir.joinpath(result_folder_info["schematisation_name"])
    schemadir.mkdir(parents=True, exist_ok=True)
    results_folder = utils.get_threedi_schematisation_simulation_results_folder(
        str(workdir), **result_folder_info
    )
    expected_folder = str(schemadir.joinpath(*results_folder_subpath))
    assert results_folder == expected_folder


def test_get_threedi_schematisation_simulation_results_folder_with_local_rev(
    tmp_path, result_folder_info, results_folder_subpath
):
    workdir = Path(tmp_path)
    schemadir = workdir.joinpath(result_folder_info["schematisation_name"])
    revdir = schemadir.joinpath(f"revision {result_folder_info['revision_number']}")
    revdir.mkdir(parents=True, exist_ok=True)
    # create schematisation config
    config_path = Path(schemadir) / "admin" / "schematisation.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config = {
        "id": 1,
        "name": result_folder_info["schematisation_name"],
        "revisions": [result_folder_info["revision_number"]],
        "wip_parent_revision": 1,
    }
    with open(config_path, "w") as f:
        json.dump(config, f)
    results_folder = utils.get_threedi_schematisation_simulation_results_folder(
        str(workdir), **result_folder_info
    )
    expected_folder = str(schemadir.joinpath(*results_folder_subpath))
    assert results_folder == expected_folder


def test_get_threedi_schematisation_simulation_results_folder_with_colon(
    tmp_path, result_folder_info, results_folder_subpath
):
    workdir = Path(tmp_path)
    result_folder_info["schematisation_name"] = "foo:bar"
    schemadir = workdir.joinpath(result_folder_info["schematisation_name"])
    schemadir.mkdir(parents=True, exist_ok=True)
    results_folder = utils.get_threedi_schematisation_simulation_results_folder(
        str(workdir), **result_folder_info
    )
    expected_folder = str(schemadir.joinpath(*results_folder_subpath)).replace(":", "_")
    assert results_folder == expected_folder
