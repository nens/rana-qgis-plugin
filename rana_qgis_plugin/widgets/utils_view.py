from qgis.PyQt.QtWidgets import QTreeView


class ContentAwareTreeView(QTreeView):
    """
    A QTreeView that intelligently resizes columns to fit their content,
    even accounting for collapsed items in hierarchical views.
    Useful for displaying long filenames or text without truncation.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

    def resize_columns_aware_of_collapsed_items(self):
        """
        Resize columns to fit their contents, including collapsed items.

        This method temporarily expands all items to measure their content width,
        resizes the columns accordingly, then restores the original collapsed state.
        """
        # Save current collapsed status
        expanded_states = {}
        for row in range(self.model().rowCount()):
            self._save_expanded_states(self.model().index(row, 0), expanded_states)
        # Temporarily expand all items
        for row in range(self.model().rowCount()):
            self._expand_all_items(self.model().index(row, 0))
        # Resize columns to fit *all items*, including collapsed ones
        for col in range(self.model().columnCount()):
            self.resizeColumnToContents(col)
        # Restore the original collapsed state
        for row in range(self.model().rowCount()):
            self._restore_expanded_states(self.model().index(row, 0), expanded_states)

    def _save_expanded_states(self, index, expanded_states):
        """
        Recursively save the expanded/collapsed state of all items.
        """
        if not index.isValid():
            return
        expanded_states[index] = self.isExpanded(index)
        for row in range(index.model().rowCount(index)):
            self._save_expanded_states(index.child(row, 0), expanded_states)

    def _expand_all_items(self, index):
        """
        Recursively expand all items in the tree view.
        """
        if not index.isValid():
            return
        self.setExpanded(index, True)
        for row in range(index.model().rowCount(index)):
            self._expand_all_items(index.child(row, 0))

    def _restore_expanded_states(self, index, expanded_states):
        """
        Recursively restore the expanded/collapsed state of items.
        """
        if not index.isValid():
            return
        if index in expanded_states:
            self.setExpanded(index, expanded_states[index])
        for row in range(index.model().rowCount(index)):
            self._restore_expanded_states(index.child(row, 0), expanded_states)
