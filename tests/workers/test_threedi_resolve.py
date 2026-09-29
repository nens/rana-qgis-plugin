from unittest.mock import patch

from rana_qgis_plugin.utils.scenario import ScenarioInfo
from rana_qgis_plugin.workers.threedi_resolve import ScenarioResolveTask


def scenario_info() -> ScenarioInfo:
    return ScenarioInfo(
        {
            "data_type": "scenario",
            "meta": {"simulation": {"id": 42}},
        }
    )


def test_resolves_scenario_metadata():
    info = scenario_info()
    threedi_api = object()
    task = ScenarioResolveTask(info, threedi_api)

    with patch.object(info, "set_simulation_info_from_threedi") as resolve:
        assert task.run()

    resolve.assert_called_once_with(threedi_api)


def test_resolution_failure_degrades_scenario():
    info = scenario_info()
    task = ScenarioResolveTask(info, object())

    with patch.object(
        info, "set_simulation_info_from_threedi", side_effect=RuntimeError
    ):
        assert task.run()

    assert not info.has_3di_simulation


def test_cancellation_skips_resolution():
    info = scenario_info()
    task = ScenarioResolveTask(info, object())
    task.cancel()

    with patch.object(info, "set_simulation_info_from_threedi") as resolve:
        assert not task.run()

    resolve.assert_not_called()
