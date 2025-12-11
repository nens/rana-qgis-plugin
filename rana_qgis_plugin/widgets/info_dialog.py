from qgis.PyQt.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout

rana_hcc_url = f"<a href='https://ranawaterintelligence.com/hcc-management'>ranawaterintelligence.com/hcc-management</a>"


class InfoDialog(QDialog):
    def __init__(self, info_msg: str, window_title: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout()
        label = QLabel(info_msg)
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        layout.addWidget(label)
        layout.addWidget(button_box)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        self.setWindowTitle(window_title)
        self.setLayout(layout)


class CreateModelDialog(InfoDialog):
    def __init__(self, parent=None):
        super().__init__(
            info_msg=f"Rana model creation started. Follow progress here: {rana_hcc_url}",
            window_title="Rana model creation started",
            parent=parent,
        )


class SaveRevisionDialog(InfoDialog):
    def __init__(self, parent=None):
        super().__init__(
            info_msg=f"Rana revision being saved. Follow progress here: {rana_hcc_url}",
            window_title="Revision being saved",
            parent=parent,
        )


class RunSimulationDialog(InfoDialog):
    def __init__(self, parent=None):
        super().__init__(
            info_msg=f"Rana revision simulation started. Follow progress here: {rana_hcc_url}",
            window_title="Revision simulation started",
            parent=parent,
        )
