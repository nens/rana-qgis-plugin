from qgis.PyQt.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from rana_qgis_plugin.constant import PLUGIN_NAME
from rana_qgis_plugin.utils_settings import (
    base_url,
    cognito_client_id,
    set_base_url,
    set_cognito_client_id,
)


class SettingsDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle(PLUGIN_NAME)
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)
        self.setLayout(layout)

        auth_group = QGroupBox("Authentication", self)
        auth_group.setLayout(QGridLayout())

        # Set up GUI and populate with settings
        auth_group.layout().addWidget(QLabel("Backend URL"), 0, 0)
        self.url_lineedit = QLineEdit(base_url(), auth_group)
        auth_group.layout().addWidget(self.url_lineedit, 0, 1)

        # Set up GUI and populate with settings
        auth_group.layout().addWidget(QLabel("Cognito client ID"), 1, 0)
        self.cognito_client_id_lineedit = QLineEdit(cognito_client_id(), auth_group)
        auth_group.layout().addWidget(self.cognito_client_id_lineedit, 1, 1)

        layout.addWidget(auth_group)

        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)
        layout.addWidget(buttonBox)

        self._authenticationSettingsChanged = False

    def authenticationSettingsChanged(self):
        return self._authenticationSettingsChanged

    def accept(self) -> None:
        if self.cognito_client_id_lineedit.text() != cognito_client_id():
            self._authenticationSettingsChanged = True
            set_cognito_client_id(self.cognito_client_id_lineedit.text())

        if self.url_lineedit.text() != base_url():
            self._authenticationSettingsChanged = True
            set_base_url(self.url_lineedit.text())

        return super().accept()
