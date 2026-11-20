from qgis.PyQt.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
)


class CommitMessageDialog(QDialog):
    """Collect an optional commit message for a new upload batch."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Commit message")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Commit message (optional):"))
        self.message_edit = QPlainTextEdit()
        self.message_edit.setPlaceholderText("Describe these uploaded files")
        layout.addWidget(self.message_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    def message(self) -> str | None:
        message = self.message_edit.toPlainText().strip()
        return message or None
