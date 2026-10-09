"""Reusable debounced search input for plugin dialogs."""

from qgis.PyQt.QtCore import QTimer, pyqtSignal
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QLineEdit


class DebouncedSearchBox(QLineEdit):
    """Line edit that emits search text after typing pauses, with search/clear icons."""

    # Custom signal that will be emitted when the debounced search should occur
    searchChanged = pyqtSignal(str)

    def __init__(
        self,
        parent=None,
        delay_ms=1000,
        min_chars=0,
        placeholder="Search...",
        show_search_icon=True,
    ):
        super().__init__(parent)

        # Setup timer for debouncing
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_timeout)

        self.delay_ms = delay_ms
        self.min_chars = min_chars

        # Setup UI
        self.setPlaceholderText(placeholder)
        if show_search_icon:
            self.addAction(
                QIcon(":images/themes/default/mIconZoom.svg"),
                QLineEdit.ActionPosition.LeadingPosition,
            )

        # Clear button -- visible only when there is text
        self._clear_action = self.addAction(
            QIcon(":images/themes/default/mIconClearText.svg"),
            QLineEdit.ActionPosition.TrailingPosition,
        )
        self._clear_action.setVisible(False)
        self._clear_action.triggered.connect(self._on_clear)

        # Connect the text changed signal
        self.textEdited.connect(self._on_text_edited)

    def _on_text_edited(self, text):
        """Handle edited text and start the debounce timer if eligible."""
        self._clear_action.setVisible(bool(text))
        self._timer.stop()
        if len(text) >= self.min_chars or len(text) == 0:
            self._timer.start(self.delay_ms)

    def _on_clear(self):
        """Clear text and emit searchChanged immediately."""
        self._timer.stop()
        self.clear()
        self._clear_action.setVisible(False)
        self.searchChanged.emit("")

    def _on_timeout(self):
        """Emit the searchChanged signal with current text."""
        self.searchChanged.emit(self.text())
