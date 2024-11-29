import webbrowser

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QAction, QDockWidget, QMenu, QSizePolicy

from .auth import get_authcfg_id, remove_authcfg, setup_oauth2
from .communication import UICommunication
from .constant import LOGOUT_URL, PLUGIN_NAME
from .icons import login_icon, logout_icon, rana_icon
from .utils_api import get_user_info
from .widgets.rana_browser import RanaBrowser


class RanaQgisPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.menu = PLUGIN_NAME
        self.dock_widget = None
        self.rana_browser = None
        self.toolbar = self.iface.addToolBar(self.menu)
        self.toolbar.setObjectName(self.menu)
        self.icon = rana_icon
        self.action = QAction(self.icon, self.menu, iface.mainWindow())
        self.action.triggered.connect(self.run)
        self.communication = UICommunication(self.iface, self.menu)

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""
        self.iface.addPluginToMenu(self.menu, self.action)
        self.toolbar.addAction(self.action)
        self.add_rana_menu()

    def login(self):
        self.communication.clear_message_bar()
        self.communication.bar_info("Login initiated! Please check your browser.")
        setup_oauth2(self.communication)
        self.add_rana_menu()
        if self.dock_widget:
            self.dock_widget.show()

    def logout(self):
        self.communication.clear_message_bar()
        self.communication.bar_info("Logout initiated! You will be logged out from Rana shortly.")
        webbrowser.open(LOGOUT_URL)
        remove_authcfg()
        self.add_rana_menu()
        if self.dock_widget:
            self.dock_widget.close()

    def find_rana_menu(self):
        for i, action in enumerate(self.iface.mainWindow().menuBar().actions()):
            if action.menu().objectName() == "rana":
                return action.menu()
        return None

    def add_rana_menu(self):
        """Add Rana menu to the main menu bar."""
        menu = self.find_rana_menu()
        if not menu:
            menu = QMenu("Rana", self.iface.mainWindow().menuBar())
            menu.setObjectName("rana")
            self.iface.mainWindow().menuBar().addMenu(menu)
        menu.clear()
        authcfg_id = get_authcfg_id()
        if authcfg_id:
            user = get_user_info(self.communication)
            if user:
                user_name = f"{user["given_name"]} {user["family_name"]}"
                user_action = QAction(user_name, self.iface.mainWindow())
                user_action.setEnabled(False)
                menu.addAction(user_action)
            logout_action = QAction(logout_icon, "Logout", self.iface.mainWindow())
            logout_action.triggered.connect(self.logout)
            menu.addAction(logout_action)
        else:
            login_action = QAction(login_icon, "Login", self.iface.mainWindow())
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
        authcfg_id = get_authcfg_id()
        if not authcfg_id:
            self.login()
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
