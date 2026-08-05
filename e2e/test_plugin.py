from unittest.mock import patch

from qgis.core import QgsSettings
from qgis.PyQt.QtCore import QEvent, Qt, QTimer
from qgis.PyQt.QtTest import QTest
from qgis.PyQt.QtWidgets import QApplication, QDialog, QDialogButtonBox, QTreeView

from e2e.test_utils import (
    click_context_menu_action,
    click_tree_item,
    make_modal_handler,
)
from rana_qgis_plugin.auth import is_authenticated
from rana_qgis_plugin.constant import RANA_AUTHCFG_ENTRY
from rana_qgis_plugin.utils.api import (
    create_project,
    delete_project,
    get_tenant_projects,
)
from rana_qgis_plugin.utils.settings import (
    base_url,
    get_tenant_id,
    set_hidden_projects,
)
from rana_qgis_plugin.widgets.projects_selection_dialog import ProjectsSelectionDialog


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
    root = plugin.data_item_provider.root_item

    with patch.object(root, "refresh") as mock_refresh:
        simulate_external_refocus(plugin, qgis_application)
        mock_refresh.assert_called_once()


def test_refocus_not_triggered_by_settings_dialog(plugin, qtbot, qgis_application):
    """Opening and closing the settings dialog must not trigger a refresh."""
    root = plugin.data_item_provider.root_item

    def dismiss(qtbot, modal):
        modal.reject()

    with patch.object(root, "refresh") as mock_refresh:
        QTimer.singleShot(200, make_modal_handler(qtbot, QDialog, dismiss))
        plugin.rana_root_item.open_settings()
        QTest.qWait(500)
        qgis_application.processEvents()

        mock_refresh.assert_not_called()


def test_select_projects(plugin, qtbot):
    import uuid

    names = ["test_project_" + str(uuid.uuid4()) for _ in range(3)]
    projects = [
        create_project({"code": name[:32], "name": name[:64]}) for name in names
    ]

    try:
        tree = plugin.browser_dock.findChild(QTreeView)
        assert tree is not None

        tree_model = tree.model()
        rana_index = next(
            (
                tree_model.index(row, 0)
                for row in range(tree_model.rowCount())
                if tree_model.data(tree_model.index(row, 0)).startswith("Rana")
            ),
            None,
        )
        assert rana_index is not None, "Rana item not found in browser tree"
        click_tree_item(tree, rana_index, qtbot)
        qtbot.waitUntil(
            lambda: all(
                name in {child.name() for child in plugin.rana_root_item.children()}
                for name in names
            ),
            timeout=30000,
        )
        child_by_name = {
            child.name(): child for child in plugin.rana_root_item.children()
        }
        hidden_name = names[0]
        click_context_menu_action(
            qtbot, child_by_name[hidden_name], "Don't show this project"
        )
        qtbot.waitUntil(
            lambda: (
                hidden_name
                not in {child.name() for child in plugin.rana_root_item.children()}
            ),
            timeout=30000,
        )
        visible_names = {child.name() for child in plugin.rana_root_item.children()}
        assert sorted(visible_names) == sorted(names[1:])
        # Open projects selector
        click_context_menu_action(qtbot, plugin.rana_root_item, "Select projects")
        qtbot.waitUntil(
            lambda: isinstance(
                QApplication.activeModalWidget(), ProjectsSelectionDialog
            ),
            timeout=10000,
        )
        dialog = QApplication.activeModalWidget()
        assert isinstance(dialog, ProjectsSelectionDialog)
        model = dialog.projects_model
        qtbot.waitUntil(
            lambda: (
                {model.data(model.index(row, 1)) for row in range(model.rowCount())}
                == set(names)
            ),
            timeout=30000,
        )

        # assert checkbox states
        def checkbox_index(name):
            return next(
                (
                    model.index(row, 0)
                    for row in range(model.rowCount())
                    if model.data(model.index(row, 1)) == name
                ),
                None,
            )

        for name in names:
            assert checkbox_index(name) is not None
            expected_cb_state = (
                Qt.CheckState.Unchecked if name == names[0] else Qt.CheckState.Checked
            )
            assert (
                model.data(checkbox_index(name), Qt.ItemDataRole.CheckStateRole)
                == expected_cb_state
            )
        # uncheck first checkbox
        first_index = checkbox_index(names[0])
        qtbot.mouseClick(
            dialog.projects_tv.viewport(),
            Qt.MouseButton.LeftButton,
            pos=dialog.projects_tv.visualRect(first_index).center(),
        )
        qtbot.waitUntil(
            lambda: (
                model.data(first_index, Qt.ItemDataRole.CheckStateRole)
                == Qt.CheckState.Checked
            ),
            timeout=5000,
        )
        # check second checkbox
        second_index = checkbox_index(names[1])
        qtbot.mouseClick(
            dialog.projects_tv.viewport(),
            Qt.MouseButton.LeftButton,
            pos=dialog.projects_tv.visualRect(second_index).center(),
        )
        qtbot.waitUntil(
            lambda: (
                model.data(second_index, Qt.ItemDataRole.CheckStateRole)
                == Qt.CheckState.Unchecked
            ),
            timeout=5000,
        )
        # close dialog
        buttons = dialog.findChild(QDialogButtonBox)
        assert buttons is not None
        with qtbot.waitSignal(dialog.finished, timeout=5000):
            qtbot.mouseClick(
                buttons.button(QDialogButtonBox.StandardButton.Ok),
                Qt.MouseButton.LeftButton,
            )
        qtbot.waitUntil(
            lambda: (
                {child.name() for child in plugin.rana_root_item.children()}
                == {names[0], names[2]}
            ),
            timeout=30000,
        )
    finally:
        set_hidden_projects(base_url(), get_tenant_id(), set())
        for project in projects:
            if project is not None:
                delete_project(project["id"])
