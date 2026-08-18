import os
import uuid
from unittest.mock import Mock, patch

import pytest
from qgis.core import QgsApplication, QgsAuthMethodConfig, QgsLayerTreeModel, QgsProject
from qgis.gui import (
    QgsBrowserDockWidget,
    QgsBrowserGuiModel,
    QgsLayerTreeMapCanvasBridge,
    QgsLayerTreeView,
    QgsMapCanvas,
    QgsMessageBar,
)
from qgis.PyQt.QtCore import QSettings, Qt
from qgis.PyQt.QtWidgets import (
    QDockWidget,
    QMainWindow,
    QMenu,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

import rana_qgis_plugin.utils.api as utils_api
from rana_qgis_plugin.constant import RANA_AUTHCFG_ENTRY, RANA_SETTINGS_ENTRY
from rana_qgis_plugin.rana_qgis_plugin import RanaQgisPlugin
from rana_qgis_plugin.utils.api import create_project, delete_project
from rana_qgis_plugin.utils.settings import (
    set_base_url,
    set_cleanup_cache_on_close,
    set_tenant_id,
)


@pytest.fixture(autouse=True)
def mock_get_user_info():
    with (
        patch("rana_qgis_plugin.data_items.rana_item.get_user_info") as mock,
        patch(
            "rana_qgis_plugin.widgets.projects_selection_dialog.get_user_info",
            new=mock,
        ),
    ):
        mock.return_value = utils_api.UserInfo(
            sub="test_user",
            given_name="test",
            family_name="user",
            email="test_user@test.com",
        )
        yield


@pytest.fixture(autouse=True)
def mock_get_user_tenants():
    with patch(
        "rana_qgis_plugin.data_items.rana_item.get_user_tenants"
    ) as mock_tenants:
        mock_tenants.return_value = [
            {
                "id": "rdc-e2e",
                "name": "Nelen & Schuurmans e2e test",
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
    qgs.exitQgis()


@pytest.fixture
def qgis_iface(qgis_application):
    """QGIS interface with visible windows"""
    # Create real main window
    main_window = QMainWindow()
    main_window.setWindowTitle("QGIS Test Window")
    main_window.resize(1200, 800)

    # Add plugin menus to main window
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

    # Create mock iface with real mainwindow and canvas, and real toolbar/dock widget methods
    iface = Mock()
    iface.mainWindow.return_value = main_window

    centerWidget = QWidget(main_window)
    center_layout = QVBoxLayout(centerWidget)
    centerWidget.setLayout(center_layout)

    main_window.setCentralWidget(centerWidget)

    canvas = QgsMapCanvas(main_window)
    iface.mapCanvas.return_value = canvas

    # Connect our local canvas to the layer tree
    root = QgsProject.instance().layerTreeRoot()
    bridge = QgsLayerTreeMapCanvasBridge(root, canvas)

    layer_tree_model = QgsLayerTreeModel(root, main_window)
    layer_tree_view = QgsLayerTreeView(main_window)
    layer_tree_view.setModel(layer_tree_model)

    message_bar = QgsMessageBar(main_window)
    iface.messageBar.return_value = message_bar
    center_layout.addWidget(message_bar)
    center_layout.addWidget(canvas)

    # Mock QGIS toolbar - returns real toolbar
    def add_toolbar(name):
        toolbar = QToolBar(name, main_window)
        main_window.addToolBar(toolbar)
        return toolbar

    iface.addToolBar.side_effect = add_toolbar
    iface.removeToolBarIcon.return_value = None

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

    # Real layer tree view for layer-panel interactions
    iface.layerTreeView.return_value = layer_tree_view

    # Process events to show windows
    qgis_application.processEvents()

    yield iface

    # Cleanup
    main_window.close()
    main_window.deleteLater()
    qgis_application.processEvents()


def configure_rana_auth(qgis_application):
    """Configure the Rana test backend and authentication."""
    QSettings().setValue(
        f"{RANA_SETTINGS_ENTRY}/last_upload_folder",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"),
    )
    auth_manager = QgsApplication.authManager()
    if not auth_manager.authenticationDatabasePath():
        auth_manager.setup()
    if not auth_manager.masterPasswordIsSet():
        auth_manager.setMasterPassword("test", True)
    set_base_url("https://test.ranawaterintelligence.com")
    set_tenant_id("rdc-e2e")
    authcfg = QgsAuthMethodConfig()
    authcfg.setName(RANA_SETTINGS_ENTRY)
    authcfg.setMethod("Basic")
    authcfg.setConfig("username", "__key__")
    authcfg.setConfig("password", os.getenv("RANA_PAK"))
    assert authcfg.isValid()
    auth_manager.storeAuthenticationConfig(authcfg)
    assert authcfg.id()
    QSettings().setValue(RANA_AUTHCFG_ENTRY, authcfg.id())
    set_cleanup_cache_on_close(False)


@pytest.fixture(scope="function")
def plugin(qgis_iface, qgis_application):
    configure_rana_auth(qgis_application)

    plugin = RanaQgisPlugin(qgis_iface)
    plugin.initGui()

    browser_model = QgsBrowserGuiModel()
    browser_model.initialize()
    browser_dock = QgsBrowserDockWidget(
        "Browser", browser_model, qgis_iface.mainWindow()
    )
    browser_model.setMapCanvas(qgis_iface.mapCanvas())
    browser_model.setMessageBar(qgis_iface.messageBar())
    qgis_iface.mainWindow().addDockWidget(
        Qt.DockWidgetArea.LeftDockWidgetArea, browser_dock
    )
    browser_dock.setUserVisible(True)

    layer_tree_view = qgis_iface.layerTreeView()
    layer_tree_dock = QDockWidget("Layers", qgis_iface.mainWindow())
    layer_tree_dock.setWidget(layer_tree_view)
    qgis_iface.mainWindow().addDockWidget(
        Qt.DockWidgetArea.LeftDockWidgetArea, layer_tree_dock
    )
    qgis_iface.mainWindow().resizeDocks(
        [browser_dock, layer_tree_dock], [300, 300], Qt.Orientation.Vertical
    )

    qgis_application.processEvents()

    rana_root_item = None
    for i in range(browser_model.rowCount()):
        idx = browser_model.index(i, 0)
        if browser_model.data(idx).startswith("Rana"):
            rana_root_item = browser_model.dataItem(idx)
            break
    assert rana_root_item is not None, "Rana root item not found in browser model"
    plugin.rana_root_item = rana_root_item
    plugin.browser_dock = browser_dock
    plugin.browser_model = browser_model

    yield plugin

    plugin.unload()
    QgsProject.instance().clear()
    layer_tree_dock.close()
    layer_tree_dock.deleteLater()
    browser_dock.close()
    browser_dock.deleteLater()
    browser_model.deleteLater()
    qgis_application.processEvents()


@pytest.fixture
def authenticated(plugin, qtbot, qgis_application):
    """Ensure the configured authentication is usable by the test API."""
    root = plugin.rana_root_item
    root.refresh()
    qtbot.waitUntil(lambda: root.children() is not None, timeout=30000)


@pytest.fixture
def rana_project(authenticated, plugin):
    """Create and clean up a project on the configured Rana test instance."""
    project = create_project(
        {"code": f"e2e_{uuid.uuid4().hex[:24]}", "name": f"e2e_{uuid.uuid4().hex[:56]}"}
    )
    assert project is not None, "create_project failed — check authentication"
    yield project
    if project.get("id"):
        delete_project(project["id"])
