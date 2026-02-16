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


class SimpleErrorDialog(QDialog):
    def __init__(self, error_message, trace, parent=None):
        super().__init__(parent)
        self.setWindowTitle("An error occurred")
        self.setMinimumSize(600, 400)

        # Main layout
        main_layout = QVBoxLayout(self)

        # Error message at the top
        error_label = QLabel(error_message)
        error_label.setWordWrap(True)
        main_layout.addWidget(error_label)

        # Traceback text box with monospace font
        self.trace_text = QTextEdit()
        self.trace_text.setReadOnly(True)

        # Set monospace font
        font = QFont("Monospace")  # Use system monospace font
        font.setStyleHint(
            QFont.Monospace
        )  # Fallback to any monospace if specific one not available
        font.setFixedPitch(True)
        self.trace_text.setFont(font)

        # Preserve formatting
        self.trace_text.setLineWrapMode(QTextEdit.NoWrap)
        self.trace_text.setText(trace)

        main_layout.addWidget(self.trace_text)

        # Button layout
        button_layout = QHBoxLayout()

        # Copy button
        copy_button = QPushButton("Copy error")
        copy_button.clicked.connect(self.copy_traceback)
        button_layout.addWidget(copy_button)

        # Spacer to push close button to the right
        button_layout.addStretch()

        # Close button
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)

        main_layout.addLayout(button_layout)

        # Store trace for copy operation
        self.trace = trace

    def copy_traceback(self):
        """Copy the traceback to clipboard"""
        QApplication.clipboard().setText(self.trace)
