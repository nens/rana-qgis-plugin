from qgis.core import Qgis, QgsMessageLog


def plugin_log_info(msg: str) -> None:
    QgsMessageLog.logMessage(msg, "Rana", Qgis.MessageLevel.Info)


def plugin_log_warn(msg: str) -> None:
    QgsMessageLog.logMessage(msg, "Rana", Qgis.MessageLevel.Warning)


def plugin_log_error(msg: str) -> None:
    QgsMessageLog.logMessage(msg, "Rana", Qgis.MessageLevel.Critical)
