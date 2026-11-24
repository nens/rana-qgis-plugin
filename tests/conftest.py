from unittest.mock import MagicMock

import pytest
from qgis.core import QgsApplication
from qgis.gui import QgsMessageBar

from rana_qgis_plugin.communication import UICommunication


class _QgsApplicationFactory:
    """Wrapper so pytest-qt's qapp fixture can instantiate QgsApplication correctly.

    pytest-qt calls ``qapp_cls(qapp_args)`` which maps to ``QgsApplication(argv)``,
    but QgsApplication requires a second ``gui`` boolean argument. This factory
    intercepts the call and supplies it.
    """

    def __new__(cls, argv):
        app = QgsApplication(
            [a.encode() if isinstance(a, str) else a for a in argv], True
        )
        return app


@pytest.fixture(scope="session")
def qapp_cls():
    """Use QgsApplication instead of plain QApplication for the whole session."""
    return _QgsApplicationFactory


@pytest.fixture(scope="session")
def qgis_application(qapp):
    """Initialise QGIS on top of the shared QApplication from pytest-qt."""
    qapp.setPrefixPath("/usr", True)
    qapp.initQgis()
    yield qapp
    qapp.processEvents()
    qapp.exitQgis()


@pytest.fixture
def step_bar(qgis_application):
    """A real message-bar progress item: (iface, message_bar, progress_bar)."""
    message_bar = QgsMessageBar()
    iface = MagicMock()
    iface.messageBar.return_value = message_bar
    pb = UICommunication(iface=iface).progress_bar("Preparing", maximum=100)
    return iface, message_bar, pb
