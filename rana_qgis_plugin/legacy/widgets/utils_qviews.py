# Utils related to QTableView and QTreeView
from typing import Union

from qgis.PyQt.QtCore import QAbstractItemModel
from qgis.PyQt.QtWidgets import QTableView, QTreeView


def update_width_with_wrapping(
    qview: Union[QTableView, QTreeView], model: QAbstractItemModel, wrap_column: int
):
    # The custom WordWrapDelegate sets a very small size hint and then uses that for wrapping
    # to the contents of the first column cannot be used for resizing
    # Instead we have to calculate and set the space manually
    used_width = 0
    for col in range(model.columnCount()):
        if col == wrap_column:
            continue
        qview.resizeColumnToContents(col)
        used_width += qview.columnWidth(col)
    remaining_width = max(qview.viewport().width() - used_width, 100)
    qview.setColumnWidth(wrap_column, remaining_width)
