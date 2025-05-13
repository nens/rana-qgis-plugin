from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QAction,
    QButtonGroup,
    QDialog,
    QDockWidget,
    QMenu,
    QRadioButton,
    QSizePolicy,
)

from .auth import get_authcfg_id, remove_authcfg, setup_oauth2
from .auth_3di import setup_3di_auth
from .communication import UICommunication
from .constant import LOGOUT_URL, PLUGIN_NAME
from .icons import login_icon, logout_icon, rana_icon
from .utils import get_tenant_id, set_tenant_id
from .utils_api import get_user_info, get_user_tenants
from .widgets.about_rana_dialog import AboutRanaDialog
from .widgets.rana_browser import RanaBrowser
from .widgets.tenant_selection_dialog import TenantSelectionDialog


class RanaQgisPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.tenants = []
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

    def login(self):
        setup_oauth2(self.communication)
        self.add_rana_menu()
        self.set_tenant()
        setup_3di_auth(self.communication)
        if self.dock_widget:
            self.dock_widget.show()

    def logout(self):
        self.communication.clear_message_bar()
        remove_authcfg()
        self.add_rana_menu()
        self.communication.bar_info("You have been logged out.")
        if self.dock_widget:
            self.dock_widget.close()

    def set_tenant(self):
        tenant_id = get_tenant_id()
        if tenant_id:
            return
        if not self.tenants:
            return
        tenant = self.tenants[0]
        set_tenant_id(tenant["id"])
        self.communication.clear_message_bar()
        self.communication.bar_info(f"Tenant set to: {tenant['id']}")

    def open_about_rana_dialog(self):
        dialog = AboutRanaDialog(self.iface.mainWindow())
        dialog.exec_()

    def open_tenant_selection_dialog(self):
        current_tenant_id = get_tenant_id()
        dialog = TenantSelectionDialog(self.iface.mainWindow())
        button_group = QButtonGroup(dialog)
        for tenant in self.tenants:
            tenant_name, tenant_id = tenant["name"], tenant["id"]
            tenant_name = tenant_name.replace("&", "&&")  # Escape '&' character
            radio_button = QRadioButton(f"{tenant_name} ({tenant_id})", dialog)
            radio_button.setObjectName(tenant_id)
            button_group.addButton(radio_button)
            dialog.tenants_widget.layout().addWidget(radio_button)
            if tenant_id == current_tenant_id:
                radio_button.setChecked(True)
        dialog.adjustSize()
        if dialog.exec_() == QDialog.Accepted:
            selected_button = button_group.checkedButton()
            selected_tenant_id = selected_button.objectName()
            if selected_tenant_id != current_tenant_id:
                set_tenant_id(selected_tenant_id)
                self.communication.clear_message_bar()
                self.communication.bar_info(f"Tenant set to: {selected_tenant_id}")
                if self.rana_browser:
                    self.rana_browser.refresh_projects()

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
                user_id = user["sub"]
                user_name = f"{user['given_name']} {user['family_name']}"
                user_action = QAction(user_name, self.iface.mainWindow())
                user_action.setEnabled(False)
                menu.addAction(user_action)
                self.tenants = get_user_tenants(self.communication, user_id)
                if len(self.tenants) > 1:
                    switch_tenant_action = QAction(
                        "Switch Tenant", self.iface.mainWindow()
                    )
                    switch_tenant_action.triggered.connect(
                        self.open_tenant_selection_dialog
                    )
                    menu.addAction(switch_tenant_action)
            logout_action = QAction(logout_icon, "Logout", self.iface.mainWindow())
            logout_action.triggered.connect(self.logout)
            menu.addAction(logout_action)
        else:
            login_action = QAction(login_icon, "Login", self.iface.mainWindow())
            login_action.triggered.connect(self.login)
            menu.addAction(login_action)
        about_rana_action = QAction(
            rana_icon, "About Rana Desktop Client", self.iface.mainWindow()
        )
        about_rana_action.triggered.connect(self.open_about_rana_dialog)
        menu.addAction(about_rana_action)

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        self.iface.removePluginMenu(self.menu, self.action)
        self.iface.removeToolBarIcon(self.action)
        if self.dock_widget:
            self.iface.removeDockWidget(self.dock_widget)
            self.dock_widget.deleteLater()

    def run(self):
        """Run method that loads and starts the plugin"""
        self.login()
        if not self.dock_widget:
            self.dock_widget = QDockWidget(self.menu, self.iface.mainWindow())
            self.dock_widget.setAllowedAreas(
                Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea
            )
            self.dock_widget.setFeatures(
                QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable
            )
            self.dock_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.dock_widget.setObjectName(self.menu)
            self.rana_browser = RanaBrowser(self.communication)
            self.dock_widget.setWidget(self.rana_browser)
        self.iface.addTabifiedDockWidget(
            Qt.RightDockWidgetArea, self.dock_widget, raiseTab=True
        )
        self.dock_widget.show()
