from copy import deepcopy
from unittest.mock import MagicMock, patch

import pytest

import rana_qgis_plugin.utils.scenario as us


@pytest.mark.parametrize(
    "descriptor, expected",
    [
        ({}, False),
        ({"status": None}, False),
        ({"status": {}}, False),
        ({"status": {"id": "completed"}}, True),
        ({"status": {"id": "processing"}}, True),
        ({"status": {"id": "foo"}}, False),
    ],
)
def test_get_ready_state_from_descriptor(descriptor, expected):
    assert us.get_ready_state_from_descriptor(descriptor) == expected


@pytest.mark.parametrize(
    "descriptor, expected",
    [
        ({}, False),
        ({"status": None}, False),
        ({"status": {}}, False),
        ({"status": {"id": "completed"}}, True),
        ({"status": {"id": "processing"}}, False),
        ({"status": {"id": "foo"}}, False),
    ],
)
def test_get_lizard_ready_state_from_descriptor(descriptor, expected):
    assert us.get_lizard_ready_state_from_descriptor(descriptor) == expected


@pytest.mark.parametrize(
    "descriptor, expected",
    [
        ({}, False),
        ({"meta": None}, False),
        ({"meta": {}}, False),
        ({"meta": {"simulation": None}}, False),
        ({"meta": {"simulation": {}}}, False),
        ({"meta": {"simulation": {"software": {}}}}, False),
        ({"meta": {"simulation": {"software": {"id": "foo"}}}}, False),
        ({"meta": {"simulation": {"software": {"id": "3Di"}}}}, False),
    ],
)
def test_get_is_3di_simulation(descriptor, expected):
    assert us.get_is_3di_simulation(descriptor) == expected


