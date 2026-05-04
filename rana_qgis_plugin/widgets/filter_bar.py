from dataclasses import dataclass, field
from typing import Optional

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QSizePolicy,
    QWidget,
)

from rana_qgis_plugin.widgets.utils_search import DebouncedSearchBox


@dataclass
class TextFilterConfig:
    """Configuration for a text search filter."""

    key: str
    placeholder: str


@dataclass
class ComboFilterConfig:
    """Configuration for a single-select combo filter with optional icons."""

    key: str
    placeholder: str
    dynamic: bool = True
    items: list[tuple[str, str]] = field(default_factory=list)
    # items format for static combos: list of (display_label, user_data)


class FilterBar(QWidget):
    """Horizontal filter bar with text search and combo filters.

    Emits filters_changed(dict) whenever any filter value changes.
    The dict keys match the filter config keys; text filters return str,
    combo filters return the selected userData value (or None if unselected).
    """

    filters_changed = pyqtSignal(dict)

    def __init__(
        self,
        filters: list,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._line_edits: dict[str, DebouncedSearchBox] = {}
        self._combos: dict[str, QComboBox] = {}

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        for config in filters:
            if isinstance(config, TextFilterConfig):
                widget = DebouncedSearchBox(
                    delay_ms=400,
                    placeholder=config.placeholder,
                    show_search_icon=False,
                )
                widget.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
                widget.searchChanged.connect(self._emit_changed)
                self._line_edits[config.key] = widget
                layout.addWidget(widget, stretch=1)
            elif isinstance(config, ComboFilterConfig):
                widget = QComboBox()
                widget.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
                widget.setMinimumWidth(0)
                widget.setEditable(True)
                widget.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
                widget.completer().setCaseSensitivity(Qt.CaseInsensitive)
                if widget.lineEdit():
                    widget.lineEdit().setPlaceholderText(config.placeholder)
                    widget.lineEdit().textChanged.connect(
                        lambda text, w=widget: self._on_combo_text_changed(w, text)
                    )
                if not config.dynamic:
                    for label, data in config.items:
                        widget.addItem(label, userData=data)
                    widget.setCurrentIndex(-1)
                widget.currentIndexChanged.connect(self._emit_changed)
                self._combos[config.key] = widget
                layout.addWidget(widget, stretch=1)

        self.setLayout(layout)

    def _on_combo_text_changed(self, combo: QComboBox, text: str):
        """Reset combo selection when the text field is cleared."""
        if not text:
            combo.setCurrentIndex(-1)

    def _emit_changed(self, _=None):
        self.filters_changed.emit(self.get_filters())

    def get_filters(self) -> dict:
        """Return current filter values keyed by filter config key."""
        result = {}
        for key, widget in self._line_edits.items():
            result[key] = widget.text()
        for key, widget in self._combos.items():
            result[key] = widget.currentData()
        return result

    def set_combo_items(self, key: str, items: list[tuple[str, str, Optional[object]]]):
        """Populate a combo filter. items: list of (label, user_data, icon_or_None)."""
        combo = self._combos[key]
        combo.blockSignals(True)
        prev_data = combo.currentData()
        combo.clear()
        new_index = -1
        for i, (label, data, icon) in enumerate(items):
            if icon:
                combo.addItem(QIcon(icon), label, userData=data)
            else:
                combo.addItem(label, userData=data)
            if data == prev_data and prev_data is not None:
                new_index = i
        combo.setCurrentIndex(new_index)
        combo.blockSignals(False)

    def update_combo_avatar(self, key: str, user_id: str, avatar):
        """Update the avatar icon for a specific user entry in a combo filter."""
        combo = self._combos[key]
        for i in range(combo.count()):
            if combo.itemData(i) == user_id:
                combo.setItemIcon(i, QIcon(avatar))
                break

    def reset(self):
        """Reset all filters to their default (empty) state."""
        for widget in self._line_edits.values():
            widget.blockSignals(True)
            widget.clear()
            widget.blockSignals(False)
        for widget in self._combos.values():
            widget.blockSignals(True)
            widget.setCurrentIndex(-1)
            widget.blockSignals(False)
        self._emit_changed()
