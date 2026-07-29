"""Rana settings dialog."""

from qgis.PyQt.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from rana_qgis_plugin.auth import update_auth_settings
from rana_qgis_plugin.constant import PLUGIN_NAME
from rana_qgis_plugin.utils.settings import base_url


class RanaSettingsDialog(QDialog):
    """Settings dialog for Rana. For this increment: backend URL only."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(PLUGIN_NAME)
        self.setMinimumWidth(400)
        self._url_changed = False

        layout = QVBoxLayout(self)

        auth_group = QGroupBox("Authentication")
        auth_layout = QGridLayout(auth_group)
        auth_layout.addWidget(QLabel("Backend URL"), 0, 0)
        self._url_edit = QLineEdit(base_url())
        auth_layout.addWidget(self._url_edit, 0, 1)
        note = QLabel("Note: changing the URL will require re-authentication.")
        note.setWordWrap(True)
        auth_layout.addWidget(note, 1, 0, 1, 2)
        layout.addWidget(auth_group)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def url_changed(self) -> bool:
        """Return True if the backend URL was changed on accept."""
        return self._url_changed

    def accept(self) -> None:
        new_url = self._url_edit.text().strip().rstrip("/")
        if new_url != base_url():
            if not update_auth_settings(new_url):
                msg = QMessageBox(self)
                msg.setIcon(QMessageBox.Icon.Critical)
                msg.setWindowTitle("Error")
                msg.setText(
                    "Can't fetch settings from this backend URL. Please check the URL and try again."
                )
                revert_button = msg.addButton(
                    "Revert URL", QMessageBox.ButtonRole.ResetRole
                )
                msg.addButton("Keep Editing", QMessageBox.ButtonRole.RejectRole)
                msg.exec()
                if msg.clickedButton() is revert_button:
                    self._url_edit.setText(base_url())
                return
            self._url_changed = True
        super().accept()
