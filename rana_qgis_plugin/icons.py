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
settings_icon = QgsApplication.getThemeIcon("/processingAlgorithm.svg")

# Exported PYQT5 icons
style = QApplication.style()
dir_icon = style.standardIcon(QStyle.SP_DirIcon)
file_icon = style.standardIcon(QStyle.SP_FileIcon)
