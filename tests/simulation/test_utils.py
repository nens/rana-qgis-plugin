from unittest.mock import MagicMock, patch

import pytest

from rana_qgis_plugin.simulation.utils import (
    download_required_files,
    handle_csv_header,
    load_local_schematisation,
)


@pytest.fixture
def load_schematisation():
    communication = MagicMock()
    local_schematisation = MagicMock()
    local_schematisation.schematisation_db_filepath = "/tmp/model.gpkg"
    editor = MagicMock()
    with patch(
        "rana_qgis_plugin.simulation.utils.get_plugin_instance", return_value=editor
    ):
        yield communication, local_schematisation, editor


def test_load_local_schematisation_passes_group_name(load_schematisation):
    communication, local_schematisation, editor = load_schematisation
    editor.load_schematisation.return_value = "Canonical name"

    result = load_local_schematisation(
        communication,
        local_schematisation,
        parents=["Project"],
        group_name="Canonical name",
    )

    assert result == "Canonical name"
    editor.load_schematisation.assert_called_once_with(
        "/tmp/model.gpkg", parents=["Project"], group_name="Canonical name"
    )


def test_load_local_schematisation_retries_without_unsupported_group_name(
    load_schematisation,
):
    communication, local_schematisation, editor = load_schematisation
    editor.load_schematisation.side_effect = [
        TypeError("unexpected keyword argument 'group_name'"),
        "Legacy name",
    ]

    result = load_local_schematisation(
        communication,
        local_schematisation,
        parents=["Project"],
        group_name="Canonical name",
    )

    assert result == "Legacy name"
    assert editor.load_schematisation.call_args_list == [
        (
            ("/tmp/model.gpkg",),
            {"parents": ["Project"], "group_name": "Canonical name"},
        ),
        (("/tmp/model.gpkg",), {"parents": ["Project"]}),
    ]
    communication.show_warn.assert_not_called()


def test_load_local_schematisation_retries_path_only_for_legacy_parents_api(
    load_schematisation,
):
    communication, local_schematisation, editor = load_schematisation
    editor.load_schematisation.side_effect = [
        TypeError("unexpected keyword argument 'group_name'"),
        TypeError("unexpected keyword argument 'parents'"),
        "Legacy name",
    ]

    result = load_local_schematisation(
        communication,
        local_schematisation,
        parents=["Project"],
        group_name="Canonical name",
    )

    assert result == "Legacy name"
    assert editor.load_schematisation.call_args_list == [
        (
            ("/tmp/model.gpkg",),
            {"parents": ["Project"], "group_name": "Canonical name"},
        ),
        (("/tmp/model.gpkg",), {"parents": ["Project"]}),
        (("/tmp/model.gpkg",), {}),
    ]
    communication.show_warn.assert_called_once()


def test_load_local_schematisation_reraises_unrelated_type_error(
    load_schematisation,
):
    communication, local_schematisation, editor = load_schematisation
    editor.load_schematisation.side_effect = TypeError("invalid layer state")

    with pytest.raises(TypeError, match="invalid layer state"):
        load_local_schematisation(
            communication,
            local_schematisation,
            parents=["Project"],
            group_name="Canonical name",
        )

    editor.load_schematisation.assert_called_once()


def test_load_local_schematisation_keeps_parents_fallback_without_group_name(
    load_schematisation,
):
    communication, local_schematisation, editor = load_schematisation
    editor.load_schematisation.side_effect = [
        TypeError("unexpected keyword argument 'parents'"),
        "Legacy name",
    ]

    result = load_local_schematisation(
        communication,
        local_schematisation,
        parents=["Project"],
    )

    assert result == "Legacy name"
    editor.load_schematisation.assert_any_call("/tmp/model.gpkg", parents=["Project"])
    editor.load_schematisation.assert_any_call("/tmp/model.gpkg")
    communication.show_warn.assert_called_once()


def test_download_required_files_removes_revision_directory_on_failure(tmp_path):
    local = MagicMock()
    local.revisions = {}
    revision = MagicMock(id=2, number=3)
    revision.sqlite.file.filename = "schema.zip"
    revision.rasters = []
    schematisation = MagicMock(id=1, name="Schema")
    directory = tmp_path / "revision"
    directory.mkdir()

    with (
        patch("rana_qgis_plugin.simulation.utils.ThreediCalls") as calls,
        patch(
            "rana_qgis_plugin.simulation.utils.get_download_file",
            side_effect=RuntimeError("download failed"),
        ),
    ):
        calls.return_value.download_schematisation_revision_sqlite.return_value = (
            MagicMock()
        )
        calls.return_value.fetch_schematisation_revision_3di_models.return_value = []

        with pytest.raises(RuntimeError, match="download failed"):
            download_required_files(
                schematisation, revision, str(directory), local, False, MagicMock()
            )

    assert not directory.exists()


def test_handle_csv_header_accepts_supported_columns():
    assert handle_csv_header(["id", "timeseries"]) is None
    assert handle_csv_header(["timeseries", "id"]) is None


def test_handle_csv_header_rejects_unexpected_columns():
    error = handle_csv_header(["id", "type", "connection_node_id", "timeseries"])

    assert error is not None
    assert "connection_node_id" in error
    assert "type" in error
