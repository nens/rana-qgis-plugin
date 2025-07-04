from qgis.PyQt.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QVBoxLayout,
)

from rana_qgis_plugin.constant import PLUGIN_NAME

class ResultBrowser(QDialog):
    def __init__(self, parent, results):
        super().__init__(parent)
        self.setWindowTitle(PLUGIN_NAME)
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)
        self.setLayout(layout)

        results_group = QGroupBox("Results", self)
        results_group.setLayout(QGridLayout())

        # # Set up GUI and populate with settings
        # auth_group.layout().addWidget(QLabel("Backend URL"), 0, 0)
        # self.url_lineedit = QLineEdit(base_url(), auth_group)
        # auth_group.layout().addWidget(self.url_lineedit, 0, 1)

        # # Set up GUI and populate with settings
        # auth_group.layout().addWidget(QLabel("Cognito client ID"), 1, 0)
        # self.cognito_client_id_lineedit = QLineEdit(cognito_client_id(), auth_group)
        # auth_group.layout().addWidget(self.cognito_client_id_lineedit, 1, 1)

        layout.addWidget(auth_group)

        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)
        layout.addWidget(buttonBox)


    def accept(self) -> None:
        return super().accept()
