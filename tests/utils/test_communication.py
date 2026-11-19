from qgis.PyQt.QtWidgets import QDialog, QWidget

from rana_qgis_plugin.communication import resolve_parent


def test_resolve_parent_returns_explicit_parent(qgis_application):
    parent = QWidget()
    assert resolve_parent(parent) is parent


def test_resolve_parent_uses_active_modal_widget(qgis_application, qtbot):
    dialog = QDialog()
    dialog.setModal(True)
    dialog.show()
    qtbot.addWidget(dialog)
    assert resolve_parent() is dialog
    dialog.close()


def test_resolve_parent_falls_back_to_none_without_modal_or_iface(qgis_application):
    assert resolve_parent() is None
