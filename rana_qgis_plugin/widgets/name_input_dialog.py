"""Reusable name-input dialog for rename and create-folder actions."""

from __future__ import annotations

from collections.abc import Callable

from qgis.PyQt.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)


def validate_item_name(name: str) -> str | None:
    """Return an error message if *name* is not a valid file/folder name, else None."""
    if not name or not name.strip():
        return "Name cannot be empty."
    if name in (".", ".."):
        return "Name cannot be '.' or '..'."
    if "/" in name or "\\" in name:
        return "Name cannot contain slashes."
    if name != name.strip():
        return "Name cannot have leading or trailing spaces."
    return None


class NameInputDialog(QDialog):
    """Small dialog with a line edit, inline error label, and OK/Cancel buttons.

    Parameters
    ----------
    title:
        Window title (e.g. "Rename file", "Create folder").
    label:
        Prompt text above the input field.
    initial_value:
        Pre-filled text (current name for rename, empty for create).
    submit_callback:
        Called with the entered name when OK is clicked. Must return None on
        success or an error string on failure. On failure the dialog stays open
        and shows the error.
    parent:
        Parent widget.
    """

    def __init__(
        self,
        title: str,
        label: str,
        initial_value: str,
        submit_callback: Callable[[str], str | None],
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.initial_value = initial_value
        self.submit_callback = submit_callback

        layout = QVBoxLayout(self)

        self.label = QLabel(label)
        layout.addWidget(self.label)

        self.line_edit = QLineEdit(initial_value)
        self.line_edit.selectAll()
        self.line_edit.textChanged.connect(self.on_text_changed)
        layout.addWidget(self.line_edit)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: red;")
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)

        self.button_box = QDialogButtonBox(self)
        ok_button = self.button_box.addButton(QDialogButtonBox.StandardButton.Ok)
        assert ok_button is not None
        self.ok_button = ok_button
        self.button_box.addButton(QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.on_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        # Run initial validation
        self.on_text_changed(initial_value)

    def on_text_changed(self, text: str) -> None:
        error = validate_item_name(text)
        if error is None and self.initial_value and text == self.initial_value:
            error = "Name has not changed."
        self.ok_button.setEnabled(error is None)
        if error:
            self.error_label.setText(error)
            self.error_label.setVisible(True)
        else:
            self.error_label.setVisible(False)

    def on_accept(self) -> None:
        name = self.line_edit.text()
        error = self.submit_callback(name)
        if error:
            self.error_label.setText(error)
            self.error_label.setVisible(True)
        else:
            self.accept()