class TestScenarioInfo:
    basic_descriptor = {
        "data_type": "scenario",
        "status": {"id": "completed"},
        "meta": {
            "id": 1,
            "simulation": {"software": {"id": "3Di"}},
            "grid": {
                "x": {"origin": 0, "cell_size": 10, "size": 10},
                "y": {"origin": 0, "cell_size": 10, "size": 10},
                "crs": "EPSG:4326",
            },
        },
    }

    def _get_descriptor_copy(self):
        return deepcopy(self.basic_descriptor)

    @pytest.mark.parametrize(
        "descriptor",
        [
            {"data_type": "foo", "meta": {}},
            {"data_type": "scenario"},
        ],
    )
    def test_init_fail(self, descriptor):
        with pytest.raises(AssertionError):
            us.ScenarioInfo(descriptor)

    def test_has_lizard_results(self):
        assert us.ScenarioInfo(self.basic_descriptor).has_lizard_results
        copy_descriptor = self._get_descriptor_copy()
        copy_descriptor["meta"]["id"] = None
        assert not us.ScenarioInfo(copy_descriptor).has_lizard_results

    def _get_complete_descriptor(self):
        descriptor = self._get_descriptor_copy()
        descriptor["meta"]["simulation"] = {"id": 42, "name": "Simulation"}
        descriptor["meta"]["schematisation"] = {
            "id": 7,
            "name": "Schematisation",
            "version": 3,
        }
        return descriptor

    def test_has_complete_simulation_info(self):
        scenario = us.ScenarioInfo(self._get_complete_descriptor())
        assert scenario.has_complete_simulation_info()

    def test_has_complete_simulation_info_can_exclude_simulation_name(self):
        descriptor = self._get_complete_descriptor()
        descriptor["meta"]["simulation"]["name"] = None
        scenario = us.ScenarioInfo(descriptor)
        assert scenario.has_complete_simulation_info(include_simulation_name=False)
        assert not scenario.has_complete_simulation_info()

    def test_needs_threedi_resolution(self):
        incomplete_descriptor = self._get_complete_descriptor()
        incomplete_descriptor["meta"]["schematisation"] = {}
        incomplete_scenario = us.ScenarioInfo(incomplete_descriptor)
        assert incomplete_scenario.needs_threedi_resolution
        complete_scenario = us.ScenarioInfo(self._get_complete_descriptor())
        assert not complete_scenario.needs_threedi_resolution
        unlinked_descriptor = self._get_complete_descriptor()
        unlinked_descriptor["meta"]["simulation"] = {}
        unlinked_scenario = us.ScenarioInfo(unlinked_descriptor)
        assert not unlinked_scenario.needs_threedi_resolution

    def test_construction_does_not_require_threedi_resolution(self):
        descriptor = self._get_descriptor_copy()
        descriptor["meta"]["simulation"]["id"] = 42

        scenario = us.ScenarioInfo(descriptor)

        assert scenario.has_3di_simulation
        assert scenario.simulation_id == 42
        assert scenario.schematisation_id is None

    def _get_tc_mock(
        self, simulation_name, threedimodel_id, threedi_model_name, revision_number
    ):
        simulation = MagicMock()
        simulation.name = simulation_name
        simulation.threedimodel_id = threedimodel_id
        threedimodel = MagicMock()
        threedimodel.name = threedi_model_name
        threedimodel.id = threedimodel_id
        threedimodel.revision_number = revision_number
        calls = MagicMock()
        calls.fetch_simulation.return_value = simulation
        calls.fetch_3di_model.return_value = threedimodel
        return calls

    def test_explicit_threedi_resolution_fills_missing_metadata(self):
        descriptor = self._get_descriptor_copy()
        descriptor["meta"]["simulation"]["id"] = 42
        scenario = us.ScenarioInfo(descriptor)
        calls = self._get_tc_mock("Simulation", 7, "Schematisation", 3)
        with patch.object(us, "ThreediCalls", return_value=calls):
            scenario.set_simulation_info_from_threedi(object())

        assert scenario.has_3di_simulation
        assert scenario.simulation_name == "Simulation"
        assert scenario.schematisation_id == 7
        assert scenario.schematisation_name == "Schematisation"
        assert scenario.revision_number == 3

    def test_explicit_threedi_resolution_incomplete_metadata(self):
        descriptor = self._get_descriptor_copy()
        descriptor["meta"]["simulation"]["id"] = 42
        scenario = us.ScenarioInfo(descriptor)
        calls = self._get_tc_mock(None, 7, "Schematisation", 3)
        with patch.object(us, "ThreediCalls", return_value=calls):
            scenario.set_simulation_info_from_threedi(object())

        assert not scenario.has_3di_simulation

    def test_grid(self):
        assert (
            us.ScenarioInfo(self.basic_descriptor).grid
            == self.basic_descriptor["meta"]["grid"]
        )
        copy_descriptor = self._get_descriptor_copy()
        copy_descriptor["meta"]["grid"] = None
        assert us.ScenarioInfo(copy_descriptor).grid == {}

    def test_get_grid(self):
        grid_copy = us.ScenarioInfo(self.basic_descriptor).get_grid()
        # grid_copy should be different object with the same contents
        assert grid_copy is not self.basic_descriptor["meta"]["grid"]
        assert grid_copy == self.basic_descriptor["meta"]["grid"]

    def test_crs(self):
        assert (
            us.ScenarioInfo(self.basic_descriptor).crs
            == self.basic_descriptor["meta"]["grid"]["crs"]
        )

    def test_pixel_size(self):
        assert us.ScenarioInfo(self.basic_descriptor).pixel_size == 10
        copy_descriptor = self._get_descriptor_copy()
        copy_descriptor["meta"]["grid"]["x"] = {}
        assert us.ScenarioInfo(copy_descriptor).pixel_size == 1
        copy_descriptor["meta"]["grid"]["x"] = None
        assert us.ScenarioInfo(copy_descriptor).pixel_size == 1
        copy_descriptor["meta"]["grid"] = None
        assert us.ScenarioInfo(copy_descriptor).pixel_size == 1
