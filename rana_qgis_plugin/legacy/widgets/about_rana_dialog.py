import os.path

from qgis.PyQt.QtWidgets import QDialog
from qgis.PyQt.uic import loadUi


class AboutRanaDialog(QDialog):
    def __init__(self, parent):
        super(AboutRanaDialog, self).__init__(parent)
        ui_fn = os.path.join(os.path.dirname(__file__), "ui", "about_rana_dialog.ui")
        loadUi(ui_fn, self)
