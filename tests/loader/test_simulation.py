from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from rana_qgis_plugin.loader import Loader
from rana_qgis_plugin.utils.api import RanaFetchError, RanaPostError


def make_revision_metadata() -> dict:
    return {"schematisation_id": 1, "revision_id": 2}


def test_start_simulation_requires_working_directory():
    communication = MagicMock()
    loader = Loader(communication)

    with (
        patch("rana_qgis_plugin.loader.Path.mkdir") as mkdir,
        patch("rana_qgis_plugin.loader.hcc_working_dir", return_value=""),
    ):
        loader.start_simulation({}, {}, 1, 2, None)

    mkdir.assert_not_called()
    communication.show_warn.assert_called_once_with(
        "Working directory not yet set, please configure this in the plugin settings."
    )


def test_start_simulation_requires_organisations():
    communication = MagicMock()
    loader = Loader(communication)
    calls = MagicMock()

    with (
        patch("rana_qgis_plugin.loader.hcc_working_dir", return_value="/tmp"),
        patch("rana_qgis_plugin.loader.get_threedi_api", return_value=MagicMock()),
        patch("rana_qgis_plugin.loader.ThreediCalls", return_value=calls),
        patch("rana_qgis_plugin.loader.get_threedi_organisations", return_value=[]),
    ):
        calls.fetch_organisations.return_value = []
        loader.start_simulation({}, {}, 1, 2, None)

    communication.show_warn.assert_called_once_with(
        "No organisation available for this simulation"
    )


def test_start_simulation_requires_valid_model():
    communication = MagicMock()
    loader = Loader(communication)
    calls = MagicMock()

    with (
        patch("rana_qgis_plugin.loader.hcc_working_dir", return_value="/tmp"),
        patch("rana_qgis_plugin.loader.get_threedi_api", return_value=MagicMock()),
        patch("rana_qgis_plugin.loader.ThreediCalls", return_value=calls),
        patch("rana_qgis_plugin.loader.get_threedi_organisations", return_value=[]),
    ):
        calls.fetch_organisations.return_value = [MagicMock()]
        calls.fetch_schematisation_revision_3di_models.return_value = []
        loader.start_simulation({}, {}, 1, 2, None)

    communication.show_warn.assert_called_once_with(
        "No enabled valid model for this schematisation revision"
    )


def test_start_simulation_preserves_organisation_uuid_format():
    communication = MagicMock()
    loader = Loader(communication)
    calls = MagicMock()
    organisation = MagicMock(unique_id="12345678-1234-1234-1234-123456789abc")
    model = MagicMock(disabled=False, is_valid=False)

    with (
        patch("rana_qgis_plugin.loader.hcc_working_dir", return_value="/tmp"),
        patch("rana_qgis_plugin.loader.get_threedi_api", return_value=MagicMock()),
        patch("rana_qgis_plugin.loader.ThreediCalls", return_value=calls),
        patch(
            "rana_qgis_plugin.loader.get_threedi_organisations",
            return_value=["12345678-1234-1234-1234-123456789abc"],
        ),
    ):
        calls.fetch_organisations.return_value = [organisation]
        calls.fetch_schematisation_revision_3di_models.return_value = [model]
        loader.start_simulation({}, {}, 1, 2, None)

    calls.fetch_organisations.assert_called_once_with(
        ["12345678-1234-1234-1234-123456789abc"]
    )


def test_start_simulation_tracker_process_starts_trackers_for_simulations():
    communication = MagicMock()
    loader = Loader(communication)
    simulations = [
        SimpleNamespace(
            simulation=SimpleNamespace(
                id_to_start="simulation-to-start",
                name="Test simulation",
                id="simulation-id",
            )
        )
    ]

    with (
        patch(
            "rana_qgis_plugin.loader.get_process_id_for_tag",
            return_value="simulation-tracker",
        ),
        patch(
            "rana_qgis_plugin.loader.start_tenant_process",
            return_value={"job_id": "job-id"},
        ) as start_process,
        patch(
            "rana_qgis_plugin.loader.get_rana_processes_url",
            return_value="https://example.test/process",
        ),
        patch("rana_qgis_plugin.loader.QMessageBox.information") as show_popup,
    ):
        loader.start_simulation_tracker_process(
            {"id": "project-id", "slug": "project-slug"},
            {"id": "folder/schematisation"},
            simulations,
        )

    start_process.assert_called_once_with(
        "simulation-tracker",
        {
            "project_id": "project-id",
            "inputs": {"simulation_id": "simulation-to-start"},
            "outputs": {
                "results": {"id": "folder/Test simulation_simulation-id_results.zip"}
            },
            "name": "Test simulation",
        },
    )
    show_popup.assert_called_once_with(
        None,
        "Rana simulation",
        '<a href="https://example.test/process">Track simulation Test simulation in Rana</a>',
    )


def test_start_simulation_tracker_process_continues_after_failure():
    communication = MagicMock()
    loader = Loader(communication)
    simulations = [
        SimpleNamespace(
            simulation=SimpleNamespace(
                id_to_start=f"simulation-to-start-{index}",
                name=f"Test simulation {index}",
                id=f"simulation-id-{index}",
            )
        )
        for index in range(2)
    ]

    with (
        patch(
            "rana_qgis_plugin.loader.get_process_id_for_tag",
            return_value="simulation-tracker",
        ),
        patch(
            "rana_qgis_plugin.loader.start_tenant_process",
            side_effect=[RanaPostError("failed", "", {}), {"id": "job-id"}],
        ) as start_process,
        patch(
            "rana_qgis_plugin.loader.get_rana_processes_url",
            return_value="https://example.test/process",
        ),
        patch("rana_qgis_plugin.loader.QMessageBox.information") as show_popup,
    ):
        loader.start_simulation_tracker_process(
            {"id": "project-id", "slug": "project-slug"},
            {"id": "folder/schematisation"},
            simulations,
        )

    assert start_process.call_count == 2
    communication.log_err.assert_called_once_with(
        "Failed to start simulation tracker: failed"
    )
    show_popup.assert_called_once_with(
        None,
        "Rana simulation",
        '<a href="https://example.test/process">Track simulation Test simulation 1 in Rana</a>',
    )


def test_start_simulation_tracker_process_handles_process_lookup_failure():
    communication = MagicMock()
    loader = Loader(communication)
    error = RanaFetchError("failed to fetch", "https://example.test", {})

    with patch(
        "rana_qgis_plugin.loader.get_process_id_for_tag", side_effect=error
    ) as get_process:
        loader.start_simulation_tracker_process({}, {}, [])

    get_process.assert_called_once_with("simulation_tracker")
    communication.bar_error.assert_called_once_with(
        "Failed to retrieve simulation tracker process: failed to fetch"
    )
    communication.log_err.assert_called_once_with(str(error))
