"""Rana root Browser data item."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from qgis.core import (
    Qgis,
    QgsDataItem,
    QgsErrorItem,
    QgsSettings,
)
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import (
    QAction,
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
)

from rana_qgis_plugin.api_error_signals import ApiErrorSignals
from rana_qgis_plugin.auth import (
    active_tenant,
    clear_credentials,
    create_oauth2_config,
    fetch_identity_providers,
    is_authenticated,
)
from rana_qgis_plugin.constant import (
    ICONS_DIR,
    RANA_AUTHCFG_ENTRY,
    RANA_SETTINGS_ENTRY,
    RANA_TENANT_ENTRY,
)
from rana_qgis_plugin.data_items.project_item import RanaProjectDataItem
from rana_qgis_plugin.network_manager import NetworkUnavailableError
from rana_qgis_plugin.utils.api import (
    RanaFetchError,
    RanaPostError,
    get_tenant_projects,
    get_user_info,
    get_user_tenants,
)
from rana_qgis_plugin.utils.auth_3di import remove_3di_auth, setup_3di_auth
from rana_qgis_plugin.utils.settings import (
    base_url,
    get_hidden_projects,
    get_tenant_id,
    set_tenant_id,
)
from rana_qgis_plugin.widgets.projects_selection_dialog import ProjectsSelectionDialog
from rana_qgis_plugin.widgets.settings_dialog import RanaSettingsDialog

if TYPE_CHECKING:
    from rana_qgis_plugin.communication import UICommunication
    from rana_qgis_plugin.loader import Loader


class RanaRootDataItem(QgsDataItem):
    """Root Browser item for Rana. Always visible; drives the auth flow."""

    def __init__(
        self,
        communication: UICommunication,
        loader: Loader,
        error_signals: ApiErrorSignals,
        parent: Optional[QgsDataItem] = None,
    ):
        self.communication = communication
        self.loader = loader
        self.error_signals = error_signals
        self.projects_selection_dialog: Optional[ProjectsSelectionDialog] = None
        super().__init__(
            Qgis.BrowserItemType.Collection, parent, "Rana", "/Rana", "Rana"
        )
        self.setIcon(QIcon(str(ICONS_DIR / "rana.svg")))
        self.tenants: Optional[list] = None
        self.update_display()
        if is_authenticated():
            self.restore_session()
        else:
            self.setState(Qgis.BrowserItemState.Populated)

    def createChildren(self) -> list:
        """Fetch and return project items. Called by QGIS in a background thread."""
        if not is_authenticated():
            return []
        try:
            response = get_tenant_projects()
        except NetworkUnavailableError:
            self.error_signals.connection_lost.emit()
            return [QgsErrorItem(self, "No connection to Rana", self.path())]
        except RanaFetchError as e:
            self.error_signals.fetch_error_occurred.emit(str(e), True)
            return [QgsErrorItem(self, "Failed to load projects", self.path())]
        hidden = get_hidden_projects(base_url(), get_tenant_id())
        return [
            RanaProjectDataItem(
                self,
                self.loader,
                p["id"],
                p["name"],
                p.get("slug", ""),
                self.error_signals,
            )
            for p in response.get("items", [])
            if p["id"] not in hidden
        ]

    def restore_session(self) -> None:
        """Silently restore tenant list from a previous authenticated session."""
        try:
            user = get_user_info()
            if user is not None:
                self.tenants = get_user_tenants(user["sub"])
        except RanaFetchError as e:
            self.error_signals.fetch_error_occurred.emit(str(e), False)
        except NetworkUnavailableError:
            self.error_signals.connection_lost.emit()
        self.communication.bar_info(f"Signed in to Rana")
        self.update_display()

    def update_display(self) -> None:
        if not is_authenticated():
            self.setName("Rana")
        else:
            tenant_id = active_tenant()
            if tenant_id:
                self.setName(f"Rana [{tenant_id}]")
            else:
                self.setName("Rana")

    def actions(self, parent) -> list:
        """Return state-aware context menu actions."""
        login_action = QAction("Login", parent)
        login_action.triggered.connect(lambda: self.login())

        logout_action = QAction("Logout", parent)
        logout_action.triggered.connect(lambda: self.logout())

        settings_action = QAction("Settings", parent)
        settings_action.triggered.connect(lambda: self.open_settings())

        if is_authenticated():
            refresh_action = QAction("Refresh", parent)
            refresh_action.setIcon(QIcon(str(ICONS_DIR / "refresh.svg")))
            refresh_action.triggered.connect(self.refresh)

            select_projects_action = QAction("Select projects", parent)
            select_projects_action.triggered.connect(self.open_projects_selection)

            actions = [refresh_action, logout_action]
            if self.tenants is not None and len(self.tenants) >= 2:
                switch_action = QAction("Switch tenant", parent)
                switch_action.triggered.connect(lambda: self.switch_tenant())
                actions.append(switch_action)
            actions.append(select_projects_action)
            actions.append(settings_action)
            return actions
        return [login_action, settings_action]

    def open_settings(self) -> None:
        """Open the settings dialog; reset auth and re-login if the backend URL changed."""
        dlg = RanaSettingsDialog()
        was_authenticated = is_authenticated()
        if dlg.exec() == RanaSettingsDialog.DialogCode.Accepted and dlg.url_changed():
            QgsSettings().remove(RANA_TENANT_ENTRY)
            clear_credentials()
            self.tenants = None
            self.update_display()
            self.refresh()
            if was_authenticated:
                self.login()

    def open_projects_selection(self) -> None:
        """Open the project visibility selection dialog and refresh on close."""
        dlg = ProjectsSelectionDialog(
            self.communication, self.loader, self.error_signals
        )
        self.projects_selection_dialog = dlg
        dlg.finished.connect(self.on_projects_selection_finished)
        dlg.open()

    def on_projects_selection_finished(self, result: int) -> None:
        if result == QDialog.DialogCode.Accepted:
            self.refresh()
        self.projects_selection_dialog = None

    def prompt_tenant(self) -> Optional[str]:
        """Prompt the user to enter a tenant code. Returns tenant ID or None if cancelled."""
        tenant_id, ok = QInputDialog.getText(
            None, "Rana Authentication", "Please provide your tenant code."
        )
        return tenant_id.strip() if ok and tenant_id.strip() else None

    def prompt_provider(self, providers: list) -> Optional[dict]:
        """Prompt user to select an identity provider, excluding internal Rana-type providers."""

        external = [p for p in providers if p.get("type") != "rana"]

        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Question)
        msg_box.setWindowTitle("Rana Authentication")
        msg_box.setText("How would you like to sign in?")

        buttons = {}
        for p in external:
            label = f"Sign in with your SSO ({p['name']})".replace("&", "&&")
            btn = QPushButton(label)
            msg_box.addButton(btn, QMessageBox.ButtonRole.YesRole)
            buttons[btn] = p

        native_btn = QPushButton("Sign in with your username and password")
        msg_box.addButton(native_btn, QMessageBox.ButtonRole.YesRole)
        msg_box.addButton(QMessageBox.StandardButton.Cancel)

        msg_box.exec()
        clicked = msg_box.clickedButton()

        if clicked is None or clicked == msg_box.button(
            QMessageBox.StandardButton.Cancel
        ):
            return None
        if clicked in buttons:
            return buttons[clicked]
        return {"id": "", "name": "", "type": "rana"}

    def login(self, start_tenant_id: Optional[str] = None) -> bool:
        """Run the full interactive login flow.

        Resolves tenant, fetches identity providers, prompts provider selection,
        creates OAuth2 config. Returns True on success, False on cancellation or error.
        No partial state is stored on failure.
        """
        settings = QgsSettings()
        base = settings.value(f"{RANA_SETTINGS_ENTRY}/base_url")
        if not base:
            self.communication.show_error("No backend URL configured.")
            return False

        tenant_id = start_tenant_id or get_tenant_id() or self.prompt_tenant()
        if not tenant_id:
            return False

        self.refresh()

        try:
            providers = fetch_identity_providers(tenant_id)
            if providers is None:
                self.communication.show_error(
                    f"Unable to retrieve identity providers for tenant {tenant_id}."
                )
                return False

            provider = self.prompt_provider(providers)
            if not provider:
                return False
            self.communication.clear_message_bar()
            self.communication.bar_info("Signing in to Rana...")
            authcfg_id = create_oauth2_config(provider)

            if not authcfg_id:
                self.communication.bar_info("Failed to sign in to Rana")
                return False

            settings.setValue(RANA_AUTHCFG_ENTRY, authcfg_id)
            set_tenant_id(tenant_id)
            try:
                user = get_user_info()
            except RanaFetchError as e:
                self.communication.bar_info(f"Failed to sign in to Rana")
                self.error_signals.fetch_error_occurred.emit(str(e), False)
                return False
            try:
                self.tenants = get_user_tenants(user["sub"])
            except RanaFetchError as e:
                self.error_signals.fetch_error_occurred.emit(str(e), False)
            self.communication.bar_info(f"Signed in to Rana")
            self.communication.log_info(f"Signed in to Rana (tenant: {tenant_id}).")
            # Log in to HCC
            self.communication.clear_message_bar()
            self.communication.bar_info("Getting HCC access...")
            try:
                setup_3di_auth(user["sub"])
                self.communication.bar_info("Signed in to HCC")
                self.communication.log_info("Signed in to HCC")
            except RanaPostError as e:
                self.communication.bar_info(f"Failed to sign in to HCC: {e}")
                self.error_signals.fetch_error_occurred.emit(
                    f"Failed to sign in to HCC: {e}", False
                )
                return False
            return True
        except NetworkUnavailableError:
            self.error_signals.connection_lost.emit()
            return False
        finally:
            self.update_display()
            self.refresh()

    def prompt_switch_tenant(self) -> Optional[str]:
        """Show a radio-button dialog to pick a tenant. Returns tenant ID or None if cancelled."""
        current = active_tenant()
        dlg = QDialog()
        dlg.setWindowTitle("Switch tenant")
        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel("Select a tenant:"))

        group = QButtonGroup(dlg)
        buttons: dict[QRadioButton, str] = {}
        for tenant in self.tenants or []:
            tenant_id = tenant.get("id", "")
            label = f"{tenant.get('name', tenant_id).replace('&', '&&')} ({tenant_id})"
            btn = QRadioButton(label)
            btn.setObjectName(tenant_id)
            if tenant_id == current:
                btn.setChecked(True)
            group.addButton(btn)
            layout.addWidget(btn)
            buttons[btn] = tenant_id

        box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        box.accepted.connect(dlg.accept)
        box.rejected.connect(dlg.reject)
        layout.addWidget(box)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None
        checked = group.checkedButton()
        return buttons.get(checked) if checked else None

    def switch_tenant(self) -> None:
        """Switch to a different tenant: snapshot, logout, re-login, rollback on failure."""
        snapshot_tenant = get_tenant_id()
        snapshot_authcfg = QgsSettings().value(RANA_AUTHCFG_ENTRY)

        new_tenant = self.prompt_switch_tenant()
        if not new_tenant or new_tenant == snapshot_tenant:
            return

        self.logout(delete_config=False)

        if not self.login(start_tenant_id=new_tenant):
            # Rollback: restore previous credentials and tenant
            self.communication.show_error(
                f"Failed to sign in to tenant '{new_tenant}'. Restoring previous session."
            )
            if snapshot_authcfg:
                QgsSettings().setValue(RANA_AUTHCFG_ENTRY, snapshot_authcfg)
            if snapshot_tenant:
                set_tenant_id(snapshot_tenant)
            self.update_display()
            self.refresh()

    def logout(self, delete_config: bool = True) -> None:
        """Full logout: clear credentials and reset UI state."""
        clear_credentials(delete_config=delete_config)
        remove_3di_auth()
        self.tenants = None
        self.communication.bar_info(f"Signed out of Rana")
        self.update_display()
        self.refresh()
