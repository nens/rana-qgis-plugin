from typing import cast
from unittest.mock import MagicMock, patch

from rana_qgis_plugin.loader import Loader
from rana_qgis_plugin.simulation.utils import download_required_files
from rana_qgis_plugin.utils.data_models import (
    OpenFileRequest,
    OpenFolderRequest,
    OpenLayerRequest,
    OpenSchematisationRequest,
)


def test_resolve_schematisation_rejects_invalid_metadata():
    communication = MagicMock()
    loader = Loader(communication)
    request = MagicMock()
    request.file_item = {"descriptor_id": "descriptor"}

    with (
        patch(
            "rana_qgis_plugin.loader.get_threedi_schematisation",
            return_value={"schematisation": {"id": 1}},
        ),
        patch("rana_qgis_plugin.loader.resolve_schematisation_download_dir") as resolve,
    ):
        loader.resolve_schematisation(request)

    communication.bar_error.assert_called_once()
    resolve.assert_not_called()


def test_resolve_schematisation_rejects_unwritable_directory():
    communication = MagicMock()
    loader = Loader(communication)
    request = MagicMock()
    request.file_item = {"descriptor_id": "descriptor"}
    metadata = {
        "schematisation": {"id": 1, "name": "Schema"},
        "latest_revision": {"id": 2, "number": 3, "sqlite": {}, "rasters": []},
    }
    with (
        patch(
            "rana_qgis_plugin.loader.get_threedi_schematisation", return_value=metadata
        ),
        patch("rana_qgis_plugin.loader.get_threedi_api", return_value=MagicMock()),
        patch("rana_qgis_plugin.loader.hcc_working_dir", return_value="/tmp"),
        patch(
            "rana_qgis_plugin.loader.resolve_schematisation_download_dir",
            return_value=("/tmp/schema", MagicMock(), False),
        ),
        patch(
            "rana_qgis_plugin.loader.ensure_writable_directory",
            return_value=(False, "permission denied"),
        ),
    ):
        loader.resolve_schematisation(request)

    communication.bar_error.assert_called_once()


def test_save_revision_requires_authenticated_api():
    communication = MagicMock()
    loader = Loader(communication)

    with patch("rana_qgis_plugin.loader.get_threedi_api", return_value=None):
        result = loader.save_revision("project", 1, 1, "/tmp/schema.gpkg", None)

    assert result is None
    communication.bar_error.assert_called_once_with(
        "Not authenticated with 3Di API — cannot save schematisation revision."
    )


def test_open_items_deduplicates_same_file_requests():
    loader = Loader(MagicMock())
    project = {"id": "project"}
    file_item = {"id": "folder/data.gpkg"}
    requests = cast(
        list[
            OpenFileRequest
            | OpenSchematisationRequest
            | OpenLayerRequest
            | OpenFolderRequest
        ],
        [OpenFileRequest(project, file_item), OpenFileRequest(project, file_item)],
    )

    with patch.object(loader, "download_and_open_file") as open_file:
        loader.open_items(requests)

    open_file.assert_called_once_with(requests[0])


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

        try:
            download_required_files(
                schematisation, revision, str(directory), local, False, MagicMock()
            )
        except RuntimeError:
            pass

    assert not directory.exists()
