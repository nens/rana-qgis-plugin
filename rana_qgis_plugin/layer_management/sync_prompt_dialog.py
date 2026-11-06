from qgis.gui import QgsCollapsibleGroupBox
from qgis.PyQt.QtCore import Qt, QTimer
from qgis.PyQt.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
)

from rana_qgis_plugin.layer_management.sync_changes import SyncChanges, SyncKind
from rana_qgis_plugin.layer_management.sync_summary import (
    build_details,
    build_summary,
    build_sync_notice,
)

SYNC_NOW = "Sync now"
CONTINUE_WITHOUT_SYNCING = "Continue without syncing"
OK = "OK"
DETAILS_MAX_HEIGHT = 240
DEFAULT_WIDTH = 480
MIN_WIDTH = 320


class SyncPromptDialog(QDialog):
    """Summary line plus a collapsible, scrollable list of the changed layers.

    Subclasses supply the title and summary, and add their buttons to
    `button_row`.
    """

    def __init__(
        self,
        parent,
        title: str,
        summary_html: str,
        changes: SyncChanges,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowSystemMenuHint
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
        )
        self.setSizeGripEnabled(True)
        self.setMinimumWidth(MIN_WIDTH)

        self.summary_label = QLabel(summary_html)
        self.summary_label.setTextFormat(Qt.TextFormat.RichText)
        self.summary_label.setWordWrap(True)

        self.details_box = QgsCollapsibleGroupBox("More details")

        details_label = QLabel(build_details(changes))
        details_label.setTextFormat(Qt.TextFormat.RichText)
        details_label.setWordWrap(True)
        details_label.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.details_area = QScrollArea()
        self.details_area.setWidget(details_label)
        self.details_area.setWidgetResizable(True)
        self.details_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.details_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.details_area.setMaximumHeight(DETAILS_MAX_HEIGHT)

        details_layout = QVBoxLayout(self.details_box)
        details_layout.addWidget(self.details_area)
        # Collapse after the area is added, so the box hides it and the layout
        # does not count it in the size.
        self.details_box.setCollapsed(True)
        self.details_box.collapsedStateChanged.connect(self.fit_height_later)

        self.button_row = QHBoxLayout()
        self.button_row.addStretch()

        layout = QVBoxLayout(self)
        layout.addWidget(self.summary_label, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.details_box, 0, Qt.AlignmentFlag.AlignTop)
        layout.addStretch()
        layout.addLayout(self.button_row)
        self.resize(DEFAULT_WIDTH, layout.sizeHint().height())
        self.fitted_to_contents = False

    def showEvent(self, event) -> None:
        """Fit the height on first show, once the collapsed box has hidden its content."""
        super().showEvent(event)
        if not self.fitted_to_contents:
            self.fitted_to_contents = True
            self.fit_height_later()

    def fit_height_later(self) -> None:
        """Fit the height once the group box has updated the layout.

        `QgsCollapsibleGroupBox` only hides or shows its content after emitting
        `collapsedStateChanged`, so the size hint is stale until the event loop runs.
        Fitting directly in the signal handler leaves the dialog the wrong height.
        """
        QTimer.singleShot(0, self.fit_height)

    def fit_height(self) -> None:
        """Resize the height to the contents.

        The details area is capped at `DETAILS_MAX_HEIGHT`, which bounds the result.
        """
        self.resize(self.width(), self.layout().sizeHint().height())


class CloseSyncDialog(SyncPromptDialog):
    """Modal question asked before unsynced changes are lost."""

    def __init__(self, parent, changes: SyncChanges):
        super().__init__(parent, "Unsynced changes", build_summary(changes), changes)
        self.clicked_label = ""
        sync_button = QPushButton(SYNC_NOW)
        sync_button.clicked.connect(
            lambda: self.choose(SYNC_NOW, QDialog.DialogCode.Accepted)
        )
        continue_button = QPushButton(CONTINUE_WITHOUT_SYNCING)
        continue_button.clicked.connect(
            lambda: self.choose(CONTINUE_WITHOUT_SYNCING, QDialog.DialogCode.Rejected)
        )
        self.button_row.addWidget(sync_button)
        self.button_row.addWidget(continue_button)

    def choose(self, label: str, result: QDialog.DialogCode):
        self.clicked_label = label
        if result == QDialog.DialogCode.Accepted:
            self.accept()
        else:
            self.reject()

    def selected_label(self) -> str:
        return self.clicked_label


class OnDemandSyncDialog(SyncPromptDialog):
    """Non-blocking notice that a sync of one kind has started."""

    def __init__(self, parent, kind: SyncKind, changes: SyncChanges):
        changes = changes.for_kind(kind)
        super().__init__(
            parent, "Sync started", build_sync_notice(kind, changes), changes
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        ok_button = QPushButton(OK)
        ok_button.clicked.connect(self.close)
        self.button_row.addWidget(ok_button)
