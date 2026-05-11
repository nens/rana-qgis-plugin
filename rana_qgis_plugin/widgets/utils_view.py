from qgis.PyQt.QtCore import QRect, Qt, pyqtSignal
from qgis.PyQt.QtWidgets import QHeaderView, QStyle, QTreeView


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


class CheckableHeaderView(QHeaderView):
    """
    A QHeaderView that renders a tri-state checkbox in section 0.
    Emits check_state_changed(Qt.CheckState) when the user clicks the checkbox.
    Use set_check_state() to update the visual state from outside.
    """

    check_state_changed = pyqtSignal(int)  # Qt.CheckState (int-backed enum)

    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self._check_state = Qt.CheckState.Unchecked
        self.setSectionsClickable(True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_state(self) -> Qt.CheckState:
        return self._check_state

    def set_check_state(self, state: Qt.CheckState):
        """Update the visual checkbox state without emitting a signal."""
        if self._check_state != state:
            self._check_state = state
            self.viewport().update()

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def paintSection(self, painter, rect, logical_index):
        painter.save()
        super().paintSection(painter, rect, logical_index)
        painter.restore()
        if logical_index != 0:
            return
        painter.save()
        # Explicitly set clip to the section rect so our drawing is not clipped
        # by whatever the base class left behind.
        painter.setClipRect(rect)
        cb_rect = self._checkbox_rect(rect)
        self._draw_checkbox(painter, cb_rect)
        painter.restore()

    def _draw_checkbox(self, painter, rect):
        """Draw a checkbox indicator using Qt's style primitives.
        Uses QStyleOptionViewItem so the draw call is consistent with how
        the item delegate renders row checkboxes."""
        from qgis.PyQt.QtWidgets import QApplication, QStyleOptionViewItem

        opt = QStyleOptionViewItem()
        opt.rect = rect
        opt.state = QStyle.State_Enabled
        if self._check_state == Qt.CheckState.Checked:
            opt.state |= QStyle.State_On
        elif self._check_state == Qt.CheckState.PartiallyChecked:
            opt.state |= QStyle.State_NoChange
        else:
            opt.state |= QStyle.State_Off
        # Use QApplication.style() (the raw application style) to match exactly
        # how QStyledItemDelegate draws row checkboxes.
        QApplication.style().drawPrimitive(
            QStyle.PrimitiveElement.PE_IndicatorViewItemCheck, opt, painter
        )

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------

    def mousePressEvent(self, event):
        logical = self.logicalIndexAt(event.pos())
        if logical == 0:
            section_rect = QRect(
                self.sectionViewportPosition(0), 0, self.sectionSize(0), self.height()
            )
            if self._checkbox_rect(section_rect).contains(event.pos()):
                self._handle_checkbox_click()
                return
        super().mousePressEvent(event)

    def _handle_checkbox_click(self):
        """Toggle the checkbox state and emit check_state_changed."""
        # Partial state is set programmatically (by the model); clicking always
        # resolves to Checked (if not already Checked) or Unchecked. This is
        # intentional — the user never directly sets PartiallyChecked via click.
        new_state = (
            Qt.CheckState.Unchecked
            if self._check_state == Qt.CheckState.Checked
            else Qt.CheckState.Checked
        )
        self._check_state = new_state
        self.viewport().update()
        self.check_state_changed.emit(new_state)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _checkbox_rect(self, section_rect):
        """Return a QRect centered in section_rect using the same indicator size
        as QStyledItemDelegate uses for row checkboxes (PM_IndicatorWidth/Height)."""
        from qgis.PyQt.QtWidgets import QApplication

        w = QApplication.style().pixelMetric(QStyle.PixelMetric.PM_IndicatorWidth)
        h = QApplication.style().pixelMetric(QStyle.PixelMetric.PM_IndicatorHeight)
        x = section_rect.x() + (section_rect.width() - w) // 2
        y = section_rect.y() + (section_rect.height() - h) // 2
        return QRect(x, y, w, h)
