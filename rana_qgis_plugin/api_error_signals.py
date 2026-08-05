"""Signals for reporting API errors to the plugin UI."""

from qgis.PyQt.QtCore import QObject, pyqtSignal


class ApiErrorSignals(QObject):
    """Shared API error signals owned by the plugin's data item provider."""

    connection_lost = pyqtSignal()
    fetch_error_occurred = pyqtSignal(str)
