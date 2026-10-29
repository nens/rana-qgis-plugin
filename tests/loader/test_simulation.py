from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from rana_qgis_plugin.api_error_signals import ApiErrorSignals
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
        loader.start_simulation({}, {}, 1, 2, ApiErrorSignals(), None)

    mkdir.assert_not_called()
    communication.show_warn.assert_called_once_with(
        "Working directory not yet set, please configure this in the plugin settings."
    )


def test_start_simulation_threads_error_signals_to_runner_completion():
    loader = Loader(MagicMock())
    error_signals = ApiErrorSignals()
    task_manager = MagicMock()

    with (
        patch(
            "rana_qgis_plugin.loader.QgsApplication.taskManager",
            return_value=task_manager,
        ),
        patch("rana_qgis_plugin.loader.QSettings") as settings,
        patch("rana_qgis_plugin.loader.SimulationRunner") as runner_factory,
    ):
        settings.return_value.value.return_value = 900
        task = runner_factory.return_value
        loader.start_simulations(
            object(),
            [],
            {"id": "project-id"},
            {"id": "file"},
            parent="parent",
            error_signals=error_signals,
        )

    completion = task.signals.initializing_simulations_finished.connect.call_args.args[
        0
    ]
    with (
        patch.object(loader, "_handle_simulation_initialization_finished"),
        patch.object(loader, "start_simulation_tracker_process") as start,
    ):
        completion("done", ["simulation"])

    start.assert_called_once_with(
        {"id": "project-id"}, {"id": "file"}, ["simulation"], error_signals, "parent"
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
        loader.start_simulation({}, {}, 1, 2, ApiErrorSignals(), None)

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
        loader.start_simulation({}, {}, 1, 2, ApiErrorSignals(), None)

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
        loader.start_simulation({}, {}, 1, 2, ApiErrorSignals(), None)

    calls.fetch_organisations.assert_called_once_with(
        ["12345678-1234-1234-1234-123456789abc"]
    )


def test_start_simulation_tracker_process_starts_trackers_for_simulations():
    communication = MagicMock()
    loader = Loader(communication)
    error_signals = ApiErrorSignals()
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
        patch.object(loader, "point_user_to_processes") as point_user,
    ):
        loader.start_simulation_tracker_process(
            {"id": "project-id", "slug": "project-slug"},
            {"id": "folder/schematisation"},
            simulations,
            error_signals,
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
    point_user.assert_called_once_with(
        {"id": "project-id", "slug": "project-slug"},
        ["job-id"],
        error_signals,
        None,
    )
    communication.bar_info.assert_called_once_with("1 simulation(s) started.")


def test_start_simulation_tracker_process_continues_after_failure():
    communication = MagicMock()
    loader = Loader(communication)
    error_signals = ApiErrorSignals()
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
        patch.object(loader, "point_user_to_processes") as point_user,
    ):
        loader.start_simulation_tracker_process(
            {"id": "project-id", "slug": "project-slug"},
            {"id": "folder/schematisation"},
            simulations,
            error_signals,
        )

    assert start_process.call_count == 2
    communication.log_err.assert_called_once_with(
        "Failed to start simulation tracker: failed"
    )
    point_user.assert_called_once_with(
        {"id": "project-id", "slug": "project-slug"},
        ["job-id"],
        error_signals,
        None,
    )
    communication.bar_info.assert_called_once_with("1 simulation(s) started.")


def test_start_simulation_tracker_process_handles_process_lookup_failure():
    communication = MagicMock()
    loader = Loader(communication)
    error = RanaFetchError("failed to fetch", "https://example.test", {})

    with patch(
        "rana_qgis_plugin.loader.get_process_id_for_tag", side_effect=error
    ) as get_process:
        loader.start_simulation_tracker_process({}, {}, [], ApiErrorSignals())

    get_process.assert_called_once_with("simulation_tracker")
    communication.bar_error.assert_called_once_with(
        "Failed to retrieve simulation tracker process: failed to fetch"
    )
    communication.log_err.assert_called_once_with(str(error))


def test_point_user_to_processes_asks_then_opens_and_highlights():
    communication = MagicMock()
    communication.ask.return_value = True
    loader = Loader(communication)
    project = {"id": "project-id", "name": "Project", "slug": "project"}
    error_signals = ApiErrorSignals()
    dock = MagicMock()
    dock.isFloating.return_value = True

    with patch.object(loader, "open_processes_dock", return_value=dock) as open_dock:
        loader.point_user_to_processes(project, ["job-id"], error_signals, "parent")

    communication.ask.assert_called_once_with(
        "parent", "Processes", "Track progress in the Processes window?"
    )
    open_dock.assert_called_once_with(project, error_signals)
    dock.widget.return_value.highlight_jobs.assert_called_once_with(["job-id"])
    dock.raise_.assert_called_once_with()
    dock.activateWindow.assert_called_once_with()


def test_point_user_to_processes_decline_does_not_open_dock():
    communication = MagicMock()
    communication.ask.return_value = False
    loader = Loader(communication)

    with patch.object(loader, "open_processes_dock") as open_dock:
        loader.point_user_to_processes(
            {"id": "project-id"}, ["job-id"], ApiErrorSignals()
        )

    open_dock.assert_not_called()


def test_point_user_to_processes_raises_open_docked_panel_and_notifies():
    communication = MagicMock()
    loader = Loader(communication)
    dock = MagicMock()
    dock.isFloating.return_value = False
    loader.process_docks["project-id"] = dock

    loader.point_user_to_processes({"id": "project-id"}, ["job-id"], ApiErrorSignals())

    dock.raise_.assert_called_once_with()
    dock.activateWindow.assert_not_called()
    dock.widget.return_value.highlight_jobs.assert_called_once_with(["job-id"])
    communication.bar_info.assert_called_once_with(
        "See the Processes panel for progress."
    )
