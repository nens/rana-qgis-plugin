import pytest
from qgis.core import QgsApplication


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
