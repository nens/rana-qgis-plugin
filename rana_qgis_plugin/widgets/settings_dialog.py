"""Rana settings dialog."""

from qgis.PyQt.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from rana_qgis_plugin.auth import update_auth_settings
from rana_qgis_plugin.constant import PLUGIN_NAME
from rana_qgis_plugin.utils.local_paths import is_writable
from rana_qgis_plugin.utils.settings import base_url, rana_root_dir, set_rana_root_dir


class RanaSettingsDialog(QDialog):
    """Settings dialog for Rana."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(PLUGIN_NAME)
        self.setMinimumWidth(400)
        self._url_changed = False
        self._authentication_reset = False

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

        storage_group = QGroupBox("Storage")
        storage_layout = QGridLayout(storage_group)
        storage_layout.addWidget(QLabel("Root directory"), 0, 0)
        self._root_dir_edit = QLineEdit(rana_root_dir())
        storage_layout.addWidget(self._root_dir_edit, 0, 1)
        browse_button = QPushButton("Browse")
        browse_button.clicked.connect(self.browse_root_dir)
        storage_layout.addWidget(browse_button, 0, 2)
        layout.addWidget(storage_group)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        reset_authentication = QPushButton("Reset authentication")
        button_box.addButton(
            reset_authentication, QDialogButtonBox.ButtonRole.ResetRole
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        reset_authentication.clicked.connect(self.reset_authentication)
        layout.addWidget(button_box)

    def url_changed(self) -> bool:
        """Return True if the backend URL was changed on accept."""
        return self._url_changed

    def authentication_reset(self) -> bool:
        """Return whether authentication reset was confirmed."""
        return self._authentication_reset

    def browse_root_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, "Select Root Directory", self._root_dir_edit.text()
        )
        if not directory:
            return
        if not is_writable(directory):
            QMessageBox.warning(
                self,
                "Warning",
                "Can't write to the selected location. Please select a folder to which you have write permission.",
            )
            return
        self._root_dir_edit.setText(directory)

    def reset_authentication(self) -> None:
        title = "Reset authentication"
        text = (
            "Reset Rana authentication and sign out? "
            "Your backend URL and local plugin settings will be preserved."
        )
        message = QMessageBox(self)
        message.setIcon(QMessageBox.Icon.Warning)
        message.setWindowTitle(title)
        message.setText(text)
        message.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        message.setDefaultButton(QMessageBox.StandardButton.No)
        if message.exec() == QMessageBox.StandardButton.Yes:
            self._authentication_reset = True
            super().accept()

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
        set_rana_root_dir(self._root_dir_edit.text().strip())
        super().accept()
