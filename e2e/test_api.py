from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtTest import QTest


def test_smoke(plugin):
    rana_tool_button = plugin.toolbar.widgetForAction(plugin.action)
    QTest.mouseClick(rana_tool_button, Qt.LeftButton)
    # import pdb
    # pdb.set_trace()
    # plugin.run()
    # print(dir(plugin))
    assert False
