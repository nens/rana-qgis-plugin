import os

from qgis.core import QgsMessageLog
from qgis.PyQt.QtWidgets import QWidget, QVBoxLayout, QLabel

class RanaFileDetails(QWidget):
    def __init__(self, file, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.file = file
        self.file_name = os.path.basename(file["id"].rstrip("/"))
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(self.file_name))
