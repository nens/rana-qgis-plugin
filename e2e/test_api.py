from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtTest import QTest


def test_smoke(plugin, qgis_application):
    rana_tool_button = plugin.toolbar.widgetForAction(plugin.action)
    # QTest.mouseClick(rana_tool_button, Qt.LeftButton)
    plugin.run()
    assert True
