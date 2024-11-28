import os.path
import webbrowser

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QDockWidget, QMenu, QSizePolicy

from .auth import remove_authcfg, setup_oauth2
from .communication import UICommunication
from .constant import LOGOUT_URL, PLUGIN_NAME, TENANT
from .utils_api import get_tenant
from .widgets.rana_browser import RanaBrowser


class RanaQgisPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.menu = PLUGIN_NAME
        self.dock_widget = None
        self.rana_browser = None
        self.toolbar = self.iface.addToolBar(self.menu)
        self.toolbar.setObjectName(self.menu)
        self.icon = QIcon(os.path.join(os.path.dirname(__file__), "icon.svg"))
        self.action = QAction(self.icon, self.menu, iface.mainWindow())
        self.action.triggered.connect(self.run)
        self.communication = UICommunication(self.iface, self.menu)

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""
        # Setup OAuth2 authentication
        setup_oauth2(self.communication)

        # Add the menu item and toolbar icon
        self.iface.addPluginToMenu(self.menu, self.action)
        self.toolbar.addAction(self.action)
        self.addHelpMenuItem()

    def login(self):
        setup_oauth2(self.communication)
        self.dock_widget.show()
        get_tenant(self.communication, TENANT)

    def logout(self):
        webbrowser.open(LOGOUT_URL)
        remove_authcfg()
        self.dock_widget.close()
        self.communication.bar_info("Logout successful! You have been logged out from Rana.")

    def find_rana_menu(self):
        for i, action in enumerate(self.iface.mainWindow().menuBar().actions()):
            if action.menu().objectName() == "rana":
                return action.menu()
        return None

    def addHelpMenuItem(self):
        menu = self.find_rana_menu()
        if not menu:
            menu = QMenu("Rana", self.iface.mainWindow().menuBar())
            menu.setObjectName("rana")
            self.iface.mainWindow().menuBar().addMenu(menu)
        # Logout action
        logout_action = QAction("Logout", self.iface.mainWindow())
        logout_action.triggered.connect(self.logout)
        menu.addAction(logout_action)
        # Login action
        login_action = QAction("Login", self.iface.mainWindow())
        login_action.triggered.connect(self.login)
        menu.addAction(login_action)

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        self.iface.removePluginMenu(self.menu, self.action)
        self.iface.removeToolBarIcon(self.action)
        if self.dock_widget:
            self.iface.removeDockWidget(self.dock_widget)
            self.dock_widget.deleteLater()

    def run(self):
        """Run method that loads and starts the plugin"""
        if not self.dock_widget:
            self.dock_widget = QDockWidget(self.menu, self.iface.mainWindow())
            self.dock_widget.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
            self.dock_widget.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable)
            self.dock_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.dock_widget.setObjectName(self.menu)
            self.rana_browser = RanaBrowser(self.communication)
            self.dock_widget.setWidget(self.rana_browser)
        self.iface.addTabifiedDockWidget(Qt.RightDockWidgetArea, self.dock_widget, raiseTab=True)
        self.dock_widget.show()
