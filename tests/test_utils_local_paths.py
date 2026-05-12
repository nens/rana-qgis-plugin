import json
from pathlib import Path

import pytest

from rana_qgis_plugin.utils import generic as utils
from rana_qgis_plugin.utils import local_paths


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


@pytest.mark.parametrize(
    "input_path,expected_output",
    [
        ("/path/to/valid_file.txt", "/path/to/valid_file.txt"),
        (
            '/path/with/most:<special>|cha"r"s/file?name*.txt',
            "/path/with/most__special__cha_r_s/file_name_.txt",
        ),
        # backslash is invalid; on Linux it's treated as part of the filename
        ("/folder/name\\file.txt", "/folder/name_file.txt"),
        # rstrip: trailing dot and space are stripped (Windows limitation)
        ("/folder/name./file.txt", "/folder/name/file.txt"),
        ("/folder/name /file.txt", "/folder/name/file.txt"),
    ],
)
def test_sanitize_path_for_filesystem(input_path, expected_output):
    result = local_paths.sanitize_path_for_filesystem(input_path)
    assert result == expected_output


def test_get_local_dir_structure():
    rana_root = "/root/Rana/"
    project = "foo"
    file_id = "baz/bar.txt"
    file_stem = Path(file_id).stem
    local_dir = local_paths.get_local_dir_structure(project, file_id)
    expected_local_dir = rana_root + project + "/files/baz/" + file_stem
    assert local_dir == expected_local_dir


def test_get_local_file_path():
    rana_root = "/root/Rana/"
    project = "foo"
    file_id = "baz/bar.txt"
    file_name = Path(file_id).name
    file_stem = Path(file_id).stem
    local_path = local_paths.get_local_file_path(project, file_id)
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
    local_dir = local_paths.get_local_publication_dir_structure(
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
    local_path = local_paths.get_local_publication_file_path(
        project, file_id, publication_tree
    )
    publication_tree_path = "/".join(publication_tree)
    expected_local_dir = (
        rana_root + project + "/publications/" + publication_tree_path + "/" + file_stem
    )
    assert local_path == expected_local_dir + "/" + file_id


def test_get_local_results_dir_no_local_data(
    tmp_path, result_folder_info, results_folder_subpath
):
    results_folder = local_paths.get_local_results_dir(
        str(tmp_path), **result_folder_info
    )
    expected_folder = str(
        tmp_path
        / result_folder_info["schematisation_name"]
        / "revision 1"
        / "results"
        / f"{result_folder_info['simulation_name']} ({result_folder_info['simulation_id']})"
    )
    assert results_folder == expected_folder


def test_get_local_results_dir_with_local_schema(
    tmp_path, result_folder_info, results_folder_subpath
):
    workdir = Path(tmp_path)
    schemadir = workdir.joinpath(result_folder_info["schematisation_name"])
    schemadir.mkdir(parents=True, exist_ok=True)
    results_folder = local_paths.get_local_results_dir(
        str(workdir), **result_folder_info
    )
    expected_folder = str(schemadir.joinpath(*results_folder_subpath))
    assert results_folder == expected_folder


def test_get_local_results_dir_with_local_rev(
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
        "id": result_folder_info["schematisation_id"],
        "name": result_folder_info["schematisation_name"],
        "revisions": [result_folder_info["revision_number"]],
        "wip_parent_revision": 1,
    }
    with open(config_path, "w") as f:
        json.dump(config, f)
    results_folder = local_paths.get_local_results_dir(
        str(workdir), **result_folder_info
    )
    expected_folder = str(schemadir.joinpath(*results_folder_subpath))
    assert results_folder == expected_folder


def test_get_local_results_dir_with_colon(
    tmp_path, result_folder_info, results_folder_subpath
):
    workdir = Path(tmp_path)
    result_folder_info["schematisation_name"] = "foo:bar"
    schemadir = workdir.joinpath(result_folder_info["schematisation_name"])
    schemadir.mkdir(parents=True, exist_ok=True)
    results_folder = local_paths.get_local_results_dir(
        str(workdir), **result_folder_info
    )
    expected_folder = str(schemadir.joinpath(*results_folder_subpath)).replace(":", "_")
    assert results_folder == expected_folder


def test_get_local_schematisation_revision_dir_not_found(tmp_path):
    """Returns None when schematisation is not found locally and create=False."""
    result = local_paths.get_local_schematisation_revision_dir(
        str(tmp_path), 999, "nonexistent", 1, create=False
    )
    assert result is None


def test_get_local_schematisation_revision_dir_no_working_dir():
    """Returns None when working_dir is empty."""
    result = local_paths.get_local_schematisation_revision_dir(
        "", 1, "foo", 1, create=False
    )
    assert result is None


def test_get_local_schematisation_revision_dir_found(tmp_path, result_folder_info):
    """Returns the revision dir when it exists locally."""
    workdir = tmp_path
    schemadir = workdir / result_folder_info["schematisation_name"]
    revdir = schemadir / f"revision {result_folder_info['revision_number']}"
    revdir.mkdir(parents=True, exist_ok=True)
    # create schematisation config
    config_path = schemadir / "admin" / "schematisation.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config = {
        "id": result_folder_info["schematisation_id"],
        "name": result_folder_info["schematisation_name"],
        "revisions": [result_folder_info["revision_number"]],
        "wip_parent_revision": 1,
    }
    with open(config_path, "w") as f:
        json.dump(config, f)

    result = local_paths.get_local_schematisation_revision_dir(
        str(workdir),
        result_folder_info["schematisation_id"],
        result_folder_info["schematisation_name"],
        result_folder_info["revision_number"],
        create=False,
    )
    assert result == revdir


