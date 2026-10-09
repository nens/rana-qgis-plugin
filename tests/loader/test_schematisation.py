from typing import cast
from unittest.mock import MagicMock, patch

from qgis.PyQt.QtWidgets import QDialog

from rana_qgis_plugin.loader import Loader
from rana_qgis_plugin.simulation.utils import download_required_files
from rana_qgis_plugin.utils.api import RanaPostError
from rana_qgis_plugin.utils.data_models import (
    OpenFileRequest,
    OpenFolderRequest,
    OpenLayersRequest,
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


def test_import_schematisation_from_hcc_requires_authenticated_api():
    communication = MagicMock()
    loader = Loader(communication)

    with patch("rana_qgis_plugin.loader.get_threedi_api", return_value=None):
        result = loader.import_schematisation_from_hcc(
            {"id": "project"}, "folder/", None, refresh_callback=MagicMock()
        )

    assert result is None
    communication.show_warn.assert_called_once_with(
        "Not authenticated with 3Di API — cannot import from HCC."
    )


def test_upload_existing_cancelled_file_picker_stops_before_authentication():
    communication = MagicMock()
    loader = Loader(communication)

    with (
        patch("rana_qgis_plugin.loader.get_filepath", return_value=None),
        patch("rana_qgis_plugin.loader.get_threedi_api") as get_api,
    ):
        result = loader.upload_existing_schematisation(
            {"id": "project"}, "folder/", None, MagicMock()
        )

    assert result is None
    get_api.assert_not_called()


def test_upload_existing_cancelled_wizard_stops_before_upload():
    communication = MagicMock()
    loader = Loader(communication)
    api = MagicMock()
    organisation = MagicMock(unique_id="org-1")

    with (
        patch("rana_qgis_plugin.loader.get_filepath", return_value="/tmp/input.gpkg"),
        patch("rana_qgis_plugin.loader.get_threedi_api", return_value=api),
        patch(
            "rana_qgis_plugin.loader.get_threedi_organisations", return_value=["org-1"]
        ),
        patch("rana_qgis_plugin.loader.ThreediCalls") as calls_type,
        patch("rana_qgis_plugin.loader.hcc_working_dir", return_value="/tmp/models"),
        patch(
            "rana_qgis_plugin.loader.UploadExistingSchematisationWizard"
        ) as wizard_type,
        patch.object(loader, "save_initial_revision") as upload_initial,
    ):
        calls_type.return_value.fetch_organisations.return_value = [organisation]
        wizard_type.return_value.exec.return_value = QDialog.DialogCode.Rejected

        result = loader.upload_existing_schematisation(
            {"id": "project"}, "folder/", None, MagicMock()
        )

    assert result is None
    upload_initial.assert_not_called()


def test_upload_existing_preparation_failure_does_not_upload_or_report_success():
    communication = MagicMock()
    loader = Loader(communication)
    api = MagicMock()
    organisation = MagicMock(unique_id="org-1")

    with (
        patch("rana_qgis_plugin.loader.get_filepath", return_value="/tmp/input.gpkg"),
        patch("rana_qgis_plugin.loader.get_threedi_api", return_value=api),
        patch(
            "rana_qgis_plugin.loader.get_threedi_organisations", return_value=["org-1"]
        ),
        patch("rana_qgis_plugin.loader.ThreediCalls") as calls_type,
        patch("rana_qgis_plugin.loader.hcc_working_dir", return_value="/tmp/models"),
        patch(
            "rana_qgis_plugin.loader.UploadExistingSchematisationWizard"
        ) as wizard_type,
        patch.object(loader, "save_initial_revision") as upload_initial,
    ):
        calls_type.return_value.fetch_organisations.return_value = [organisation]
        wizard = wizard_type.return_value
        wizard.exec.return_value = QDialog.DialogCode.Accepted
        wizard.new_schematisation = None
        wizard.new_local_schematisation = None

        result = loader.upload_existing_schematisation(
            {"id": "project"}, "folder/", None, MagicMock()
        )

    assert result is None
    upload_initial.assert_not_called()
    communication.bar_info.assert_not_called()


def test_import_schematisation_from_hcc_copies_selected_revision_and_refreshes():
    communication = MagicMock()
    loader = Loader(communication)
    schematisation = {"id": "source-schema", "name": "My model"}
    revision = MagicMock(id=31, number=4)
    refresh_callback = MagicMock()

    with (
        patch("rana_qgis_plugin.loader.get_threedi_api", return_value=MagicMock()),
        patch("rana_qgis_plugin.loader.SchematisationBrowser") as dialog_type,
        patch("rana_qgis_plugin.loader.copy_threedi_schematisation") as copy_schema,
    ):
        dialog = dialog_type.return_value
        dialog.exec.return_value = 1
        dialog.selected_schematisation = schematisation
        dialog.selected_revision = revision
        loader.import_schematisation_from_hcc(
            {"id": "project"},
            "folder/",
            None,
            refresh_callback=refresh_callback,
        )

    copy_schema.assert_called_once_with(
        project_id="project",
        schematisation_id="source-schema",
        revision_id=31,
        path="folder/My model_#4",
    )
    refresh_callback.assert_called_once_with()
    communication.show_error.assert_not_called()


def test_import_schematisation_from_hcc_does_not_refresh_when_copy_fails():
    communication = MagicMock()
    loader = Loader(communication)
    refresh_callback = MagicMock()
    error = RanaPostError("copy failed", "url", {})

    with (
        patch("rana_qgis_plugin.loader.get_threedi_api", return_value=MagicMock()),
        patch("rana_qgis_plugin.loader.SchematisationBrowser") as dialog_type,
        patch(
            "rana_qgis_plugin.loader.copy_threedi_schematisation",
            side_effect=error,
        ) as copy_schema,
    ):
        dialog = dialog_type.return_value
        dialog.exec.return_value = 1
        dialog.selected_schematisation = {"id": "source-schema", "name": "My model"}
        dialog.selected_revision = MagicMock(id=31, number=4)
        loader.import_schematisation_from_hcc(
            {"id": "project"},
            "folder/",
            None,
            refresh_callback=refresh_callback,
        )

    copy_schema.assert_called_once()
    communication.show_error.assert_called_once_with(str(error), parent=None)
    refresh_callback.assert_not_called()


def test_upload_existing_wizard_hands_prepared_result_to_initial_upload():
    communication = MagicMock()
    loader = Loader(communication)
    project = {"id": "project"}
    refresh_callback = MagicMock()
    api = MagicMock()
    organisation = MagicMock(unique_id="org-1")
    schematisation = MagicMock()
    local_schematisation = MagicMock()
    raster_paths = {"model_settings": {"dem_file": "dem.tif"}}
    task = MagicMock()

    with (
        patch("rana_qgis_plugin.loader.get_filepath", return_value="/tmp/input.gpkg"),
        patch("rana_qgis_plugin.loader.get_threedi_api", return_value=api),
        patch(
            "rana_qgis_plugin.loader.get_threedi_organisations",
            return_value=["org-1"],
        ),
        patch("rana_qgis_plugin.loader.ThreediCalls") as calls_type,
        patch("rana_qgis_plugin.loader.hcc_working_dir", return_value="/tmp/models"),
        patch(
            "rana_qgis_plugin.loader.UploadExistingSchematisationWizard"
        ) as wizard_type,
        patch.object(
            loader, "save_initial_revision", return_value=task
        ) as save_initial,
    ):
        calls_type.return_value.fetch_organisations.return_value = [organisation]
        wizard = wizard_type.return_value
        wizard.exec.return_value = 1
        wizard.new_schematisation = schematisation
        wizard.new_local_schematisation = local_schematisation
        wizard.raster_paths = raster_paths

        result = loader.upload_existing_schematisation(
            project, "target/", None, refresh_callback
        )

    assert result is task
    wizard_type.assert_called_once_with(
        api,
        "/tmp/models",
        communication,
        {"org-1": organisation},
        "/tmp/input.gpkg",
        "project",
        "target/",
    )
    save_initial.assert_called_once_with(
        project,
        schematisation,
        local_schematisation,
        raster_paths,
        refresh_callback,
    )


def test_upload_existing_cancel_does_not_start_initial_upload():
    communication = MagicMock()
    loader = Loader(communication)
    api = MagicMock()
    organisation = MagicMock(unique_id="org-1")

    with (
        patch("rana_qgis_plugin.loader.get_filepath", return_value="/tmp/input.gpkg"),
        patch("rana_qgis_plugin.loader.get_threedi_api", return_value=api),
        patch(
            "rana_qgis_plugin.loader.get_threedi_organisations",
            return_value=["org-1"],
        ),
        patch("rana_qgis_plugin.loader.ThreediCalls") as calls_type,
        patch("rana_qgis_plugin.loader.hcc_working_dir", return_value="/tmp/models"),
        patch(
            "rana_qgis_plugin.loader.UploadExistingSchematisationWizard"
        ) as wizard_type,
        patch.object(loader, "save_initial_revision") as save_initial,
    ):
        calls_type.return_value.fetch_organisations.return_value = [organisation]
        wizard_type.return_value.exec.return_value = 0

        result = loader.upload_existing_schematisation(
            {"id": "project"}, "target/", None, MagicMock()
        )

    assert result is None
    save_initial.assert_not_called()


def test_upload_existing_rejected_registration_does_not_start_initial_upload():
    communication = MagicMock()
    loader = Loader(communication)
    api = MagicMock()
    organisation = MagicMock(unique_id="org-1")

    with (
        patch("rana_qgis_plugin.loader.get_filepath", return_value="/tmp/input.gpkg"),
        patch("rana_qgis_plugin.loader.get_threedi_api", return_value=api),
        patch(
            "rana_qgis_plugin.loader.get_threedi_organisations",
            return_value=["org-1"],
        ),
        patch("rana_qgis_plugin.loader.ThreediCalls") as calls_type,
        patch("rana_qgis_plugin.loader.hcc_working_dir", return_value="/tmp/models"),
        patch(
            "rana_qgis_plugin.loader.UploadExistingSchematisationWizard"
        ) as wizard_type,
        patch.object(loader, "save_initial_revision") as save_initial,
    ):
        calls_type.return_value.fetch_organisations.return_value = [organisation]
        wizard = wizard_type.return_value
        wizard.exec.return_value = 1
        wizard.new_schematisation = None
        wizard.new_local_schematisation = None

        result = loader.upload_existing_schematisation(
            {"id": "project"}, "target/", None, MagicMock()
        )

    assert result is None
    save_initial.assert_not_called()
    communication.show_error.assert_called_once()


def test_from_scratch_cancelled_wizard_stops_before_upload():
    communication = MagicMock()
    loader = Loader(communication)
    api = MagicMock()
    organisation = MagicMock(unique_id="org-1")

    with (
        patch("rana_qgis_plugin.loader.get_threedi_api", return_value=api),
        patch(
            "rana_qgis_plugin.loader.get_threedi_organisations",
            return_value=["org-1"],
        ),
        patch("rana_qgis_plugin.loader.ThreediCalls") as calls_type,
        patch("rana_qgis_plugin.loader.hcc_working_dir", return_value="/tmp/models"),
        patch("rana_qgis_plugin.loader.NewSchematisationWizard") as wizard_type,
        patch.object(loader, "save_initial_revision") as save_initial,
    ):
        calls_type.return_value.fetch_organisations.return_value = [organisation]
        wizard_type.return_value.exec.return_value = QDialog.DialogCode.Rejected

        result = loader.create_schematisation_from_scratch(
            {"id": "project"}, "folder/", None, MagicMock()
        )

    assert result is None
    save_initial.assert_not_called()


def test_from_scratch_preparation_failure_does_not_upload_or_report_success():
    communication = MagicMock()
    loader = Loader(communication)
    api = MagicMock()
    organisation = MagicMock(unique_id="org-1")

    with (
        patch("rana_qgis_plugin.loader.get_threedi_api", return_value=api),
        patch(
            "rana_qgis_plugin.loader.get_threedi_organisations",
            return_value=["org-1"],
        ),
        patch("rana_qgis_plugin.loader.ThreediCalls") as calls_type,
        patch("rana_qgis_plugin.loader.hcc_working_dir", return_value="/tmp/models"),
        patch("rana_qgis_plugin.loader.NewSchematisationWizard") as wizard_type,
        patch.object(loader, "save_initial_revision") as save_initial,
    ):
        calls_type.return_value.fetch_organisations.return_value = [organisation]
        wizard = wizard_type.return_value
        wizard.exec.return_value = QDialog.DialogCode.Accepted
        wizard.new_schematisation = None
        wizard.new_local_schematisation = None

        result = loader.create_schematisation_from_scratch(
            {"id": "project"}, "folder/", None, MagicMock()
        )

    assert result is None
    save_initial.assert_not_called()
    communication.bar_info.assert_not_called()


def test_from_scratch_wizard_hands_prepared_result_to_initial_upload():
    communication = MagicMock()
    loader = Loader(communication)
    project = {"id": "project"}
    refresh_callback = MagicMock()
    api = MagicMock()
    organisation = MagicMock(unique_id="org-1")
    schematisation = MagicMock()
    local_schematisation = MagicMock()
    raster_paths = {"model_settings": {"dem_file": "dem.tif"}}
    task = MagicMock()

    with (
        patch("rana_qgis_plugin.loader.get_threedi_api", return_value=api),
        patch(
            "rana_qgis_plugin.loader.get_threedi_organisations",
            return_value=["org-1"],
        ),
        patch("rana_qgis_plugin.loader.ThreediCalls") as calls_type,
        patch("rana_qgis_plugin.loader.hcc_working_dir", return_value="/tmp/models"),
        patch("rana_qgis_plugin.loader.NewSchematisationWizard") as wizard_type,
        patch.object(
            loader, "save_initial_revision", return_value=task
        ) as save_initial,
    ):
        calls_type.return_value.fetch_organisations.return_value = [organisation]
        wizard = wizard_type.return_value
        wizard.exec.return_value = QDialog.DialogCode.Accepted
        wizard.new_schematisation = schematisation
        wizard.new_local_schematisation = local_schematisation
        wizard.raster_paths = raster_paths

        result = loader.create_schematisation_from_scratch(
            project, "target/", None, refresh_callback
        )

    assert result is task
    wizard_type.assert_called_once_with(
        api,
        "/tmp/models",
        communication,
        {"org-1": organisation},
        "project",
        "target/",
    )
    save_initial.assert_called_once_with(
        project,
        schematisation,
        local_schematisation,
        raster_paths,
        refresh_callback,
    )


def test_open_items_deduplicates_same_file_requests():
    loader = Loader(MagicMock())
    project = {"id": "project"}
    file_item = {"id": "folder/data.gpkg"}
    requests = cast(
        list[
            OpenFileRequest
            | OpenSchematisationRequest
            | OpenLayersRequest
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
