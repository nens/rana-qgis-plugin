import os.path

from qgis.core import QgsApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QApplication, QStyle

# Base path for the icons directory
ICONS_DIR = os.path.join(os.path.dirname(__file__), "icons")

# Exported custom icons
login_icon = QIcon(os.path.join(ICONS_DIR, "login.svg"))
logout_icon = QIcon(os.path.join(ICONS_DIR, "logout.svg"))
refresh_icon = QIcon(os.path.join(ICONS_DIR, "refresh.svg"))
rana_icon = QIcon(os.path.join(ICONS_DIR, "rana.svg"))
separator_icon = QIcon(os.path.join(ICONS_DIR, "separator.svg"))
ellipsis_icon = QIcon(os.path.join(ICONS_DIR, "ellipsis.svg"))
settings_icon = QgsApplication.getThemeIcon("/processingAlgorithm.svg")


def get_safe_icon(standard_pixmap):
    """Safely get a standard icon, with fallback to a blank QIcon"""
    app = QApplication.instance()
    if app and app.style():
        return app.style().standardIcon(standard_pixmap)
    return QIcon()  # Return empty icon as fallback


# Use the safe function
dir_icon = get_safe_icon(QStyle.StandardPixmap.SP_DirIcon)
file_icon = get_safe_icon(QStyle.StandardPixmap.SP_FileIcon)
