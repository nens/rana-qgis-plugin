from unittest.mock import MagicMock, patch

from qgis.PyQt.QtCore import QCoreApplication, QEvent
from qgis.PyQt.QtWidgets import QMainWindow

from rana_qgis_plugin.loader import Loader
from rana_qgis_plugin.widgets.processes_panel import ProcessesPanel


def test_open_processes_dock_creates_floating_project_dock(qgis_application):
    main_window = QMainWindow()
    communication = MagicMock()
    communication.iface.mainWindow.return_value = main_window
    communication.iface.addDockWidget.side_effect = main_window.addDockWidget
    loader = Loader(communication)
    project = {"id": "project-1", "name": "Project", "slug": "project"}

    with patch.object(ProcessesPanel, "start_polling") as start_polling:
        dock = loader.open_processes_dock(project, MagicMock())
        qgis_application.processEvents()

    assert loader.process_docks["project-1"] is dock
    assert dock.windowTitle() == "Processes: Project"
    assert dock.isFloating()
    assert isinstance(dock.widget(), ProcessesPanel)
    start_polling.assert_called_once_with()

    second_dock = loader.open_processes_dock(
        {"id": "project-2", "name": "Second", "slug": "second"}, MagicMock()
    )
    assert second_dock is not dock
    assert loader.process_docks == {"project-1": dock, "project-2": second_dock}

    dock.deleteLater()
    second_dock.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert loader.process_docks == {}
    main_window.close()


def test_open_processes_dock_raises_existing_project_dock(qgis_application):
    main_window = QMainWindow()
    communication = MagicMock()
    communication.iface.mainWindow.return_value = main_window
    communication.iface.addDockWidget.side_effect = main_window.addDockWidget
    loader = Loader(communication)
    project = {"id": "project-1", "name": "Project", "slug": "project"}

    with patch.object(ProcessesPanel, "start_polling"):
        first_dock = loader.open_processes_dock(project, MagicMock())
        first_dock.hide()
        second_dock = loader.open_processes_dock(project, MagicMock())
        qgis_application.processEvents()

    assert second_dock is first_dock
    assert first_dock.isVisible()
    communication.iface.addDockWidget.assert_called_once()

    first_dock.close()
    first_dock.deleteLater()
    main_window.close()


def test_process_dock_visibility_pauses_and_resumes_polling(qgis_application):
    main_window = QMainWindow()
    communication = MagicMock()
    communication.iface.mainWindow.return_value = main_window
    communication.iface.addDockWidget.side_effect = main_window.addDockWidget
    loader = Loader(communication)
    project = {"id": "project-1", "name": "Project", "slug": "project"}

    with patch.object(ProcessesPanel, "_request_fetch"):
        dock = loader.open_processes_dock(project, MagicMock())
        panel = dock.widget()
        assert isinstance(panel, ProcessesPanel)
        qgis_application.processEvents()
        assert panel.polling

        dock.hide()
        qgis_application.processEvents()
        assert not panel.polling

        dock.show()
        qgis_application.processEvents()
        assert panel.polling

    panel.stop_polling()
    dock.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    main_window.close()
