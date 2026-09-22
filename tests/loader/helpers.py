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
