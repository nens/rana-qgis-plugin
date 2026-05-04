from dataclasses import dataclass, field
from typing import Callable, Optional

from qgis.gui import QgsCheckableComboBox
from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QSizePolicy,
    QToolButton,
    QWidget,
)

from rana_qgis_plugin.icons import refresh_icon


@dataclass
class TextFilterConfig:
    """Configuration for a text search filter."""

    key: str
    placeholder: str


@dataclass
class ComboFilterConfig:
    """Configuration for a multi-select combo filter."""

    key: str
    placeholder: str
    dynamic: bool = True
    items: list[tuple[str, str]] = field(default_factory=list)
    # items format for static combos: list of (display_label, user_data)


class FilterBar(QWidget):
    """Horizontal filter bar with text search and multi-select combo filters.

    Emits filters_changed(dict) whenever any filter value changes.
    The dict keys match the filter config keys; text filters return str,
    combo filters return list of checked userData values.
    """

    filters_changed = pyqtSignal(dict)

    def __init__(
        self,
        filters: list,
        refresh_callback: Callable,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._line_edits: dict[str, QLineEdit] = {}
        self._combos: dict[str, QgsCheckableComboBox] = {}

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        for config in filters:
            if isinstance(config, TextFilterConfig):
                widget = QLineEdit()
                widget.setPlaceholderText(config.placeholder)
                widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                widget.textChanged.connect(self._emit_changed)
                self._line_edits[config.key] = widget
                layout.addWidget(widget)
            elif isinstance(config, ComboFilterConfig):
                widget = QgsCheckableComboBox()
                widget.setDefaultText(config.placeholder)
                widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                if not config.dynamic:
                    for label, data in config.items:
                        widget.addItemWithCheckState(label, 0, userData=data)
                widget.checkedItemsChanged.connect(self._emit_changed)
                self._combos[config.key] = widget
                layout.addWidget(widget)

        self._refresh_btn = QToolButton()
        self._refresh_btn.setIcon(refresh_icon)
        self._refresh_btn.setToolTip("Refresh")
        self._refresh_btn.clicked.connect(refresh_callback)
        layout.addWidget(self._refresh_btn)

        self.setLayout(layout)

    def _emit_changed(self):
        self.filters_changed.emit(self.get_filters())

    def get_filters(self) -> dict:
        """Return current filter values keyed by filter config key."""
        result = {}
        for key, widget in self._line_edits.items():
            result[key] = widget.text()
        for key, widget in self._combos.items():
            result[key] = widget.checkedItemsData()
        return result

    def set_combo_items(
        self, key: str, items: list[tuple[str, str, Optional[QIcon]]]
    ):
        """Populate a combo filter. items: list of (label, user_data, icon_or_None)."""
        combo = self._combos[key]
        combo.blockSignals(True)
        combo.deselectAllOptions()
        while combo.count():
            combo.removeItem(0)
        for label, data, icon in items:
            combo.addItemWithCheckState(label, 0, userData=data)
            if icon:
                combo.setItemIcon(combo.count() - 1, QIcon(icon))
        combo.blockSignals(False)

    def update_combo_avatar(self, key: str, user_id: str, avatar):
        """Update the avatar icon for a specific user entry in a combo filter."""
        combo = self._combos[key]
        for i in range(combo.count()):
            if combo.itemData(i) == user_id:
                combo.setItemIcon(i, QIcon(avatar))
                break
