from functools import partial

from qgis.core import QgsApplication
from qgis.PyQt.QtCore import Qt, QTimer
from qgis.PyQt.QtWidgets import (
    QAction,
    QButtonGroup,
    QDialog,
    QDockWidget,
    QRadioButton,
    QSizePolicy,
)

from rana_qgis_plugin.auth import get_authcfg_id, remove_authcfg, setup_oauth2
from rana_qgis_plugin.auth_3di import setup_3di_auth
from rana_qgis_plugin.communication import UICommunication
from rana_qgis_plugin.constant import PLUGIN_NAME
from rana_qgis_plugin.icons import login_icon, logout_icon, rana_icon, settings_icon
from rana_qgis_plugin.loader import Loader
from rana_qgis_plugin.utils import parse_url
from rana_qgis_plugin.utils_api import get_user_info, get_user_tenants
from rana_qgis_plugin.utils_settings import (
    get_tenant_id,
    initialize_settings,
    set_tenant_id,
)
from rana_qgis_plugin.widgets.about_rana_dialog import AboutRanaDialog
from rana_qgis_plugin.widgets.rana_browser import RanaBrowser
from rana_qgis_plugin.widgets.settings_dialog import SettingsDialog
from rana_qgis_plugin.widgets.tenant_selection_dialog import TenantSelectionDialog


class RanaQgisPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.tenants = []
        self.dock_widget = None
        self.rana_browser = None
        self.toolbar = self.iface.addToolBar(PLUGIN_NAME)
        self.toolbar.setObjectName(PLUGIN_NAME)
        self.action = QAction(rana_icon, "Open browser", iface.mainWindow())
        self.action.triggered.connect(self.run)
        self.communication = UICommunication(self.iface, PLUGIN_NAME)
        initialize_settings()

        iface.initializationCompleted.connect(self.check_arguments)

    def check_arguments(self):
        # sys.argv does not seem to be filled yet when starting the plugin
        # self.communication.show_info(str(sys.argv))
        for arg in QgsApplication.arguments():
            if arg.startswith("rana://"):
                QTimer.singleShot(
                    0, partial(self.run, arg)
                )  # Calls run() after the event loop starts

    def initGui(self):
        """Create the (initial) menu entries and toolbar icons inside the QGIS GUI."""
        self.add_rana_menu(False)
        self.toolbar.addAction(self.action)

    def login(self, start_tenant_id: str = None) -> bool:
        if not setup_oauth2(self.communication):
            return False
        self.add_rana_menu(True)
        if not self.set_tenant(start_tenant_id):
            return False
        setup_3di_auth(self.communication)
        if self.dock_widget:
            self.dock_widget.show()

        return True

    def logout(self):
        self.communication.clear_message_bar()
        remove_authcfg()
        set_tenant_id("")
        self.add_rana_menu(False)
        self.communication.bar_info("You have been logged out.")
        if self.dock_widget:
            self.dock_widget.close()

    def set_tenant(self, start_tenant_id: str = None):
        if start_tenant_id is None:
            tenant_id = get_tenant_id()
            if tenant_id:
                return True
            if not self.tenants:
                return False

            tenant_id = self.tenants[0]["id"]
        else:
            # Extra check to see whether requested tenant is in list.
            if any(t["id"] == start_tenant_id for t in self.tenants):
                tenant_id = start_tenant_id
            else:
                self.communication.bar_error(
                    f"Tenant {start_tenant_id} not in list available tenants, aborting load...",
                    -1,
                )
                return False

        set_tenant_id(tenant_id)
        self.communication.clear_message_bar()
        self.communication.bar_info(f"Tenant set to: {tenant_id}")

        return True

    def open_about_rana_dialog(self):
        dialog = AboutRanaDialog(self.iface.mainWindow())
        dialog.exec_()

    def open_settings_dialog(self):
        dialog = SettingsDialog(self.iface.mainWindow())
        if dialog.exec() == QDialog.Accepted:
            if dialog.authenticationSettingsChanged():
                self.logout()
                self.login()
                if self.rana_browser:
                    self.rana_browser.refresh_projects()

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

    def add_rana_menu(self, show_authentication: bool):
        """Add Rana menu to the main menu bar."""
        menu = self.iface.mainWindow().getPluginMenu(PLUGIN_NAME)
        menu.clear()
        menu.addAction(self.action)
        menu.addSeparator()

        if show_authentication:
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

        menu.addSeparator()
        settings_action = QAction(settings_icon, "Settings", self.iface.mainWindow())
        settings_action.triggered.connect(self.open_settings_dialog)
        menu.addAction(settings_action)

        about_rana_action = QAction(
            rana_icon, "About Rana Desktop Client", self.iface.mainWindow()
        )
        about_rana_action.triggered.connect(self.open_about_rana_dialog)
        menu.addAction(about_rana_action)

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        menu = self.iface.mainWindow().getPluginMenu(PLUGIN_NAME)
        menu.clear()
        self.iface.removeToolBarIcon(self.action)
        if self.dock_widget:
            self.iface.removeDockWidget(self.dock_widget)
            self.dock_widget.deleteLater()

    def run(self, start_url: str = None):
        """Run method that loads and starts the plugin"""
        if start_url:
            path_params, query_params = parse_url(start_url)
            if not self.login(path_params["tenant_id"]):
                return
        else:
            self.login()
        if not self.dock_widget:
            # Setup GUI
            self.dock_widget = QDockWidget(PLUGIN_NAME, self.iface.mainWindow())
            self.dock_widget.setAllowedAreas(
                Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea
            )
            self.dock_widget.setFeatures(
                QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable
            )
            self.dock_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.dock_widget.setObjectName(PLUGIN_NAME)
            self.rana_browser = RanaBrowser(self.communication)
            self.dock_widget.setWidget(self.rana_browser)
            self.loader = Loader(self.communication, self.rana_browser)

            # Connect signals
            self.rana_browser.open_wms_selected.connect(self.loader.open_wms)

        self.iface.addTabifiedDockWidget(
            Qt.RightDockWidgetArea, self.dock_widget, raiseTab=True
        )
        self.dock_widget.show()

        if start_url:
            self.rana_browser.start_file_in_qgis(
                path_params["project_id"], query_params["path"][0]
            )
