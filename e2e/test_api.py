from time import sleep

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtTest import QTest


def test_smoke(plugin):
    rana_tool_button = plugin.toolbar.widgetForAction(plugin.action)
    # QTest.mouseClick(rana_tool_button, Qt.LeftButton)
    sleep(10)
    rana_tool_button.click()

    print("*******")
    print(plugin.rana_browser.projects_browser.projects_tv.model().rowCount())
    # import pdb
    # pdb.set_trace()
    # plugin.run()
    # print(dir(plugin))
    sleep(10)
    assert True