def test_get_local_schematisation_revision_dir_creates(tmp_path, result_folder_info):
    """Creates the revision dir when create=True."""
    result = local_paths.get_local_schematisation_revision_dir(
        str(tmp_path),
        result_folder_info["schematisation_id"],
        result_folder_info["schematisation_name"],
        result_folder_info["revision_number"],
        create=True,
    )
    assert result is not None
    assert result.exists()


def test_get_local_results_dir_from_meta_complete(tmp_path, result_folder_info):
    """Returns results dir when meta is complete and revision exists."""
    workdir = tmp_path
    schemadir = workdir / result_folder_info["schematisation_name"]
    revdir = schemadir / f"revision {result_folder_info['revision_number']}"
    revdir.mkdir(parents=True, exist_ok=True)
    config_path = schemadir / "admin" / "schematisation.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config = {
        "id": result_folder_info["schematisation_id"],
        "name": result_folder_info["schematisation_name"],
        "revisions": [result_folder_info["revision_number"]],
        "wip_parent_revision": 1,
    }
    with open(config_path, "w") as f:
        json.dump(config, f)

    meta = {
        "schematisation": {
            "id": result_folder_info["schematisation_id"],
            "name": result_folder_info["schematisation_name"],
            "version": result_folder_info["revision_number"],
        },
        "simulation": {
            "id": result_folder_info["simulation_id"],
            "name": result_folder_info["simulation_name"],
        },
    }
    result = local_paths.get_local_results_dir_from_meta(meta, str(workdir))
    expected = str(
        revdir
        / "results"
        / f"{result_folder_info['simulation_name']} ({result_folder_info['simulation_id']})"
    )
    assert result == expected


def test_get_local_results_dir_from_meta_incomplete():
    """Returns None when meta is missing required fields."""
    meta = {
        "schematisation": {"id": 1, "name": "foo"},
        "simulation": {},  # missing name and id
    }
    result = local_paths.get_local_results_dir_from_meta(meta, "/tmp/fake")
    assert result is None


def test_get_local_results_dir_from_meta_no_local_revision(tmp_path):
    """Returns None when revision doesn't exist locally (create=False)."""
    meta = {
        "schematisation": {"id": 999, "name": "nonexistent", "version": 1},
        "simulation": {"id": 42, "name": "sim"},
    }
    result = local_paths.get_local_results_dir_from_meta(meta, str(tmp_path))
    assert result is None
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
