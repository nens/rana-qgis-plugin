from typing import Optional

from qgis.PyQt.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout

from rana_qgis_plugin.utils_settings import base_url


def get_hcc_url(path: Optional[str] = None) -> str:
    hcc_path = f"{base_url()}/hcc-management"
    if path:
        hcc_path += "/" + path
    return f"<a href='{hcc_path}'>{hcc_path}</a>"


class InfoDialog(QDialog):
    def __init__(self, info_msg: str, window_title: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout()
        label = QLabel(info_msg)
        label.setOpenExternalLinks(True)
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
            info_msg=f"Rana model creation started. Follow progress here: {get_hcc_url()}",
            window_title="Rana model creation started",
            parent=parent,
        )


class SaveRevisionDialog(InfoDialog):
    def __init__(self, parent=None):
        super().__init__(
            info_msg=f"Rana revision being saved. Follow progress here: {get_hcc_url()}",
            window_title="Revision being saved",
            parent=parent,
        )
