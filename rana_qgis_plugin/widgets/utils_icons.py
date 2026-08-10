from qgis.core import QgsApplication
from qgis.PyQt.QtCore import QSize
from qgis.PyQt.QtGui import QIcon, QPixmap
from qgis.PyQt.QtWidgets import QLabel


def get_icon_from_theme(icon_name: str) -> QIcon:
    return QgsApplication.getThemeIcon(icon_name)


def get_icon_from_theme_as_pixmap(icon_name: str) -> QPixmap:
    return get_icon_from_theme(icon_name).pixmap(QSize(32, 32))


def get_icon_label(icon: QPixmap) -> QLabel:
    icon_label = QLabel()
    icon_label.setPixmap(icon)
    return icon_label
