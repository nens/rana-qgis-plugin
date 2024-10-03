import os

from qgis.core import QgsMessageLog
from qgis.PyQt.QtWidgets import QTableWidget, QTableWidgetItem

class RanaFileDetails:
    def __init__(self, table_widget: QTableWidget):
        self.table_widget = table_widget
        self.table_widget.horizontalHeader().hide()
        self.table_widget.hide()

    def hide_file_details(self):
        self.table_widget.hide()

    def show_file_details(self, file):
        self.table_widget.clearContents()
        self.table_widget.setRowCount(3)
        self.table_widget.setColumnCount(2)

        # Define labels and values
        labels = ["Filename", "Size", "Type"]
        values = [
            os.path.basename(file["id"].rstrip("/")),
            f"{file["size"]} bytes",
            file["type"]
        ]

        # Populate the table
        for i, (label, value) in enumerate(zip(labels, values)):
            self.table_widget.setItem(i, 0, QTableWidgetItem(label))
            self.table_widget.setItem(i, 1, QTableWidgetItem(value))

        # Resize the columns
        self.table_widget.resizeColumnsToContents()
        self.table_widget.show()
