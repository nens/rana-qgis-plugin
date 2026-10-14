import gc
import os
from unittest.mock import MagicMock, patch

import pytest
from qgis.core import QgsApplication
from qgis.PyQt.QtWidgets import QComboBox, QDialog

from rana_qgis_plugin.communication import UICommunication
from rana_qgis_plugin.rana_qgis_plugin import RanaQgisPlugin
from rana_qgis_plugin.widgets.rana_browser import RanaBrowser


@pytest.fixture(scope="session")
def qgis_application() -> QgsApplication:
    """QGIS app without processing providers"""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    qgs = QgsApplication([], False)
    qgs.initQgis()
    yield qgs
    gc.collect()
    qgs.exitQgis()
    gc.collect()


@pytest.fixture
def plugin():
    plugin = RanaQgisPlugin.__new__(RanaQgisPlugin)
    plugin.iface = MagicMock()
    plugin.iface.mainWindow.return_value = None
    plugin.tenants = [
        {"name": "R&D", "id": "org-1"},
        {"name": "Water Board", "id": "org-2"},
    ]
    plugin.communication = MagicMock()
    plugin.rana_browser = MagicMock()
    return plugin


@pytest.fixture
def dialog(qgis_application):
    dialog = MagicMock()
    dialog.organisations_box = QComboBox()
    return dialog


def test_rana_browser(qgis_application):
    """Test that the RanaBrowser widget can be instantiated"""
    communication = UICommunication()
    widget = RanaBrowser(communication)
    assert widget is not None


def test_tenant_selection_dialog_switches_selected_tenant(plugin, dialog):
    def select_first_tenant():
        dialog.organisations_box.setCurrentIndex(0)
        return QDialog.DialogCode.Accepted

    dialog.exec.side_effect = select_first_tenant
    with (
        patch(
            "rana_qgis_plugin.rana_qgis_plugin.TenantSelectionDialog",
            return_value=dialog,
        ),
        patch(
            "rana_qgis_plugin.rana_qgis_plugin.get_tenant_id",
            return_value="org-2",
        ),
        patch("rana_qgis_plugin.rana_qgis_plugin.set_tenant_id") as set_tenant_id,
    ):
        plugin.open_tenant_selection_dialog()

    assert dialog.organisations_box.itemText(0) == "R&D (org-1)"
    assert dialog.organisations_box.itemData(0) == "org-1"
    assert dialog.organisations_box.itemText(1) == "Water Board (org-2)"
    assert dialog.organisations_box.itemData(1) == "org-2"
    assert set_tenant_id.call_args.args == ("org-1",)
    plugin.communication.bar_info.assert_called_once_with("Organisation set to: org-1")
    plugin.rana_browser.reset.assert_called_once_with()


def test_tenant_selection_dialog_keeps_current_tenant_when_accepted_without_change(
    plugin, dialog
):
    dialog.exec.return_value = QDialog.DialogCode.Accepted

    with (
        patch(
            "rana_qgis_plugin.rana_qgis_plugin.TenantSelectionDialog",
            return_value=dialog,
        ),
        patch(
            "rana_qgis_plugin.rana_qgis_plugin.get_tenant_id",
            return_value="org-2",
        ),
        patch("rana_qgis_plugin.rana_qgis_plugin.set_tenant_id") as set_tenant_id,
    ):
        plugin.open_tenant_selection_dialog()

    assert dialog.organisations_box.currentData() == "org-2"
    set_tenant_id.assert_not_called()
    plugin.communication.bar_info.assert_not_called()
    plugin.rana_browser.reset.assert_not_called()


def test_tenant_selection_dialog_keeps_current_tenant_when_rejected_after_change(
    plugin, dialog
):
    def select_first_tenant_and_reject():
        dialog.organisations_box.setCurrentIndex(0)
        return QDialog.DialogCode.Rejected

    dialog.exec.side_effect = select_first_tenant_and_reject

    with (
        patch(
            "rana_qgis_plugin.rana_qgis_plugin.TenantSelectionDialog",
            return_value=dialog,
        ),
        patch(
            "rana_qgis_plugin.rana_qgis_plugin.get_tenant_id",
            return_value="org-2",
        ),
        patch("rana_qgis_plugin.rana_qgis_plugin.set_tenant_id") as set_tenant_id,
    ):
        plugin.open_tenant_selection_dialog()

    assert dialog.organisations_box.currentData() == "org-1"
    set_tenant_id.assert_not_called()
    plugin.communication.bar_info.assert_not_called()
    plugin.rana_browser.reset.assert_not_called()
