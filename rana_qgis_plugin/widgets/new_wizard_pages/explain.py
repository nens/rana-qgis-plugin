"""Explanation page used by the from-scratch schematisation wizard."""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QGridLayout,
    QLabel,
    QSizePolicy,
    QSpacerItem,
    QWidget,
    QWizardPage,
)


class SchematisationExplainPage(QWizardPage):
    """Explain the settings step before users configure a new model."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QGridLayout(self)
        self.main_widget = SchematisationExplainWidget(self)
        layout.addWidget(self.main_widget, 0, 0)
        layout.addItem(
            QSpacerItem(
                20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding
            ),
            1,
            0,
        )


class SchematisationExplainWidget(QWidget):
    """Widget holding the explanation text from the legacy wizard."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Explain")
        grid_layout = QGridLayout(self)
        description = QLabel(self)
        grid_layout.addWidget(description, 0, 0)
        description.setAlignment(
            Qt.AlignmentFlag.AlignLeading
            | Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignTop
        )
        description.setWordWrap(True)
        description.setText(
            """<html><head/><body>
            <p align="justify"><span style=" font-size:14pt;">
            Almost there! To create a valid schematisation, you will have to choose many settings.
            Choosing the right settings is important for a well-working model. This can be quite a challenge,
            requiring a thorough understanding of the Rana computational core.</span></p>
            <p align="justify"><br/></p>
            <p align="justify"><span style=" font-size:14pt;">
            This wizard will help you with this as much as possible. After you have completed it,
            we generate a model with valid global and numerical settings.</span></p>
            <p align="justify"><br/></p>
            <p align="justify"><span style=" font-size:14pt;">
            Where possible, we use sensible defaults suitable to most use cases. However, some settings
            are fully dependent on your use case and need to be chosen by you. To guide you through this,
            we will ask you some questions, to understand what kind of model you are going to build.</span></p>
            <p align="justify"><br/></p>
            <p align="justify"><span style=" font-size:14pt;">
            We have kept the list of questions as short as possible. We strongly advise you to check and
            finetune the resulting settings after the schematisation has been created.</span></p>
            <p align="justify"><br/></p>
            </body></html>"""
        )
        grid_layout.addItem(
            QSpacerItem(
                20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding
            ),
            1,
            0,
        )
