from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)
from qgis.PyQt.QtCore import Qt, QTimer


class ErrorDialog(QDialog):
    def __init__(self, error_message, trace, parent=None):
        super().__init__(parent)
        self.setWindowTitle("An error occurred")
        self.setMinimumSize(600, 400)

        # Main layout
        main_layout = QVBoxLayout(self)

        # Error message at the top
        error_label = QLabel(error_message)
        error_label.setWordWrap(True)
        error_label.setTextInteractionFlags(
            Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard
        )
        error_label.setCursor(Qt.IBeamCursor)
        main_layout.addWidget(error_label)

        # Traceback text box with monospace font
        trace_text = QTextEdit()
        trace_text.setReadOnly(True)

        # Set monospace font
        font = QFont("Monospace")  # Use system monospace font
        font.setStyleHint(
            QFont.Monospace
        )  # Fallback to any monospace if specific one not available
        font.setFixedPitch(True)
        trace_text.setFont(font)

        # Preserve formatting
        trace_text.setLineWrapMode(QTextEdit.NoWrap)
        trace_text.setText(trace)

        main_layout.addWidget(trace_text)

        # Button layout
        bottom_layout = QHBoxLayout()

        # Copy button
        copy_button = QPushButton("Copy error")
        bottom_layout.addWidget(copy_button)

        confirm_label = QLabel("error copied to clipboard")
        confirm_label.hide()
        bottom_layout.addWidget(confirm_label)
        copy_button.clicked.connect(
            lambda: self.copy_with_confirmation(trace, confirm_label)
        )

        # Spacer to push close button to the right
        bottom_layout.addStretch()

        # Close button
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        bottom_layout.addWidget(close_button)

        main_layout.addLayout(bottom_layout)

        # Store trace for copy operation
        self.trace = trace

    @staticmethod
    def copy_with_confirmation(trace, label):
        # Copy to clipboard
        QApplication.clipboard().setText(trace)

        label.show()

        # Hide the label after 2 seconds using QTimer
        QTimer.singleShot(2000, label.hide)


def show_error_dialog_with_helpdesk_message(trace):
    msg = "An unhandled error occurred. Please contact the helpdesk via support@ranawaterintelligence.com and include a copy of this error in your message."
    dialog = ErrorDialog(msg, trace)
    dialog.exec()
