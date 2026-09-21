from unittest.mock import MagicMock

from rana_qgis_plugin.loader import Loader
from rana_qgis_plugin.utils.data_models import OpenScenarioRequest


def make_loader() -> tuple[Loader, MagicMock]:
    communication = MagicMock()
    return Loader(communication), communication


def scenario_request() -> OpenScenarioRequest:
    return OpenScenarioRequest(
        project={"id": "project", "name": "Project", "slug": "project"},
        file_item={
            "id": "scenario.json",
            "descriptor_id": "descriptor",
            "data_type": "scenario",
        },
    )


def scenario_descriptor(simulation: dict, scenario_id: int | None = 1) -> dict:
    return {
        "data_type": "scenario",
        "status": {"id": "completed"},
        "meta": {
            "id": scenario_id,
            "simulation": simulation,
            "grid": {
                "x": {"cell_size": 10},
                "crs": "EPSG:4326",
            },
        },
    }


def linked_descriptor() -> dict:
    descriptor = scenario_descriptor({"id": 42, "name": "Simulation"})
    descriptor["meta"]["schematisation"] = {
        "id": 7,
        "name": "Schematisation",
        "version": 3,
    }
    return descriptor
