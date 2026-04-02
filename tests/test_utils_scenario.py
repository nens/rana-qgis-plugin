from copy import deepcopy

import pytest

import rana_qgis_plugin.utlis.scenario as us


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
