from unittest.mock import patch

from qgis.core import QgsSettings
from qgis.PyQt.QtCore import QEvent, QTimer
from qgis.PyQt.QtTest import QTest
from qgis.PyQt.QtWidgets import QApplication, QDialog

from e2e.test_utils import click_context_menu_action, make_modal_handler
from rana_qgis_plugin.auth import is_authenticated
from rana_qgis_plugin.constant import RANA_AUTHCFG_ENTRY


def simulate_external_refocus(plugin, qgis_application):
    """Simulate returning from an external application.

    Hides the main window so QApplication.activeWindow() returns None, then sends
    WindowDeactivate (which should set the flag) and WindowActivate (which should
    trigger refresh). Restores the window afterwards.
    """
    main_window = plugin.iface.mainWindow()
    main_window.hide()
    qgis_application.processEvents()
    QApplication.sendEvent(main_window, QEvent(QEvent.Type.WindowDeactivate))
    qgis_application.processEvents()
    main_window.show()
    qgis_application.processEvents()
    QApplication.sendEvent(main_window, QEvent(QEvent.Type.WindowActivate))
    qgis_application.processEvents()


def test_smoke(plugin, request):
    plugin.iface.mainWindow().setWindowTitle(request.node.nodeid)
    assert plugin.rana_root_item is not None


def test_login_logout(plugin, qtbot, request):
    """Test logout and login via context menu clicks."""
    plugin.iface.mainWindow().setWindowTitle(request.node.nodeid)

    root = plugin.rana_root_item

    # Step 1: the plugin fixture has stored a valid authcfg so we are already
    # logged in. Verify Logout is present in the context menu.
    assert is_authenticated()
    assert any(a.text() == "Logout" for a in root.actions(None))

    # Step 2: open context menu and click Logout.
    click_context_menu_action(qtbot, root, "Logout")

    # Step 3: verify Login is in the context menu again.
    assert any(a.text() == "Login" for a in root.actions(None))

    # Step 4: verify no authcfg is stored in settings.
    assert not QgsSettings().value(RANA_AUTHCFG_ENTRY)


def test_refocus_triggers_refresh(plugin, qgis_application):
    """WindowDeactivate→WindowActivate from external app triggers refresh."""
    root = plugin._data_item_provider.root_item

    with patch.object(root, "refresh") as mock_refresh:
        simulate_external_refocus(plugin, qgis_application)
        mock_refresh.assert_called_once()


def test_refocus_not_triggered_by_settings_dialog(plugin, qtbot, qgis_application):
    """Opening and closing the settings dialog must not trigger a refresh."""
    root = plugin._data_item_provider.root_item

    def dismiss(qtbot, modal):
        modal.reject()

    with patch.object(root, "refresh") as mock_refresh:
        QTimer.singleShot(200, make_modal_handler(qtbot, QDialog, dismiss))
        plugin.rana_root_item.open_settings()
        QTest.qWait(500)
        qgis_application.processEvents()

        mock_refresh.assert_not_called()
