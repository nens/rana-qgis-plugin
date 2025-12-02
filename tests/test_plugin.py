import gc
import os

import pytest
from qgis.core import QgsApplication

from rana_qgis_plugin.communication import UICommunication
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


def test_rana_browser(qgis_application):
    """Test that the RanaBrowser widget can be instantiated"""
    communication = UICommunication()
    widget = RanaBrowser(communication)
    assert widget is not None
