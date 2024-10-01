import os

from qgis.PyQt import uic

base_dir = os.path.dirname(__file__)
rana_uicls, rana_basecls = uic.loadUiType(os.path.join(base_dir, "ui", "rana.ui"))

class RanaBrowser(rana_uicls, rana_basecls):
    def __init__(self, plugin, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.plugin = plugin
        self.projects = []
