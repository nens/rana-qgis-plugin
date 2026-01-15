from qgis.core import QgsApplication
from qgis.PyQt.QtCore import QSize
from qgis.PyQt.QtGui import QPixmap
from qgis.PyQt.QtWidgets import QLabel


def get_icon_from_theme(icon_name: str) -> QPixmap:
    return QgsApplication.getThemeIcon(icon_name).pixmap(QSize(32, 32))


def get_icon_label(icon: QPixmap) -> QLabel:
    icon_label = QLabel()
    icon_label.setPixmap(icon)
    return icon_label
