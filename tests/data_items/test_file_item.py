from unittest.mock import MagicMock, patch

from qgis.core import Qgis, QgsDataItem

from rana_qgis_plugin.api_error_signals import ApiErrorSignals
from rana_qgis_plugin.data_items.file_item import RanaFileDataItem
from rana_qgis_plugin.utils.data_models import OpenScenarioRequest


def test_double_click_opens_single_scenario_results(qgis_application):
    loader = MagicMock()
    project = {"id": "project", "name": "Project", "slug": "project"}
    file_item = {
        "id": "scenario.json",
        "descriptor_id": "descriptor",
        "data_type": "scenario",
    }
    parent = QgsDataItem(Qgis.BrowserItemType.Custom, None, "Rana", "Rana")
    item = RanaFileDataItem(
        parent,
        loader,
        project,
        file_item,
        "scenario.json",
        ApiErrorSignals(),
    )

    with patch.object(loader, "open_scenario_results") as open_results:
        assert item.handleDoubleClick()

    open_results.assert_called_once_with(OpenScenarioRequest(project, file_item))
