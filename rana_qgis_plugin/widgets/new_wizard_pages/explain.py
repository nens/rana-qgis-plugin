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
    def __init__(self, parent):
        super().__init__(parent)
        self.main_widget = SchematisationExplainWidget(self)
        layout = QGridLayout()
        layout.addWidget(self.main_widget)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)


class SchematisationExplainWidget(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Explain")

        # Grid layout
        gridLayout = QGridLayout(self)

        description_label = QLabel()
        description_label.setAlignment(Qt.AlignLeading | Qt.AlignLeft | Qt.AlignTop)
        description_label.setWordWrap(True)

        description_label.setText("""
        <html><head/><body>
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
        finetune the resulting settings after the schematization has been created.</span></p>
        <p align="justify"><br/></p>
        </body></html>
        """)
        gridLayout.addWidget(description_label, 0, 0)

        gridLayout.addItem(
            QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding), 1, 0
        )
