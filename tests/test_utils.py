import json
from pathlib import Path

import pytest

import rana_qgis_plugin.utlis.generic as utils


@pytest.mark.parametrize(
    "input_path,expected_output",
    [
        ("/folder/invalid:name.txt", "/folder/invalid_name.txt"),
        (
            "/path/with/<special>|chars/file?name*.txt",
            "/path/with/special_chars/file_name.txt",
        ),
        ("/folder/my:important:file", "/folder/my_important_file"),
        ("/path/to/valid_file.txt", "/path/to/valid_file.txt"),
        ("", ""),
        (
            "/root/folder/sub:folder<name>/invalid|file:name*.csv",
            "/root/folder/sub_folder_name/invalid_file_name.csv",
        ),
        ("/path/to/file.name.with.dots.ext", "/path/to/file_name_with_dots.ext"),
        ("/folder/файл/tość/файл.txt", "/folder/файл/tość/файл.txt"),
        ("/folder/SubFolder/File.Name.TXT", "/folder/SubFolder/File_Name.TXT"),
    ],
)
def test_sanitize_path_for_filesystem(input_path, expected_output):
    # Would be great to test this on windows somehow
    result = utils.sanitize_path_for_filesystem(input_path)
    assert result == expected_output


def test_get_local_dir_structure():
    rana_root = "/root/Rana/"
    project = "foo"
    file_id = "baz/bar.txt"
    file_stem = Path(file_id).stem
    local_dir = utils.get_local_dir_structure(project, file_id)
    expected_local_dir = rana_root + project + "/files/baz/" + file_stem
    assert local_dir == expected_local_dir


def test_get_local_file_path():
    rana_root = "/root/Rana/"
    project = "foo"
    file_id = "baz/bar.txt"
    file_name = Path(file_id).name
    file_stem = Path(file_id).stem
    local_path = utils.get_local_file_path(project, file_id)
    expected_local_path = (
        rana_root + project + "/files/baz/" + file_stem + "/" + file_name
    )
    assert local_path == expected_local_path


def test_get_local_publication_dir_structure():
    rana_root = "/root/Rana/"
    project = "foo"
    file_id = "bar.txt"
    file_stem = Path(file_id).stem
    publication_tree = ["publication", "map", "folder"]
    local_dir = utils.get_local_publication_dir_structure(
        project, file_id, publication_tree
    )
    publication_tree_path = "/".join(publication_tree)
    expected_local_dir = (
        rana_root + project + "/publications/" + publication_tree_path + "/" + file_stem
    )
    assert local_dir == expected_local_dir


def test_get_local_publication_file_path():
    rana_root = "/root/Rana/"
    project = "foo"
    file_id = "bar.txt"
    file_stem = Path(file_id).stem
    publication_tree = ["publication", "map", "folder"]
    local_path = utils.get_local_publication_file_path(
        project, file_id, publication_tree
    )
    publication_tree_path = "/".join(publication_tree)
    expected_local_dir = (
        rana_root + project + "/publications/" + publication_tree_path + "/" + file_stem
    )
    assert local_path == expected_local_dir + "/" + file_id


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
        "simulation_id": 1337,
    }


@pytest.fixture
def results_folder_subpath(result_folder_info):
    return [
        f"revision {result_folder_info['revision_number']}",
        "results",
        f"{result_folder_info['simulation_name']} ({result_folder_info['simulation_id']})",
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


def test_find_publication_map_layer_from_tree():
    publication_version = {
        "maps": [
            {
                "name": "map_1",
                "layers": [
                    {"type": "layer", "name": "foo", "some_id": 1},
                    {
                        "type": "folder",
                        "name": "bar",
                        "layers": [{"type": "layer", "name": "foo", "some_id": 2}],
                    },
                ],
            }
        ]
    }
    tree_1 = ["map_1", "foo"]
    tree_2 = ["map_1", "bar", "foo"]
    assert (
        utils.find_publication_map_layer_from_tree(publication_version, tree_1)[
            "some_id"
        ]
        == 1
    )
    assert (
        utils.find_publication_map_layer_from_tree(publication_version, tree_2)[
            "some_id"
        ]
        == 2
    )
