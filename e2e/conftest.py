import gc
import os
from unittest.mock import Mock, patch

# Patch get_user_info to always return a test user using unittest.mock.patch
import pytest
from qgis.core import QgsApplication, QgsAuthMethodConfig, QgsProject
from qgis.gui import QgsMapCanvas
from qgis.PyQt.QtCore import QObject, QTimer, QUrl, pyqtSignal
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import (
    QAction,
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QToolBar,
)

import rana_qgis_plugin.utils_api as utils_api
from rana_qgis_plugin.auth_3di import set_3di_auth
from rana_qgis_plugin.constant import RANA_SETTINGS_ENTRY
from rana_qgis_plugin.rana_qgis_plugin import RanaQgisPlugin
from rana_qgis_plugin.utils_settings import set_base_url


@pytest.fixture(autouse=True)
def mock_get_user_info():
    with patch("rana_qgis_plugin.rana_qgis_plugin.get_user_info") as mock:
        mock.return_value = utils_api.UserInfo(
            sub="test_user",
            given_name="test",
            family_name="user",
            email="test_user@test.com",
        )
        yield


@pytest.fixture(autouse=True)
def mock_get_user_info_2():
    with patch("rana_qgis_plugin.widgets.projects_browser.get_user_info") as mock:
        mock.return_value = utils_api.UserInfo(
            sub="test_user",
            given_name="test",
            family_name="user",
            email="test_user@test.com",
        )
        yield


@pytest.fixture(autouse=True)
def mock_get_user_tenants():
    with patch("rana_qgis_plugin.rana_qgis_plugin.get_user_tenants") as mock_tenants:
        mock_tenants.return_value = [
            {
                "id": "nenstest",
                "name": "Nelen & Schuurmans Test",
                "identity_providers": [
                    {
                        "id": "NelenSchuurmans",
                        "name": "Nelen & Schuurmans",
                        "type": "azure",
                    }
                ],
                "threedi_organisations": [os.getenv("ORG_3DI", "")],
                "created_at": "2025-11-25T08:37:42.095140Z",
                "updated_at": "2026-02-16T08:02:51.288248Z",
                "description": "Test org",
                "license": "pioneer",
            }
        ]
        yield


@pytest.fixture(scope="session")
def qgis_application() -> QgsApplication:
    """QGIS app for testing with GUI"""
    QgsApplication.setPrefixPath("/usr", True)
    qgs = QgsApplication([], True)
    qgs.initQgis()
    yield qgs

    qgs.processEvents()
    gc.collect()
    qgs.exitQgis()
    gc.collect()


@pytest.fixture
def qgis_iface(qgis_application):
    """Real QGIS interface with visible windows"""
    # Create real main window
    main_window = QMainWindow()
    main_window.setWindowTitle("QGIS Test Window")
    main_window.resize(1200, 800)

    # Add plugin menu storage to main window
    main_window._plugin_menus = {}

    # Add getPluginMenu method to main window
    def get_plugin_menu(name):
        if name not in main_window._plugin_menus:
            plugin_menu = QMenu(name, main_window)
            main_window.menuBar().addMenu(plugin_menu)
            main_window._plugin_menus[name] = plugin_menu
        return main_window._plugin_menus[name]

    main_window.getPluginMenu = get_plugin_menu
    main_window.show()

    # Create mock iface with real GUI components
    iface = Mock()
    iface.mainWindow.return_value = main_window

    # Create real map canvas
    canvas = QgsMapCanvas(main_window)
    main_window.setCentralWidget(canvas)
    iface.mapCanvas.return_value = canvas

    # Create real message bar
    message_bar = QMessageBox(main_window)
    iface.messageBar.return_value = message_bar
    # Add clearWidgets method to message bar mock
    message_bar.clearWidgets = Mock()
    message_bar.pushMessage = Mock()

    # Mock toolbar - returns real toolbar
    def add_toolbar(name):
        toolbar = QToolBar(name, main_window)
        main_window.addToolBar(toolbar)
        return toolbar

    iface.addToolBar.side_effect = add_toolbar
    iface.removeToolBarIcon.return_value = None

    # Real dock widget methods
    def add_dock_widget(area, widget):
        main_window.addDockWidget(area, widget)

    def add_tabified_dock_widget(area, widget, raiseTab=False):
        main_window.addDockWidget(area, widget)
        if raiseTab:
            widget.raise_()

    iface.addDockWidget.side_effect = add_dock_widget
    iface.addTabifiedDockWidget.side_effect = add_tabified_dock_widget
    iface.removeDockWidget.side_effect = lambda w: main_window.removeDockWidget(w)

    # Mock signal
    iface.initializationCompleted = Mock()
    iface.initializationCompleted.connect = Mock()

    # Process events to show windows
    qgis_application.processEvents()

    yield iface

    # Cleanup
    main_window.close()
    main_window.deleteLater()
    qgis_application.processEvents()


@pytest.fixture(scope="function")
def plugin(qgis_iface, qgis_application):
    auth_manager = QgsApplication.authManager()
    if not auth_manager.authenticationDatabasePath():
        auth_manager.setup()

    if not auth_manager.masterPasswordIsSet():
        auth_manager.setMasterPassword("test", True)

    secret = os.getenv("RANA_PAK")

    set_base_url("https://test.ranawaterintelligence.com")
    set_3di_auth("insert_test_api_key_here")
    # insert BASIC auth config for testing
    authcfg = QgsAuthMethodConfig()
    authcfg.setName(RANA_SETTINGS_ENTRY)
    authcfg.setMethod("Basic")
    authcfg.setConfig("username", "__key__")
    authcfg.setConfig("password", secret)
    # check if method parameters are correctly set
    assert authcfg.isValid()
    auth_manager.storeAuthenticationConfig(authcfg)
    newAuthCfgId = authcfg.id()
    assert newAuthCfgId

    plugin = RanaQgisPlugin(qgis_iface)
    plugin.initGui()
    yield plugin

    plugin.unload()
    qgis_application.processEvents()
