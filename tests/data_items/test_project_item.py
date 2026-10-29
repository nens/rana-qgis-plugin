from unittest.mock import MagicMock

from qgis.core import Qgis, QgsDataItem
from qgis.PyQt.QtWidgets import QWidget

from rana_qgis_plugin.api_error_signals import ApiErrorSignals
from rana_qgis_plugin.data_items.project_item import RanaProjectDataItem


def test_processes_action_opens_dock_for_project(qgis_application):
    loader = MagicMock()
    project = {"id": "project-1", "name": "Project", "slug": "project"}
    error_signals = ApiErrorSignals()
    parent = QgsDataItem(Qgis.BrowserItemType.Custom, None, "Rana", "Rana")
    item = RanaProjectDataItem(parent, loader, project, error_signals)
    action_parent = QWidget()

    actions = item.actions(action_parent)
    processes_action = next(
        action for action in actions if action.text() == "Processes"
    )
    processes_action.trigger()

    loader.open_processes_dock.assert_called_once_with(project, error_signals)
