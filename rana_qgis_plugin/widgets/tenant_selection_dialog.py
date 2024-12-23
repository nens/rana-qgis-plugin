import os.path

from qgis.PyQt.QtWidgets import QDialog
from qgis.PyQt.uic import loadUi


class TenantSelectionDialog(QDialog):
    def __init__(self, parent):
        super(TenantSelectionDialog, self).__init__(parent)
        ui_fn = os.path.join(os.path.dirname(__file__), "ui", "tenant_selection_dialog.ui")
        loadUi(ui_fn, self)
