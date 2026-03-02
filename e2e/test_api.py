import os
from time import sleep

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtTest import QTest


def test_smoke(plugin):
    secret = os.getenv("RANA_PAK")
    print(secret)
    print(type(secret))
    rana_tool_button = plugin.toolbar.widgetForAction(plugin.action)
    # QTest.mouseClick(rana_tool_button, Qt.LeftButton)
    # sleep(2)
    # # rana_tool_button.click()
    # plugin.run()

    # print("*******")
    # assert plugin.rana_browser.projects_browser.projects_tv.model().rowCount() == 1
    # sleep(10)
    # # import pdb
    # # pdb.set_trace()
    # # plugin.run()
    
    # # print(dir(plugin))
    # sleep(10)
    assert False
